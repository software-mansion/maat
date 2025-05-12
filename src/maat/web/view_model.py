from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel

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


class RootViewModel(BaseModel):
    report_names: list[ReportNameViewModel]
    metrics: MetricsTransposed
    label_groups: list[LabelGroupViewModel]


class ReportInfo(NamedTuple):
    report: Report
    meta: ReportMeta
    metrics: Metrics
    pivot_path: str


def build_view_model(
    reports: list[ReportInfo],
    reference_report_idx: int,
) -> RootViewModel:
    metrics_transposed = MetricsTransposed.new(
        [metrics for _, _, metrics, _ in reports]
    )

    report_names = [
        ReportNameViewModel(
            title=meta.name,
            pivot_href=pivot_path,
        )
        for _, meta, _, pivot_path in reports
    ]
    report_names[reference_report_idx].is_reference = True

    reference_report, _, reference_metrics, _ = reports[reference_report_idx]

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
            for report_idx, (report, _, _, _) in enumerate(reports)
            for test in report.tests
        }

        rows = []
        for test_name in relevant_test_names:
            cells = []
            for report_idx, (_, report_meta, _, _) in enumerate(reports):
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
    )


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    return Path() / meta.name / test.name_and_rev / "logs.txt"
