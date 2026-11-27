"""
Deterministic comparison of a target report against a pivot report.

This is where all facts come from. The LLM only interprets what is computed here, and the
final status is clamped against it (see ``pipeline``), so nothing can be "found" that the
data doesn't show.
"""

import subprocess
from typing import Literal

from pydantic import BaseModel

from maat.installation import REPO
from maat.model import LabelCategory, Report, ReportMeta, TestReport, TestsSummary
from maat.triage.known_issues import KnownIssue, match_known_issue
from maat.triage.lint import LintDiff, lint_diff, reconcile_lint
from maat.triage.logs import error_set, error_signature, excerpt, lint_panicked
from maat.triage.perf import Performance, compare_performance
from maat.web.view_model import logs_txt_path

# Categories that describe a known-broken Ma'at setup rather than a toolchain outcome.
_IGNORED_CATEGORIES = {
    LabelCategory.TEST_PASS,
    LabelCategory.BROKEN,
    LabelCategory.LINT_BROKEN,
    LabelCategory.LS_BROKEN,
}
# cairo-lint fails on nearly every project and is unreliable, so lint outcomes are tracked
# separately from the "core" build/test/LS outcome.
_LINT_CATEGORIES = {LabelCategory.LINT_FAIL}

MAX_EXCERPTS = 25

type ChangeKind = Literal[
    "regression",
    "fix",
    "changed-failure",
    "still-failing",
    "lint-change",
    "new-project",
    "removed-project",
]


class ProjectChange(BaseModel):
    project: str
    kind: ChangeKind
    labels_target: list[str] = []
    labels_pivot: list[str] = []
    rev_target: str | None = None
    rev_pivot: str | None = None
    tests_target: TestsSummary | None = None
    tests_pivot: TestsSummary | None = None
    error_target: str | None = None
    """Normalised first error line in the target logs."""
    error_pivot: str | None = None
    excerpt: str | None = None
    """Log excerpt from the target (untrusted third-party output)."""
    logs_href: str | None = None
    known_issue: str | None = None
    history: list[str] = []
    """Worst label category in recent earlier reports, oldest first."""

    @property
    def rev_changed(self) -> bool:
        return (
            self.rev_target is not None
            and self.rev_pivot is not None
            and self.rev_target != self.rev_pivot
        )


class RevChange(BaseModel):
    project: str
    pivot: str
    target: str


class Drift(BaseModel):
    added: list[str] = []
    removed: list[str] = []
    rev_changes: list[RevChange] = []
    maat_commits: list[str] = []
    """Ma'at commits between the pivot and target harness (subject lines)."""
    maat_changed: bool = False


class ReportDiff(BaseModel):
    target: str
    pivot: str
    pivot_reason: str
    target_versions: dict[str, str]
    pivot_versions: dict[str, str]
    changes: list[ProjectChange]
    performance: Performance
    drift: Drift
    lint: LintDiff = LintDiff()
    projects_total: int
    projects_clean: int
    """Projects whose worst label is ``test-pass`` in the target."""

    def of_kind(self, *kinds: ChangeKind) -> list[ProjectChange]:
        return [c for c in self.changes if c.kind in kinds]


def diff_reports(
    target: Report,
    target_name: str,
    pivot: Report,
    pivot_name: str,
    pivot_reason: str,
    known_issues: list[KnownIssue],
    history: dict[str, list[str]],
) -> ReportDiff:
    t_tests = target.tests_by_name()
    p_tests = pivot.tests_by_name()
    meta = ReportMeta(name=target_name)

    changes: list[ProjectChange] = []
    for name in sorted(t_tests.keys() | p_tests.keys()):
        t, p = t_tests.get(name), p_tests.get(name)
        change = _classify(t, p)
        if change is None:
            continue
        if t is not None:
            change.logs_href = str(logs_txt_path(meta, t))
            if change.kind in ("regression", "changed-failure", "new-project"):
                change.excerpt = excerpt(t)
            if ki := match_known_issue(known_issues, name, change.labels_target):
                change.known_issue = ki.id
        change.history = history.get(name, [])
        changes.append(change)

    # Bound prompt size: keep excerpts for the first N regressions/changed failures only.
    with_excerpt = [c for c in changes if c.excerpt]
    for c in with_excerpt[MAX_EXCERPTS:]:
        c.excerpt = None

    clean = sum(1 for t in target.tests if not _bad_categories(t))

    return ReportDiff(
        target=target_name,
        pivot=pivot_name,
        pivot_reason=pivot_reason,
        target_versions=_versions(target),
        pivot_versions=_versions(pivot),
        changes=changes,
        performance=compare_performance(target, pivot, known_issues),
        drift=_drift(target, pivot, t_tests, p_tests),
        lint=lint_diff(t_tests, p_tests),
        projects_total=len(target.tests),
        projects_clean=clean,
    )


def _versions(r: Report) -> dict[str, str]:
    return {
        "workspace": r.workspace,
        "scarb": r.scarb,
        "foundry": r.foundry,
        "maat": r.maat_commit[:9],
    }


def _labels(t: TestReport | None) -> list[str]:
    if t is None or t.analyses.labels is None:
        return []
    return [str(lbl) for lbl in t.analyses.labels]


def _bad_categories(t: TestReport) -> set[LabelCategory]:
    if t.analyses.labels is None:
        return set()
    bad = (
        {lbl.category for lbl in t.analyses.labels}
        - _IGNORED_CATEGORIES
        - _LINT_CATEGORIES
    )
    # Lint violations are tracked separately (see `lint.lint_diff`), but a cairo-lint panic is a
    # toolchain crash like any other, so it counts as a real failure.
    if lint_panicked(t):
        bad.add(LabelCategory.LINT_FAIL)
    return bad


def _lint_failed(t: TestReport) -> bool:
    # Labels are `Label` objects, not categories, so compare by category.
    return any(
        lbl.category == LabelCategory.LINT_FAIL for lbl in t.analyses.labels or []
    )


def _core_labels(t: TestReport) -> list[str]:
    return [
        str(lbl)
        for lbl in (t.analyses.labels or [])
        if lbl.category not in _LINT_CATEGORIES
    ]


def worst_category(t: TestReport) -> str:
    """
    The most severe build/test/LS outcome, consistent with how ``_classify`` sees projects.

    ``test-pass`` only wins when nothing else (lint aside) failed: it sorts above ``ls-fail``
    in ``LabelCategory``, so a plain ``min`` would report LS failures as passes.
    """
    if not t.analyses.labels:
        return "none"
    order = list(LabelCategory)
    bad = _bad_categories(t)
    if bad:
        return min(bad, key=order.index).value
    categories = {lbl.category for lbl in t.analyses.labels}
    if LabelCategory.TEST_PASS in categories:
        return LabelCategory.TEST_PASS.value
    return min(categories, key=order.index).value


def _classify(t: TestReport | None, p: TestReport | None) -> ProjectChange | None:
    name = (t or p).name  # type: ignore[union-attr]
    base = dict(
        project=name,
        labels_target=_labels(t),
        labels_pivot=_labels(p),
        rev_target=t.rev if t else None,
        rev_pivot=p.rev if p else None,
        tests_target=t.analyses.tests_summary if t else None,
        tests_pivot=p.analyses.tests_summary if p else None,
        error_target=error_signature(t) if t else None,
        error_pivot=error_signature(p) if p else None,
    )
    if p is None:
        # Newly added projects that pass are plain ecosystem drift (see `Drift.added`).
        if t is not None and _bad_categories(t):
            return ProjectChange(kind="new-project", **base)
        return None
    if t is None:
        return ProjectChange(kind="removed-project", **base)

    bad_t, bad_p = _bad_categories(t), _bad_categories(p)
    if bad_t - bad_p:
        return ProjectChange(kind="regression", **base)
    if bad_p - bad_t:
        # Something got fixed; if something else remained broken it's still mostly a fix.
        return ProjectChange(kind="fix", **base)
    if not bad_t:
        if _lint_failed(t) != _lint_failed(p):
            return ProjectChange(kind="lint-change", **base)
        return None
    if _core_labels(t) != _core_labels(p) or error_set(t) != error_set(p):
        return ProjectChange(kind="changed-failure", **base)
    return ProjectChange(kind="still-failing", **base)


def reconcile(diffs: list["ReportDiff"]) -> None:
    """
    A failure that is unchanged against one pivot is not news against another.

    Example: a project fails the same way on the previous stable release and on this RC,
    but differently on the previous RC (where a harness problem masked the real error).
    The "changed failure" against the previous RC is demoted to "still failing".
    """
    for d in diffs:
        others = [o for o in diffs if o is not d]
        for i, c in enumerate(d.changes):
            if c.kind != "changed-failure":
                continue
            if any(
                oc.project == c.project and oc.kind == "still-failing"
                for o in others
                for oc in o.changes
            ):
                d.changes[i] = c.model_copy(update={"kind": "still-failing"})

    reconcile_lint(diffs)


def _drift(
    target: Report,
    pivot: Report,
    t_tests: dict[str, TestReport],
    p_tests: dict[str, TestReport],
) -> Drift:
    rev_changes = [
        RevChange(project=n, pivot=p_tests[n].rev or "?", target=t_tests[n].rev or "?")
        for n in sorted(t_tests.keys() & p_tests.keys())
        if t_tests[n].rev != p_tests[n].rev
    ]
    maat_changed = target.maat_commit != pivot.maat_commit
    return Drift(
        added=sorted(t_tests.keys() - p_tests.keys()),
        removed=sorted(p_tests.keys() - t_tests.keys()),
        rev_changes=rev_changes,
        maat_changed=maat_changed,
        maat_commits=_maat_log(pivot.maat_commit, target.maat_commit)
        if maat_changed
        else [],
    )


def _maat_log(base: str, head: str, limit: int = 40) -> list[str]:
    try:
        out = subprocess.check_output(
            [
                "git",
                "log",
                "--no-merges",
                "--format=%h %s",
                f"-{limit}",
                f"{base}..{head}",
                "--",
                "src/",
                "workspaces/",
                "maat",
            ],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    # Report merges themselves are noise.
    return [
        line
        for line in out.splitlines()
        if not line.split(" ", 1)[-1].startswith(("experiment:", "gc-reports:"))
    ]
