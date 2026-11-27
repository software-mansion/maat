from datetime import datetime, timezone
from pathlib import Path

from maat.model import Report
from maat.triage.catalog import ReportRef, build_catalog, ref_for_path
from maat.triage.changelog import changelogs as fetch_changelogs
from maat.triage.diff import ReportDiff, diff_reports, reconcile, worst_category
from maat.triage.known_issues import load_known_issues
from maat.triage.llm import build_prompt, call_claude
from maat.triage.model import STATUS_RANK, Analysis, LlmMeta, Triage
from maat.triage.pivot import Pivot, choose_pivots, strip_run_number, target_kind
from maat.utils.log import log, track
from maat.utils.shell import join_command

HISTORY_DEPTH = 4

# Classifications under which a regression is "explained" and need not hold the status at amber.
_EXPLAINED = {"known-issue", "flaky", "infra", "project-change"}


def run_triage(
    report_path: Path,
    pivot_names: list[str] | None = None,
    use_llm: bool = True,
    dry_run_prompt: Path | None = None,
    include_history: bool = True,
    run_url: str | None = None,
) -> Analysis:
    target_ref = ref_for_path(report_path)
    target = target_ref.load()

    with track("Building report catalog"):
        catalog = build_catalog(include_history=include_history)
    by_name = {r.name: r for r in catalog}

    if pivot_names:
        missing = [n for n in pivot_names if n not in by_name]
        if missing:
            raise ValueError(f"unknown pivot report(s): {', '.join(missing)}")
        pivots = [Pivot(name=n, reason="chosen manually") for n in pivot_names]
    else:
        pivots = choose_pivots(target_ref, catalog)
    for p in pivots:
        log(f"📌 pivot {p.name}: {p.reason}")

    known_issues = load_known_issues()
    history = _history(target_ref, catalog)

    diffs: list[ReportDiff] = []
    for p in pivots:
        with track(f"Diffing against {p.name}"):
            diffs.append(
                diff_reports(
                    target=target,
                    target_name=target_ref.name,
                    pivot=by_name[p.name].load(),
                    pivot_name=p.name,
                    pivot_reason=p.reason,
                    known_issues=known_issues,
                    history=history,
                )
            )
    reconcile(diffs)

    changelogs = []
    if diffs:
        with track("Fetching upstream changelogs"):
            changelogs = fetch_changelogs(
                diffs[0].pivot_versions, diffs[0].target_versions
            )

    triage: Triage | None = None
    llm: LlmMeta | None = None
    if diffs:
        prompt = build_prompt(
            target_ref.name, diffs[0].target_versions, diffs, changelogs, known_issues
        )
        if dry_run_prompt is not None:
            dry_run_prompt.write_text(prompt, encoding="utf-8")
            log(
                f"📝 prompt written to {dry_run_prompt} ({len(prompt)} chars); LLM not called"
            )
        elif use_llm:
            with track("Asking Claude"):
                triage, llm = call_claude(prompt)
            if llm.error:
                log(f"⚠️ LLM step failed: {llm.error}")

    if triage is not None:
        triage = _sanitize(triage, diffs, changelogs)

    status, notes = _final_status(triage, diffs)
    headline = triage.headline if triage else _fallback_headline(diffs, llm)

    return Analysis(
        report=target_ref.name,
        generated_at=datetime.now(timezone.utc),
        target_versions={
            "workspace": target.workspace,
            "scarb": target.scarb,
            "foundry": target.foundry,
            "maat": target.maat_commit[:9],
        },
        pivots=pivots,
        diffs=diffs,
        changelogs=changelogs,
        triage=triage,
        status=status,
        status_notes=notes,
        headline=headline,
        rerun_command=_rerun_command(target),
        llm=llm,
        run_url=run_url,
    )


def _history(target: ReportRef, catalog: list[ReportRef]) -> dict[str, list[str]]:
    """
    Worst outcome per project in the most recent earlier reports of the same kind.

    Reports of other kinds (e.g. dev or custom runs in the release workspace) run different
    toolchains, so mixing them in would make toolchain differences look like flakiness.
    Entries are tagged with the tool versions so the LLM can tell the two apart.
    """
    kind = target_kind(target)
    series = strip_run_number(target.name) if kind == "custom" else None
    earlier = sorted(
        (
            r
            for r in catalog
            if r.header.workspace == target.header.workspace
            and r.header.created_at < target.header.created_at
            and r.name != target.name
            and target_kind(r) == kind
            and (series is None or strip_run_number(r.name) == series)
        ),
        key=lambda r: r.header.created_at,
    )[-HISTORY_DEPTH:]
    history: dict[str, list[str]] = {}
    for ref in earlier:
        try:
            report = ref.load()
        except Exception as e:  # noqa: BLE001
            log(f"⚠️ cannot load {ref.name} for history: {e}")
            continue
        tools = f"{ref.header.scarb}/{ref.header.foundry}"
        for t in report.tests:
            history.setdefault(t.name, []).append(f"{worst_category(t)}@{tools}")
    return history


def _sanitize(triage: Triage, diffs: list[ReportDiff], changelogs) -> Triage:
    """Drop references the input doesn't contain; the LLM must not introduce new facts."""
    known_projects = {c.project for d in diffs for c in d.changes} | {
        o.project for d in diffs for o in d.performance.outliers
    }
    known_shas = {c.sha for cl in changelogs for c in cl.commits}
    known_lint = {k.id for k in diffs[0].lint.kinds} if diffs else set()

    for f in triage.findings:
        f.projects = [p for p in f.projects if p in known_projects]
        f.suspected_commits = [
            s
            for s in f.suspected_commits
            if any(k.startswith(s[:7]) or s.startswith(k) for k in known_shas)
        ]
        f.lint_kinds = [k for k in f.lint_kinds if k in known_lint]
    for a in triage.actions:
        a.projects = [p for p in a.projects if p in known_projects]
    return triage


def _final_status(
    triage: Triage | None, diffs: list[ReportDiff]
) -> tuple[str, list[str]]:
    """
    Clamp the LLM status to what the data shows:
    nothing new and no perf regression ⇒ green; unexplained regressions ⇒ at least amber.
    Without an LLM verdict the status is green or amber, never red.
    """
    notes: list[str] = []
    if not diffs:
        return "amber", ["no pivot report available; nothing to compare against"]

    primary = diffs[0]
    # Regressions against any pivot block a forced green (an RC can be unchanged vs the
    # previous RC and still be broken vs the last stable release). Only the primary pivot
    # forces amber below, so long-standing differences don't pin every nightly to amber.
    news = primary.of_kind("regression", "changed-failure", "new-project") + [
        c for d in diffs[1:] for c in d.of_kind("regression")
    ]
    unknown_news = [c for c in news if not c.known_issue]
    perf_regressed = primary.performance.regressed
    lint_shift = primary.lint.significant_kinds()

    if triage is None:
        status = "amber" if (unknown_news or perf_regressed or lint_shift) else "green"
        if status == "amber":
            notes.append(
                "LLM triage unavailable; amber because there are unexplained changes"
            )
        return status, notes

    status = triage.status
    if not unknown_news and not perf_regressed and not lint_shift and status != "green":
        notes.append(
            f"LLM said {status}, but the diff shows no new failures, no performance "
            "regression and no significant lint change"
        )
        status = "green"

    explained = {
        p for f in triage.findings if f.classification in _EXPLAINED for p in f.projects
    }
    unexplained = [
        c.project
        for c in primary.of_kind("regression")
        if not c.known_issue and c.project not in explained
    ]
    if unexplained and STATUS_RANK[status] < STATUS_RANK["amber"]:
        notes.append(
            f"raised to amber: unexplained regressions in {', '.join(unexplained[:5])}"
        )
        status = "amber"

    # A lint change may be intended (new lint) or not (a lint broken along the way), so each
    # significant kind needs its own justification: an intended change backed by a commit.
    justified = {
        k
        for f in triage.findings
        if f.classification == "intended-breaking-change" and f.suspected_commits
        for k in f.lint_kinds
    }
    unjustified = [k for k in lint_shift if k.id not in justified]
    if unjustified and STATUS_RANK[status] < STATUS_RANK["amber"]:
        notes.append(
            "raised to amber: lint diagnostic changes not attributed to an intended upstream "
            "change: " + "; ".join(f"{k.id} {k.kind[:60]}" for k in unjustified[:3])
        )
        status = "amber"
    return status, notes


def _fallback_headline(diffs: list[ReportDiff], llm: LlmMeta | None) -> str:
    if not diffs:
        return "No pivot report found; nothing to compare against."
    d = diffs[0]
    reg = len(d.of_kind("regression"))
    fix = len(d.of_kind("fix"))
    chg = len(d.of_kind("changed-failure"))
    s = f"vs {d.pivot}: {reg} regressions, {chg} changed failures, {fix} fixes."
    if lint := d.lint.significant_kinds():
        s += f" Lint diagnostics changed ({len(lint)} kinds)."
    if llm and llm.error:
        s += " (LLM triage unavailable)"
    return s


def _rerun_command(report: Report) -> str:
    return join_command(
        [
            "gh",
            "workflow",
            "run",
            "experiment.yml",
            "-f",
            f"workspace={report.workspace}",
            "-f",
            f"scarb={report.scarb}",
            "-f",
            f"foundry={report.foundry}",
        ]
    )


STATUS_EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴"}


def slack_fields(analysis: Analysis, analysis_url: str) -> dict[str, str]:
    """Variables for the Slack workflow. ``thread_text`` is empty when there is nothing to say."""
    status = f"{STATUS_EMOJI[analysis.status]} {analysis.status.upper()}"
    lines: list[str] = []
    t = analysis.triage
    if t is not None:
        # The thread is for things someone has to look at: known issues and performance
        # findings that aren't a regression stay on the page only.
        perf_news = t.performance.verdict in ("regressed", "mixed")
        news = [
            f
            for f in t.findings
            if f.classification != "known-issue"
            and (f.classification != "performance" or perf_news)
        ]
        for f in news[:3]:
            projects = ", ".join(f.projects[:3]) + (" …" if len(f.projects) > 3 else "")
            lines.append(
                f"• *{f.title}* ({f.classification}, {f.confidence})"
                + (f" — {projects}" if projects else "")
            )
        if len(news) > 3:
            lines.append(f"…and {len(news) - 3} more findings")
        if t.actions:
            lines.append(
                f"{len(t.actions)} action item(s): "
                + "; ".join(a.title for a in t.actions[:3])
            )
        if t.performance.verdict in ("regressed", "mixed"):
            lines.append(f"Performance: {t.performance.summary}")
    elif analysis.status != "green" and analysis.primary is not None:
        lines.append(analysis.headline)
    if lines:
        lines.append(f"Details: {analysis_url}")
    return {
        "status": status,
        "summary": analysis.headline,
        "analysis_url": analysis_url,
        "thread_text": "\n".join(lines),
    }
