"""
Per-kind comparison of cairo-lint diagnostics.

On projects at the same rev, cairo-lint output is deterministic: between reports with the same
toolchain it practically never changes, so any shift comes from the toolchain (cairo-lint rules
or the compiler) and may be intended or a regression.
"""

import re
from collections import Counter
from typing import TYPE_CHECKING

from pydantic import BaseModel

from maat.model import TestReport
from maat.triage.logs import lint_panicked, normalise

if TYPE_CHECKING:
    from maat.triage.diff import ReportDiff

LINT_KIND_MIN_PROJECTS = 2
"""A lint kind is significant if it changed in at least this many projects..."""
LINT_KIND_MIN_DELTA = 5
"""...or its total count changed by at least this much."""
MAX_LINT_KINDS = 20
MAX_LINT_EXAMPLES = 5


class LintKindDelta(BaseModel):
    id: str
    """Short stable reference (``L1``, ``L2``, ...) used by the LLM to say which kinds it explains."""
    kind: str
    """Diagnostic code and normalised message, e.g. ``E2200: Redundant conversion: ...``."""
    pivot_count: int
    target_count: int
    pivot_projects: int
    target_projects: int
    changed_projects: list[str]
    """Projects where this kind's count changed (truncated to a few examples)."""
    changed_projects_total: int
    significant: bool


class LintDiff(BaseModel):
    """Per-kind change of lint diagnostics, on projects at the same rev in both reports."""

    compared_projects: int = 0
    changed_projects: int = 0
    kinds: list[LintKindDelta] = []
    """Kinds whose count changed, most significant first (truncated)."""
    kinds_total: int = 0
    """Number of kinds whose count changed, before truncation."""

    @property
    def significant(self) -> bool:
        return any(k.significant for k in self.kinds)

    def significant_kinds(self) -> list[LintKindDelta]:
        return [k for k in self.kinds if k.significant]


_LINT_DIAG_RE = re.compile(
    r"^\[(?:out|err)] (?:warn|error)\[(E\d+)]: (?:Plugin diagnostic: )?(.+)$", re.M
)


def lint_profile(t: TestReport) -> Counter[str] | None:
    """Diagnostic counts per kind in the lint step, or None if lint didn't run (or panicked)."""
    step = t.step("lint")
    if step is None or not step.was_executed or step.log is None or lint_panicked(t):
        return None
    return Counter(
        f"{m.group(1)}: {normalise(m.group(2))}"
        for m in _LINT_DIAG_RE.finditer(step.log_str)
    )


def lint_diff(
    t_tests: dict[str, TestReport], p_tests: dict[str, TestReport]
) -> LintDiff:
    # Only projects at the same rev: a changed project legitimately changes its diagnostics.
    same_rev = sorted(
        n for n in t_tests.keys() & p_tests.keys() if t_tests[n].rev == p_tests[n].rev
    )
    totals: dict[
        str, list[int]
    ] = {}  # kind -> [pivot count, target count, pivot projects, target projects]
    changed_in: dict[str, list[str]] = {}
    compared = changed = 0
    for name in same_rev:
        pt, pp = lint_profile(t_tests[name]), lint_profile(p_tests[name])
        if pt is None or pp is None:
            continue
        compared += 1
        changed += pt != pp
        for kind in pt.keys() | pp.keys():
            v = totals.setdefault(kind, [0, 0, 0, 0])
            v[0] += pp[kind]
            v[1] += pt[kind]
            v[2] += kind in pp
            v[3] += kind in pt
            if pp[kind] != pt[kind]:
                changed_in.setdefault(kind, []).append(name)

    deltas = []
    for kind, projects in changed_in.items():
        pc, tc, pp_, tp = totals[kind]
        deltas.append(
            LintKindDelta(
                id="",
                kind=kind,
                pivot_count=pc,
                target_count=tc,
                pivot_projects=pp_,
                target_projects=tp,
                changed_projects=projects[:MAX_LINT_EXAMPLES],
                changed_projects_total=len(projects),
                significant=len(projects) >= LINT_KIND_MIN_PROJECTS
                or abs(tc - pc) >= LINT_KIND_MIN_DELTA,
            )
        )
    deltas.sort(
        key=lambda d: (
            not d.significant,
            -d.changed_projects_total,
            -abs(d.target_count - d.pivot_count),
            d.kind,
        )
    )
    for i, d in enumerate(deltas, 1):
        d.id = f"L{i}"
    return LintDiff(
        compared_projects=compared,
        changed_projects=changed,
        kinds=deltas[:MAX_LINT_KINDS],
        kinds_total=len(deltas),
    )


def reconcile_lint(diffs: "list[ReportDiff]") -> None:
    """
    A diagnostic whose count is unchanged against another pivot (for every affected project,
    compared at the same rev there) is not news. See ``diff.reconcile``.
    """
    for d in diffs:
        others = [o for o in diffs if o is not d]

        def unchanged_in(o: "ReportDiff", k: LintKindDelta) -> bool:
            if len(o.lint.kinds) < o.lint.kinds_total:
                return False  # truncated: absence proves nothing
            if any(ok.kind == k.kind for ok in o.lint.kinds):
                return False
            not_compared = set(o.drift.added) | {r.project for r in o.drift.rev_changes}
            return not not_compared & set(k.changed_projects)

        kept = [
            k
            for k in d.lint.kinds
            if k.changed_projects_total > len(k.changed_projects)
            or not any(unchanged_in(o, k) for o in others)
        ]
        d.lint.kinds_total -= len(d.lint.kinds) - len(kept)
        d.lint.kinds = kept
