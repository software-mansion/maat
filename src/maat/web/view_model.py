from pathlib import Path

from pydantic import BaseModel

from maat.model import Label, LabelCategory, ReportMeta, TestReport
from maat.report.metrics import MetricsTransposed
from maat.report.timings import FullTimings, collect_timings
from maat.report.trends import Trend, trends_row, trends_row_with_optionals
from maat.utils.slugify import slugify
from maat.utils.smart_sort import smart_sort_key
from maat.web.report_info import ReportInfo
from maat.web.slices import Slice


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


class SliceViewModel(BaseModel):
    title: str
    href: str
    is_current: bool = False


class MetricsTrendsViewModel(BaseModel):
    total_execution_time: list[Trend]
    mean_build_time: list[Trend | None]
    mean_lint_time: list[Trend | None]
    mean_test_time: list[Trend | None]
    mean_ls_time: list[Trend | None]
    median_build_time: list[Trend | None]
    median_lint_time: list[Trend | None]
    median_test_time: list[Trend | None]
    median_ls_time: list[Trend | None]


class RootViewModel(BaseModel):
    report_names: list[ReportNameViewModel]
    metrics: MetricsTransposed
    metrics_trends: MetricsTrendsViewModel
    label_groups: list[LabelGroupViewModel]
    slices: list[SliceViewModel]
    reference_report_idx: int
    full_timings: FullTimings


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
            title=sl.title,
            href=_get_href(
                slice_name=slices[i].title,
                index=(len(slices[i].reports) - 1),
                is_default=slices[i].default,
            ),
        )
        for i, sl in enumerate(slices)
    ]
    slices_view[curr_slice_idx].is_current = True
    assert sum(sv.is_current for sv in slices_view) == 1, (
        "only one slice can be the default"
    )

    metrics_trends = MetricsTrendsViewModel(
        total_execution_time=trends_row(
            metrics_transposed.total_execution_time, reference_report_idx
        ),
        mean_build_time=trends_row_with_optionals(
            metrics_transposed.mean_build_time, reference_report_idx
        ),
        mean_lint_time=trends_row_with_optionals(
            metrics_transposed.mean_lint_time, reference_report_idx
        ),
        mean_test_time=trends_row_with_optionals(
            metrics_transposed.mean_test_time, reference_report_idx
        ),
        mean_ls_time=trends_row_with_optionals(metrics_transposed.mean_ls_time, reference_report_idx),
        median_build_time=trends_row_with_optionals(
            metrics_transposed.median_build_time, reference_report_idx
        ),
        median_lint_time=trends_row_with_optionals(
            metrics_transposed.median_lint_time, reference_report_idx
        ),
        median_test_time=trends_row_with_optionals(
            metrics_transposed.median_test_time, reference_report_idx
        ),
        median_ls_time=trends_row_with_optionals(metrics_transposed.median_ls_time, reference_report_idx),
    )

    full_timings = collect_timings(reports, reference_report_idx)

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
        metrics_trends=metrics_trends,
        label_groups=label_groups,
        slices=slices_view,
        reference_report_idx=reference_report_idx,
        full_timings=full_timings,
    )


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    return Path() / meta.name / test.name_and_rev / "logs.txt"


# NOTE: The last report for the default slice will be the reference,
# and thus it will be rendered as index.html.
def _get_href(slice_name: str, index: int, is_default: bool) -> str:
    return (
        f"{slugify(slice_name)}-pivot-{index}.html" if not is_default else "index.html"
    )
