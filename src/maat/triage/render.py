"""
Static HTML page for one analysis, served at ``<site>/analysis/<report>.html``.

All links are built here from deterministic data (never from LLM output), and every string
is HTML-escaped. Paths are relative to the ``analysis/`` directory of the web build.
"""

from html import escape
from urllib.parse import quote, urlencode

from maat.triage.diff import ProjectChange, ReportDiff
from maat.triage.perf import fmt_amount as _amount
from maat.triage.model import Action, Analysis, Finding

_CSS = """
:root{--bg:#fff;--fg:#1d2127;--muted:#5d6670;--line:#e3e6ea;--card:#f7f8fa;--code:#f1f3f5;
--green:#1a7f37;--green-bg:#dafbe1;--amber:#9a6700;--amber-bg:#fff1c2;--red:#cf222e;--red-bg:#ffe1e0;--link:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e8eb;--muted:#9aa3ad;--line:#2a3038;--card:#161a20;--code:#1c2129;
--green:#4ac26b;--green-bg:#12301c;--amber:#d4a72c;--amber-bg:#3a2e0c;--red:#ff7b72;--red-bg:#3d1416;--link:#58a6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}a{color:var(--link)}h1{font-size:20px;margin:0 0 4px;word-break:break-all}
h2{font-size:16px;margin:32px 0 8px;padding-bottom:4px;border-bottom:1px solid var(--line)}h3{font-size:15px;margin:16px 0 6px}
.muted{color:var(--muted)}.small{font-size:13px}code,pre{font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);border-radius:4px}
code{padding:1px 4px}pre{padding:10px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
.pill{display:inline-block;font-weight:700;font-size:13px;padding:2px 10px;border-radius:999px;letter-spacing:.04em}
.green{color:var(--green);background:var(--green-bg)}.amber{color:var(--amber);background:var(--amber-bg)}.red{color:var(--red);background:var(--red-bg)}
.banner{border:1px solid var(--line);border-radius:8px;padding:14px 16px;background:var(--card);margin:16px 0}
.banner p{margin:6px 0 0;font-size:16px}.card{border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0;background:var(--card)}
.card .meta{font-size:13px;color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
.scroll{overflow-x:auto}ul.actions{list-style:none;padding:0;margin:0}ul.actions li{margin:8px 0}
details{margin:8px 0}summary{cursor:pointer;color:var(--muted)}.tag{font-size:12px;border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-right:4px;white-space:nowrap}
.hl{background:var(--amber-bg)}
"""

_STATUS_TEXT = {"green": "GREEN", "amber": "AMBER", "red": "RED"}


def render_analysis(analysis: Analysis, available_reports: set[str]) -> str:
    a = analysis
    t = a.triage
    e = escape
    out: list[str] = []
    w = out.append

    w("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    w("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    w(
        f"<title>Ma'at analysis · {e(a.report)}</title><style>{_CSS}</style></head><body><main>"
    )

    w(f"<h1>{e(a.report)}</h1>")
    v = a.target_versions
    w(
        f"<div class='muted small'>Scarb <code>{e(v['scarb'])}</code> · Foundry <code>{e(v['foundry'])}</code>"
        f" · workspace <code>{e(v['workspace'])}</code> · Ma'at <code>{e(v['maat'])}</code></div>"
    )

    w(
        f"<div class='banner'><span class='pill {a.status}'>{_STATUS_TEXT[a.status]}</span><p>{e(a.headline)}</p>"
    )
    for note in a.status_notes:
        w(f"<div class='muted small'>Guardrail: {e(note)}</div>")
    links = []
    if a.report in available_reports:
        links.append(
            f"<a href='../#s={quote(a.report)}&amp;p={quote(a.report)}'>Full report</a>"
        )
    if a.run_url:
        links.append(f"<a href='{e(a.run_url)}'>Workflow run</a>")
    if links:
        w(f"<div class='small' style='margin-top:8px'>{' · '.join(links)}</div>")
    w("</div>")

    # Pivots
    w("<h2>Compared against</h2><ul>")
    for d in a.diffs:
        cmp = ""
        if d.pivot in available_reports and a.report in available_reports:
            cmp = f" · <a href='../#s={quote(a.report + ' ' + d.pivot)}&amp;p={quote(d.pivot)}'>side by side</a>"
        w(
            f"<li><code>{e(d.pivot)}</code> — {e(d.pivot_reason)}"
            f" <span class='muted small'>(Scarb {e(d.pivot_versions['scarb'])}, Foundry {e(d.pivot_versions['foundry'])})</span>{cmp}</li>"
        )
    if not a.diffs:
        w("<li class='muted'>No suitable pivot report was found.</li>")
    w("</ul>")

    # Actions
    if t is not None:
        w("<h2>Action items</h2>")
        if t.actions:
            w("<ul class='actions'>")
            for act in t.actions:
                w(_action(act, a))
            w("</ul>")
        else:
            w("<p class='muted'>Nothing to do.</p>")

        w("<h2>Findings</h2>")
        if t.findings:
            for f in t.findings:
                w(_finding(f, a))
        else:
            w("<p class='muted'>No findings.</p>")
    elif a.llm and a.llm.error:
        w(
            f"<h2>Triage</h2><p class='muted'>LLM triage unavailable ({e(a.llm.error)}). Deterministic results below.</p>"
        )

    # Deterministic changes
    for d in a.diffs:
        w(_changes_section(d))

    # Performance
    if a.primary is not None:
        p = a.primary.performance
        w("<h2>Performance</h2>")
        if t is not None:
            w(
                f"<p><strong>{e(t.performance.verdict.replace('-', ' '))}</strong> — {e(t.performance.summary)}</p>"
            )
        if not p.comparable:
            w(f"<p class='muted'>Not comparable: {e(p.reason or '')}</p>")
        elif p.metrics:
            w(
                "<div class='scroll'><table><tr><th>Metric</th><th>Median ratio</th>"
                "<th>Middle 50%</th><th>&gt;20% slower / faster</th><th>Total</th></tr>"
            )
            for m in p.metrics:
                cls = " class='hl'" if m.significant else ""
                w(
                    f"<tr{cls}><td>{e(m.metric)}</td><td>{m.median_ratio:.2f}×</td>"
                    f"<td>{m.p25_ratio:.2f}–{m.p75_ratio:.2f}×</td>"
                    f"<td>{m.slower} / {m.faster} of {m.samples}</td>"
                    f"<td>{_amount(m.total_pivot, m.unit)} → {_amount(m.total_target, m.unit)}</td></tr>"
                )
            w(
                "</table></div><p class='muted small'>Ratios are target/pivot per project (same project in both "
                "reports). Highlighted rows: overall median shifted more than ±7%, or a test-runner group (≥10 projects) shifted more than ±15%.</p>"
            )
            for m in p.metrics:
                if not m.significant or not (m.groups or m.top):
                    continue
                w(f"<h3>What drives the {e(m.metric)} change</h3>")
                if m.groups:
                    w(
                        "<p class='small'>By test runner: "
                        + " · ".join(
                            f"<strong>{e(g.group)}</strong> {g.median_ratio:.2f}× ({g.samples} projects)"
                            for g in m.groups
                        )
                        + "</p>"
                    )
                if m.top:
                    w(
                        "<p class='small muted'>Largest absolute contributors:</p><ul class='small'>"
                    )
                    for o in m.top:
                        w(
                            f"<li><code>{e(o.project)}</code> {_amount(o.pivot, o.unit)} → {_amount(o.target, o.unit)}</li>"
                        )
                    w("</ul>")
            for ex in p.excluded:
                shifts = " · ".join(f"{e(k)} {v:.2f}×" for k, v in ex.medians.items())
                w(
                    f"<p class='small'>Excluded by known issue <code>{e(ex.issue)}</code> "
                    f"({ex.projects} projects); their own medians: {shifts or 'n/a'}</p>"
                )
            if p.outliers:
                w(
                    "<h3>Projects deviating from the overall trend</h3><ul class='small'>"
                )
                for o in p.outliers:
                    w(
                        f"<li><code>{e(o.project)}</code> {e(o.metric)}: {_amount(o.pivot, o.unit)} → {_amount(o.target, o.unit)}</li>"
                    )
                w(
                    "</ul><p class='muted small'>Single-project swings are common noise on shared CI VMs.</p>"
                )

        w(_lint_section(a))

        # Drift
        dr = a.primary.drift
        w("<h2>Ecosystem drift</h2>")
        if t is not None and t.drift_summary:
            w(f"<p>{e(t.drift_summary)}</p>")
        w(
            f"<p class='small'>{len(dr.added)} added · {len(dr.removed)} removed · "
            f"{len(dr.rev_changes)} projects at a different rev · Ma'at harness "
            f"{_harness_state(dr)}</p>"
        )
        if dr.added:
            w(
                f"<p class='small'>Added: {', '.join(f'<code>{e(x)}</code>' for x in dr.added)}</p>"
            )
        if dr.removed:
            w(
                f"<p class='small'>Removed: {', '.join(f'<code>{e(x)}</code>' for x in dr.removed)}</p>"
            )
        if dr.rev_changes:
            w("<details><summary>Rev changes</summary><ul class='small'>")
            for rc in dr.rev_changes:
                w(
                    f"<li><code>{e(rc.project)}</code> {e(rc.pivot)} → {e(rc.target)}</li>"
                )
            w("</ul></details>")
        if dr.maat_commits:
            w("<details><summary>Ma'at commits</summary><ul class='small'>")
            for line in dr.maat_commits:
                sha, _, subj = line.partition(" ")
                w(
                    f"<li><a href='https://github.com/software-mansion/maat/commit/{e(sha)}'><code>{e(sha)}</code></a> {e(subj)}</li>"
                )
            w("</ul></details>")

    # Upstream changes
    if a.changelogs:
        suspected = {s for f in (t.findings if t else []) for s in f.suspected_commits}
        w("<h2>Upstream changes</h2>")
        for cl in a.changelogs:
            title = (
                f"{e(cl.component)} <code>{e(cl.base)}</code>…<code>{e(cl.head)}</code>"
            )
            if cl.compare_url:
                title = f"<a href='{e(cl.compare_url)}'>{title}</a>"
            w(f"<h3>{title}</h3>")
            if cl.error:
                w(f"<p class='muted small'>{e(cl.error)}</p>")
                continue
            if cl.direction == "behind":
                w(
                    "<p class='small'>Target is <strong>older</strong> than the pivot; listed commits are missing from the target.</p>"
                )
            w(
                f"<details><summary>{cl.total_commits} commits</summary><ul class='small'>"
            )
            for c in cl.commits:
                cls = (
                    " class='hl'"
                    if any(c.sha.startswith(s[:7]) for s in suspected)
                    else ""
                )
                w(
                    f"<li{cls}><a href='{e(c.url)}'><code>{e(c.sha[:9])}</code></a> {e(c.subject)}</li>"
                )
            w("</ul></details>")

    # Footer
    w("<h2>About this analysis</h2><p class='muted small'>")
    w(f"Generated {e(a.generated_at.strftime('%Y-%m-%d %H:%M UTC'))}. ")
    if a.llm:
        tok = (
            f", {a.llm.input_tokens or 0:,} in / {a.llm.output_tokens or 0:,} out tokens"
            if a.llm.input_tokens
            else ""
        )
        req = (
            f", request <code>{e(a.llm.request_id)}</code>" if a.llm.request_id else ""
        )
        w(f"Triage by <code>{e(a.llm.model)}</code>{tok}{req}. ")
    w(
        "Facts (labels, timings, revs, commits) are computed deterministically; classifications and actions are the model's "
        "judgement and may be wrong. Rerun: "
    )
    w(f"<code>{e(a.rerun_command)}</code></p>")

    w("</main></body></html>")
    return "\n".join(out)


def _action(act: Action, a: Analysis) -> str:
    e = escape
    extra = ""
    if act.kind == "rerun":
        extra = f"<div><code>{e(a.rerun_command)}</code></div>"
    elif act.kind == "file-issue" and act.issue_repo != "none" and act.issue_title:
        q = urlencode({"title": act.issue_title, "body": act.issue_body[:6000]})
        extra = f"<div><a href='https://github.com/{e(act.issue_repo)}/issues/new?{e(q)}'>Open pre-filled issue in {e(act.issue_repo)}</a></div>"
    elif act.kind == "known-issue":
        extra = "<div class='muted small'>Add an entry to <code>known_issues.toml</code>.</div>"
    projects = "".join(f"<span class='tag'>{e(p)}</span>" for p in act.projects)
    return (
        f"<li><label><input type='checkbox'> <strong>{e(act.title)}</strong></label> <span class='tag'>{e(act.kind)}</span>"
        f"<div class='small'>{e(act.detail)}</div>{('<div>' + projects + '</div>') if projects else ''}{extra}</li>"
    )


def _finding(f: Finding, a: Analysis) -> str:
    e = escape
    logs = {}
    for d in a.diffs:
        for c in d.changes:
            if c.logs_href:
                logs.setdefault(c.project, c.logs_href)
    projects = " ".join(
        f"<a class='tag' href='../{e(logs[p])}'>{e(p)}</a>"
        if p in logs
        else f"<span class='tag'>{e(p)}</span>"
        for p in f.projects
    )
    evidence = "".join(f"<pre>{e(x)}</pre>" for x in f.evidence[:3])
    commits = ", ".join(f"<code>{e(s[:9])}</code>" for s in f.suspected_commits)
    lint = ", ".join(f"<a href='#lint-{e(k)}'>{e(k)}</a>" for k in f.lint_kinds)
    return (
        f"<div class='card'><strong>{e(f.title)}</strong>"
        f"<div class='meta'>{e(f.classification)} · {e(f.component)} · {e(f.confidence)} confidence"
        f"{(' · suspected commits ' + commits) if commits else ''}"
        f"{(' · lint ' + lint) if lint else ''}</div>"
        f"<p class='small'>{e(f.explanation)}</p>{('<div>' + projects + '</div>') if projects else ''}{evidence}</div>"
    )


def _lint_section(a: Analysis) -> str:
    e = escape
    lint = a.primary.lint
    out = [
        "<h2>Lint diagnostics</h2>",
        f"<p class='small'>Projects at the same rev in both reports: {lint.changed_projects} of "
        f"{lint.compared_projects} changed their lint output; {lint.kinds_total} diagnostic kinds changed.</p>",
    ]
    if not lint.kinds:
        return "\n".join(out)
    explained: dict[str, list[str]] = {}
    for f in a.triage.findings if a.triage else []:
        for k in f.lint_kinds:
            explained.setdefault(k, []).append(f.classification)
    out.append(
        "<div class='scroll'><table><tr><th>ID</th><th>Diagnostic</th><th>Count</th>"
        "<th>Projects with it</th><th>Changed in</th><th>Triage</th></tr>"
    )
    for k in lint.kinds:
        cls = " class='hl'" if k.significant else ""
        more = (
            f" +{k.changed_projects_total - len(k.changed_projects)} more"
            if k.changed_projects_total > len(k.changed_projects)
            else ""
        )
        out.append(
            f"<tr id='lint-{e(k.id)}'{cls}><td>{e(k.id)}</td><td><code>{e(k.kind)}</code></td>"
            f"<td>{k.pivot_count} → {k.target_count}</td><td>{k.pivot_projects} → {k.target_projects}</td>"
            f"<td class='small'>{e(', '.join(k.changed_projects))}{e(more)}</td>"
            f"<td class='small'>{e(', '.join(explained.get(k.id, [])) or '—')}</td></tr>"
        )
    out.append(
        "</table></div><p class='muted small'>Only projects whose rev is unchanged are compared, so "
        "these changes come from the toolchain. Highlighted: changed in ≥2 projects or by ≥5 "
        "diagnostics. Each highlighted kind keeps the status at least amber unless the triage "
        "attributes it to an intended upstream change with a suspected commit.</p>"
    )
    if lint.kinds_total > len(lint.kinds):
        out.append(
            f"<p class='muted small'>…and {lint.kinds_total - len(lint.kinds)} more changed kinds.</p>"
        )
    return "\n".join(out)


def _changes_section(d: ReportDiff) -> str:
    e = escape
    out = [f"<h2>Changes vs <code>{e(d.pivot)}</code></h2>"]
    groups = [
        ("Regressions", d.of_kind("regression")),
        ("Changed failures", d.of_kind("changed-failure")),
        ("New failing projects", d.of_kind("new-project")),
        ("Fixes", d.of_kind("fix")),
    ]
    still = d.of_kind("still-failing")
    out.append(
        "<p class='small'>"
        + " · ".join(f"{len(items)} {title.lower()}" for title, items in groups)
        + f" · {len(still)} still failing · {d.projects_clean}/{d.projects_total} clean</p>"
    )
    for title, items in groups:
        if items:
            out.append(f"<h3>{e(title)}</h3>{_table(items)}")
    if still:
        out.append(
            f"<details><summary>{len(still)} still failing (unchanged)</summary>{_table(still)}</details>"
        )
    return "\n".join(out)


def _table(items: list[ProjectChange]) -> str:
    e = escape
    rows = [
        "<div class='scroll'><table><tr><th>Project</th><th>Before</th><th>Now</th><th>Notes</th></tr>"
    ]
    for c in items:
        name = (
            f"<a href='../{e(c.logs_href)}'>{e(c.project)}</a>"
            if c.logs_href
            else e(c.project)
        )
        notes = []
        if c.rev_changed:
            notes.append(f"rev {e(c.rev_pivot or '')} → {e(c.rev_target or '')}")
        if c.known_issue:
            notes.append(f"known: {e(c.known_issue)}")
        if c.history:
            notes.append(f"history: {e(' '.join(c.history))}")
        if c.error_target:
            notes.append(f"now: <code>{e(c.error_target)}</code>")
        if c.error_pivot and c.error_pivot != c.error_target:
            notes.append(f"before: <code>{e(c.error_pivot)}</code>")
        rows.append(
            f"<tr><td>{name}</td><td>{e(', '.join(c.labels_pivot) or '—')}</td>"
            f"<td>{e(', '.join(c.labels_target) or '—')}</td><td class='small'>{'<br>'.join(notes)}</td></tr>"
        )
    rows.append("</table></div>")
    return "".join(rows)


def _harness_state(dr) -> str:
    if not dr.maat_changed:
        return "unchanged"
    if dr.maat_commits:
        return f"changed ({len(dr.maat_commits)} commits)"
    return "unchanged (different Ma'at commit, no harness changes)"
