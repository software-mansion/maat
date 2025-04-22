from pathlib import Path

from pydantic import BaseModel

from maat.model import LabelCategory, Report, ReportMeta, TestReport
from maat.report.metrics import Metrics, MetricsTransposed
from maat.utils.smart_sort import smart_sort_key


class ReportNameViewModel(BaseModel):
    title: str
    is_reference: bool = False


class TestCellViewModel(BaseModel):
    missing: bool = False
    label: str
    logs_href: str


class MissingTestCellViewModel(BaseModel):
    missing: bool = True


class LabelGroupRowViewModel(BaseModel):
    project: str
    cells: list[TestCellViewModel | MissingTestCellViewModel]


class LabelGroupViewModel(BaseModel):
    category: LabelCategory
    rows: list[LabelGroupRowViewModel]
    count: int
    ratio: float


class RootViewModel(BaseModel):
    report_names: list[ReportNameViewModel]
    metrics: MetricsTransposed
    label_groups: list[LabelGroupViewModel]


def build_view_model(
    reports: list[tuple[Report, ReportMeta, Metrics]],
) -> RootViewModel:
    reports.sort(key=_reports_sorting_key)

    metrics_transposed = MetricsTransposed.new([metrics for _, _, metrics in reports])

    report_names = [ReportNameViewModel(title=m.name) for m in metrics_transposed.meta]
    report_names[-1].is_reference = True

    reference_metrics = reports[-1][2]

    label_groups = []
    for category in LabelCategory:
        tests_with_category: list[list[TestReport]] = [
            report.tests_with_label_category(category) for report, _, _ in reports
        ]
        assert len(tests_with_category) == len(reports)

        unique_test_names = list(
            sorted(
                set(test.name for test in tests_with_category[-1]),
                key=smart_sort_key,
            )
        )

        tests_indexed_by_report_and_name: dict[tuple[int, str], TestReport] = {
            (report_idx, test.name): test
            for report_idx, tests in enumerate(tests_with_category)
            for test in tests
        }

        rows = []
        for test_name in unique_test_names:
            cells = []
            for report_idx, (_, report_meta, _) in enumerate(reports):
                if test := tests_indexed_by_report_and_name.get(
                    (report_idx, test_name)
                ):
                    label = test.analyses.label_by_category(category)
                    assert label is not None
                    logs_href = str(logs_txt_path(report_meta, test))
                    cell = TestCellViewModel(
                        label=label.comment or label.category,
                        logs_href=logs_href,
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
    )


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    return Path() / meta.name / test.name_and_rev / "logs.txt"


def _reports_sorting_key(report_tuple: tuple[Report, ReportMeta, Metrics]) -> list:
    _, _, metrics = report_tuple
    return smart_sort_key(metrics.meta.name)
