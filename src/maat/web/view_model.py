from pathlib import Path
from typing import NamedTuple

from collections import defaultdict
from collections.abc import Iterable, Callable, Iterator

from pydantic import BaseModel, Field

from maat.model import Label, LabelCategory, Report, ReportMeta, TestReport
from maat.report.metrics import Metrics, MetricsTransposed
from maat.utils.smart_sort import smart_sort_key


class ReportNameViewModel(BaseModel):
    title: str
    pivot_href: str
    is_reference: bool = False


class TestCellViewModel(BaseModel):
    missing: bool = False
    label: Label
    logs_href: str
    rev: str | None = None


class MissingTestCellViewModel(BaseModel):
    missing: bool = True
    logs_href: str | None = None
    rev: str | None = None


class LabelGroupRowViewModel(BaseModel):
    project: str
    cells: list[TestCellViewModel | MissingTestCellViewModel]

    @property
    def uniform_rev(self) -> str | None:
        """
        Returns rev string shared by all cells in this row, or None if they differ,
        or none of the cells has rev.
        """

        expected: str | None = None
        for cell in self.cells:
            if cell.rev is None:
                continue
            if expected is None:
                expected = cell.rev
            elif cell.rev != expected:
                return None
        return expected


class LabelGroupViewModel(BaseModel):
    category: LabelCategory
    rows: list[LabelGroupRowViewModel]
    count: int
    ratio: float


class ReportInfo(NamedTuple):
    report: Report
    meta: ReportMeta
    metrics: Metrics


class Slice(BaseModel):
    title: str
    reports: list[ReportInfo] = Field(min_length=1)
    default: bool = False


class SliceViewModel(BaseModel):
    title: str
    href: str
    is_current: bool = False


class RootViewModel(BaseModel):
    report_names: list[ReportNameViewModel]
    metrics: MetricsTransposed
    label_groups: list[LabelGroupViewModel]
    slices: list[SliceViewModel]


def build_view_model(
    reports: list[ReportInfo],
    reference_report_idx: int,
    slices: list[Slice],
    curr_slice_idx: int,
) -> RootViewModel:
    metrics_transposed = MetricsTransposed.new([metrics for _, _, metrics in reports])

    report_names = [
        ReportNameViewModel(
            title=report.meta.name,
            pivot_href=_get_href(
                slice_name=slices[curr_slice_idx].title,
                index=i,
                is_default=(slices[curr_slice_idx].default and i == len(reports) - 1),
            ),
        )
        for i, report in enumerate(reports)
    ]
    report_names[reference_report_idx].is_reference = True

    slices_view = [
        SliceViewModel(
            title=slice.title,
            href=_get_href(
                slice_name=slices[i].title,
                index=(len(slices[i].reports) - 1),
                is_default=slices[i].default,
            ),
        )
        for i, slice in enumerate(slices)
    ]
    slices_view[curr_slice_idx].is_current = True

    reference_report, _, reference_metrics = reports[reference_report_idx]

    label_groups = []
    for category in LabelCategory:
        relevant_test_names = list(
            test.name
            for test in reference_report.tests
            if category in test.analyses.labels
        )
        relevant_test_names.sort(key=smart_sort_key)

        tests_by_report_idx_and_name: dict[tuple[int, str], TestReport] = {
            (report_idx, test.name): test
            for report_idx, (report, _, _) in enumerate(reports)
            for test in report.tests
        }

        rows = []
        for test_name in relevant_test_names:
            cells = []
            for report_idx, (_, report_meta, _) in enumerate(reports):
                if test := tests_by_report_idx_and_name.get((report_idx, test_name)):
                    logs_href = str(logs_txt_path(report_meta, test))

                    if label := test.analyses.labels.prioritize(category)[0]:
                        cell = TestCellViewModel(
                            label=label,
                            logs_href=logs_href,
                            rev=test.rev,
                        )
                    else:
                        cell = MissingTestCellViewModel(
                            logs_href=logs_href,
                            rev=test.rev,
                        )
                else:
                    cell = MissingTestCellViewModel()

                cells.append(cell)

            rows.append(LabelGroupRowViewModel(project=test_name, cells=cells))

        if rows:
            ratio = len(rows) / reference_metrics.total_projects

            label_groups.append(
                LabelGroupViewModel(
                    category=category,
                    rows=rows,
                    count=len(rows),
                    ratio=ratio,
                )
            )

    return RootViewModel(
        report_names=report_names,
        metrics=metrics_transposed,
        label_groups=label_groups,
        slices=slices_view,
    )


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    return Path() / meta.name / test.name_and_rev / "logs.txt"


def make_slices(reports: list[ReportInfo]) -> list[Slice]:
    slices = []

    def push_slice(title: str, reps: list[ReportInfo], default: bool = False):
        if reps:
            sl = Slice(title=title, reports=reps, default=default)
            slices.append(sl)

    latest_nightly = [t for t in reports if t.meta.name == "nightly-latest"]

    all_stable = [
        t
        for t in reports
        if t.report.workspace == "release"
        if t.report.used_stable_tooling
    ]

    latest_stable_by_scarb = max(
        all_stable,
        default=None,
        key=lambda t: t.report.by_version_preferring_scarb,
    )

    latest_stable_by_foundry = max(
        all_stable,
        default=None,
        key=lambda t: t.report.by_version_preferring_foundry,
    )

    # If there is one report with both the highest scarb and highest foundry version,
    # then this will be one item. Otherwise, this will be a pair.
    latest_stable: list[ReportInfo] = []
    if latest_stable_by_scarb:
        latest_stable.append(latest_stable_by_scarb)

        if (
            latest_stable_by_foundry
            and latest_stable_by_foundry != latest_stable_by_scarb
        ):
            latest_stable.append(latest_stable_by_foundry)

    # Nightly vs (Latest) Stable
    if latest_nightly and latest_stable:
        push_slice("Nightly vs Stable", [*latest_nightly, *latest_stable], default=True)

    # Last N(<=3) Scarbs
    last_n_scarbs = list(
        unique_by(
            # Deduplicate same-scarb-different-foundry runs.
            lambda t: t.report.scarb,
            sorted(
                all_stable,
                key=lambda t: t.report.by_version_preferring_scarb,
            ),
        )
    )[:3]
    push_slice(f"Last {len(last_n_scarbs)} Scarbs", last_n_scarbs)

    # Last N(<=3) Foundries. Foundry targets 3 last stable Scarb versions, so we add all of them.
    last_n_foundries = list(
        unique_by_at_most(
            3,
            lambda t: t.report.foundry,
            sorted(
                all_stable,
                key=lambda t: t.report.by_version_preferring_foundry,
            ),
        )
    )

    push_slice(
        f"Last {len({x.report.foundry for x in last_n_foundries})} Foundries",
        last_n_foundries,
    )

    # Finally, the "All" slice.
    push_slice("All", reports)

    return slices


def unique_by[T, K](key: Callable[[T], K], iterable: Iterable[T]) -> Iterator[T]:
    seen = set()
    for item in iterable:
        k = key(item)
        if k not in seen:
            seen.add(k)
            yield item


def unique_by_at_most[T, K](
    n: int, key: Callable[[T], K], iterable: Iterable[T]
) -> Iterator[T]:
    seen = defaultdict(int)
    for item in iterable:
        k = key(item)
        seen[k] += 1
        if seen[k] <= n:
            yield item


# NOTE: The last report for default slice will be the reference,
# and thus it will be rendered as index.html.
def _get_href(slice_name: str, index: int, is_default: bool) -> str:
    return (
        f"{_slugify(slice_name)}-pivot-{index}.html" if not is_default else "index.html"
    )


def _slugify(text: str) -> str:
    return text.lower().replace(" ", "-")
