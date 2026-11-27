"""
Paired performance comparison of two reports.

Each project is compared with itself (target / pivot ratio) and only on matching hardware, so
the medians are robust against the ecosystem changing between reports.
"""

import statistics
from datetime import timedelta

from pydantic import BaseModel

from maat.model import Report, TestReport
from maat.triage.known_issues import KnownIssue

# Performance thresholds. Paired comparisons (same project in both reports) on matching
# hardware are fairly stable on the GCP runners, but individual projects still jitter.
AGGREGATE_THRESHOLD = 0.07
"""Relative change of the median paired ratio considered significant."""
PROJECT_RATIO_THRESHOLD = 1.0
"""Per-project change (after normalising by the median shift); heavy projects jitter ~2x."""
PROJECT_ABS_THRESHOLD = timedelta(seconds=30)
PROJECT_MEM_ABS_THRESHOLD_KB = 200 * 1024
MIN_PAIRED_SAMPLES = 10
MAX_OUTLIERS = 5
MAX_TOP = 8
MIN_GROUP_SAMPLES = 5
MIN_SIGNIFICANT_GROUP = 10
GROUP_THRESHOLD = 0.15
"""Median shift within a test-runner group considered significant."""


def fmt_amount(v: float, unit: str) -> str:
    if unit == "KB":
        return f"{v / 1024:,.0f} MB"
    if v >= 120:
        return f"{v / 60:,.1f} min"
    return f"{v:,.1f}s"


class Outlier(BaseModel):
    project: str
    metric: str
    pivot: float
    target: float
    unit: str


class GroupDelta(BaseModel):
    group: str
    """Test runner of the project (``snforge``, ``cairo-test`` or ``unknown``)."""
    samples: int
    median_ratio: float


class MetricDelta(BaseModel):
    metric: str
    unit: str
    samples: int
    median_ratio: float
    """Median over projects of target/pivot; 1.0 means unchanged."""
    p25_ratio: float
    p75_ratio: float
    slower: int
    """Projects more than 20% slower (or larger, for memory)."""
    faster: int
    """Projects more than 20% faster (or smaller)."""
    total_pivot: float
    total_target: float
    significant: bool
    """Overall median moved by more than 7%, or a sizeable runner group moved by more than 15%."""
    groups: list[GroupDelta] = []
    """Breakdown by test runner; populated when there is more than one sizeable group."""
    top: list[Outlier] = []
    """Projects contributing most (in absolute terms) to a significant shift."""


class ExcludedGroup(BaseModel):
    """Projects excluded from performance aggregates by a known issue, shown for transparency."""

    issue: str
    projects: int
    medians: dict[str, float] = {}
    """Metric name -> median target/pivot ratio within the excluded projects."""


class Performance(BaseModel):
    comparable: bool
    reason: str | None = None
    metrics: list[MetricDelta] = []
    outliers: list[Outlier] = []
    excluded: list[ExcludedGroup] = []

    @property
    def regressed(self) -> bool:
        return self.comparable and any(
            m.significant
            and (
                m.median_ratio > 1 + AGGREGATE_THRESHOLD
                or any(
                    g.samples >= MIN_SIGNIFICANT_GROUP
                    and g.median_ratio > 1 + GROUP_THRESHOLD
                    for g in m.groups
                )
            )
            for m in self.metrics
        )


def compare_performance(
    target: Report, pivot: Report, known_issues: list[KnownIssue] = ()
) -> Performance:
    t_cpus = {h.cpu_model for h in target.hardware}
    p_cpus = {h.cpu_model for h in pivot.hardware}
    if not target.hardware or not pivot.hardware:
        return Performance(
            comparable=False, reason="hardware info missing in one of the reports"
        )
    if t_cpus != p_cpus:
        return Performance(
            comparable=False,
            reason=f"different CPUs: {sorted(map(str, p_cpus))} → {sorted(map(str, t_cpus))}",
        )
    if {h.cpu_count for h in target.hardware} != {h.cpu_count for h in pivot.hardware}:
        return Performance(comparable=False, reason="different CPU counts")

    t_tests, p_tests = target.tests_by_name(), pivot.tests_by_name()
    all_pairs = [
        (t_tests[n], p_tests[n]) for n in sorted(t_tests.keys() & p_tests.keys())
    ]
    excluded_by: dict[str, str] = {}
    for t, _ in all_pairs:
        if ki := next((k for k in known_issues if k.covers_performance(t.name)), None):
            excluded_by[t.name] = ki.id
    pairs = [(t, p) for t, p in all_pairs if t.name not in excluded_by]
    excluded_pairs: dict[str, list] = {}
    for t, p in all_pairs:
        if t.name in excluded_by:
            excluded_pairs.setdefault(excluded_by[t.name], []).append((t, p))

    metrics: list[MetricDelta] = []
    outliers: list[Outlier] = []

    def step_time(t: TestReport, step: str) -> float | None:
        s = t.step(step)
        if s and s.exit_code == 0 and s.execution_time:
            return s.execution_time.total_seconds()
        return None

    def analysis_time(attr: str):
        def get(t: TestReport, _: str) -> float | None:
            v = getattr(t.analyses, attr)
            return v.total_seconds() if v else None

        return get

    def mem(t: TestReport, _: str) -> float | None:
        v = t.analyses.ls_mem_post_analysis_peak_kb
        return float(v) if v else None

    series = [
        ("build time", "build", step_time, "s"),
        ("test time", "test", step_time, "s"),
        ("lint time", "lint", step_time, "s"),
        ("CairoLS analysis time", "ls", step_time, "s"),
        ("cold build", "", analysis_time("cold_build_time"), "s"),
        ("incremental build", "", analysis_time("incremental_build_time"), "s"),
        ("CairoLS peak memory", "", mem, "KB"),
    ]

    for metric, step, getter, unit in series:
        ratios = []
        candidates = []
        by_group: dict[str, list[float]] = {}
        for t, p in pairs:
            vt, vp = getter(t, step), getter(p, step)
            if not vt or not vp:
                continue
            ratios.append(vt / vp)
            candidates.append((t.name, vp, vt))
            by_group.setdefault(t.analyses.test_runner or "unknown", []).append(vt / vp)
        if len(ratios) < MIN_PAIRED_SAMPLES:
            continue
        med = statistics.median(ratios)
        q = statistics.quantiles(ratios, n=4)
        groups = [
            GroupDelta(
                group=g, samples=len(v), median_ratio=round(statistics.median(v), 3)
            )
            for g, v in sorted(by_group.items(), key=lambda kv: -len(kv[1]))
            if len(v) >= MIN_GROUP_SAMPLES
        ]
        if len(groups) < 2:
            groups = []

        # A metric is significant if the overall median moved, or if a sizeable group of
        # projects moved (two populations shifting in opposite directions can cancel out in
        # the overall median, e.g. snforge slower and cairo-test faster).
        shifted_groups = [
            g
            for g in groups
            if g.samples >= MIN_SIGNIFICANT_GROUP
            and abs(g.median_ratio - 1) > GROUP_THRESHOLD
        ]
        significant = abs(med - 1) > AGGREGATE_THRESHOLD or bool(shifted_groups)
        if abs(med - 1) > AGGREGATE_THRESHOLD:
            lead = med
        elif shifted_groups:
            lead = max(
                shifted_groups, key=lambda g: abs(g.median_ratio - 1)
            ).median_ratio
        else:
            lead = 1.0

        top: list[Outlier] = []
        if significant:
            direction = 1 if lead > 1 else -1
            ranked = sorted(candidates, key=lambda c: -direction * (c[2] - c[1]))
            top = [
                Outlier(
                    project=n,
                    metric=metric,
                    pivot=round(vp, 1),
                    target=round(vt, 1),
                    unit=unit,
                )
                for n, vp, vt in ranked[:MAX_TOP]
                if direction * (vt - vp) > 0
            ]

        metrics.append(
            MetricDelta(
                metric=metric,
                unit=unit,
                samples=len(ratios),
                median_ratio=round(med, 3),
                p25_ratio=round(q[0], 3),
                p75_ratio=round(q[2], 3),
                slower=sum(r > 1.2 for r in ratios),
                faster=sum(r < 1 / 1.2 for r in ratios),
                total_pivot=round(sum(c[1] for c in candidates), 1),
                total_target=round(sum(c[2] for c in candidates), 1),
                significant=significant,
                groups=groups,
                top=top,
            )
        )
        abs_threshold = (
            PROJECT_MEM_ABS_THRESHOLD_KB
            if unit == "KB"
            else PROJECT_ABS_THRESHOLD.total_seconds()
        )
        for name, vp, vt in candidates:
            # Normalise by the aggregate shift so a global slowdown doesn't flag everyone.
            rel = vt / (vp * med) - 1
            if abs(rel) > PROJECT_RATIO_THRESHOLD and abs(vt - vp) > abs_threshold:
                outliers.append(
                    Outlier(
                        project=name,
                        metric=metric,
                        pivot=round(vp, 1),
                        target=round(vt, 1),
                        unit=unit,
                    )
                )

    outliers.sort(key=lambda o: -abs(o.target - o.pivot) / max(o.pivot, 1e-9))

    excluded: list[ExcludedGroup] = []
    for issue_id, ps in excluded_pairs.items():
        medians = {}
        for metric, step, getter, _ in series:
            r = [
                vt / vp
                for t, p in ps
                if (vt := getter(t, step)) and (vp := getter(p, step))
            ]
            if len(r) >= MIN_GROUP_SAMPLES:
                medians[metric] = round(statistics.median(r), 3)
        excluded.append(
            ExcludedGroup(issue=issue_id, projects=len(ps), medians=medians)
        )

    return Performance(
        comparable=True,
        metrics=metrics,
        outliers=outliers[:MAX_OUTLIERS],
        excluded=excluded,
    )
