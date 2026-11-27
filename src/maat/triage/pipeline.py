from datetime import datetime, timezone
from pathlib import Path

from maat.model import Report
from maat.triage.catalog import ReportRef, build_catalog, ref_for_path
from maat.triage.diff import ReportDiff, diff_reports, reconcile, worst_category
from maat.triage.known_issues import load_known_issues
from maat.triage.model import Analysis
from maat.triage.pivot import Pivot, choose_pivots, strip_run_number, target_kind
from maat.utils.log import log, track
from maat.utils.shell import join_command

HISTORY_DEPTH = 4


def run_triage(
    report_path: Path,
    pivot_names: list[str] | None = None,
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

    status, notes = _final_status(diffs)
    headline = _fallback_headline(diffs)

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
        status=status,
        status_notes=notes,
        headline=headline,
        rerun_command=_rerun_command(target),
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


def _final_status(diffs: list[ReportDiff]) -> tuple[str, list[str]]:
    """
    Deterministic status: green when the diff shows no new failures, amber otherwise.
    Red needs a judgement the data alone can't make.
    """
    if not diffs:
        return "amber", ["no pivot report available; nothing to compare against"]

    primary = diffs[0]
    # Regressions against any pivot count (an RC can be unchanged vs the previous RC and
    # still be broken vs the last stable release).
    news = primary.of_kind("regression", "changed-failure", "new-project") + [
        c for d in diffs[1:] for c in d.of_kind("regression")
    ]
    unknown_news = [c for c in news if not c.known_issue]
    if unknown_news:
        return "amber", []
    return "green", []


def _fallback_headline(diffs: list[ReportDiff]) -> str:
    if not diffs:
        return "No pivot report found; nothing to compare against."
    d = diffs[0]
    reg = len(d.of_kind("regression"))
    fix = len(d.of_kind("fix"))
    chg = len(d.of_kind("changed-failure"))
    s = f"vs {d.pivot}: {reg} regressions, {chg} changed failures, {fix} fixes."
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
