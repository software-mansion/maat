import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Self

from pydantic import BaseModel

from maat.model import Report, ReportMeta


class Metrics(BaseModel):
    meta: ReportMeta
    workspace: str
    scarb_version: str
    foundry_version: str
    maat_commit: str
    created_at: datetime
    total_execution_time: timedelta
    total_projects: int
    """Total number of projects tested in the experiment."""

    mean_build_time: timedelta
    mean_lint_time: timedelta
    mean_test_time: timedelta
    mean_ls_time: timedelta

    median_build_time: timedelta
    median_lint_time: timedelta
    median_test_time: timedelta
    median_ls_time: timedelta

    @classmethod
    def compute(cls, report: Report, meta: ReportMeta) -> Self:
        times: dict[str, list[timedelta]] = defaultdict(list)

        total_tests = 0
        failed_tests = 0

        for test in report.tests:
            for step_name in ["build", "lint", "test", "ls"]:
                if step := test.step(step_name):
                    if step.exit_code == 0 and step.execution_time:
                        times[step_name].append(step.execution_time)

            if summary := test.analyses.tests_summary:
                total_tests += summary.total
                failed_tests += summary.failed

        mean_build_time = _timedelta_mean(times["build"])
        mean_lint_time = _timedelta_mean(times["lint"])
        mean_test_time = _timedelta_mean(times["test"])
        mean_ls_time = _timedelta_mean(times["ls"])

        median_build_time = _timedelta_median(times["build"])
        median_lint_time = _timedelta_median(times["lint"])
        median_test_time = _timedelta_median(times["test"])
        median_ls_time = _timedelta_median(times["ls"])

        return cls(
            meta=meta,
            workspace=report.workspace,
            scarb_version=report.scarb,
            foundry_version=report.foundry,
            maat_commit=report.maat_commit,
            created_at=report.created_at,
            total_execution_time=report.total_execution_time,
            total_projects=len(report.tests),
            mean_build_time=mean_build_time,
            mean_lint_time=mean_lint_time,
            mean_test_time=mean_test_time,
            mean_ls_time=mean_ls_time,
            median_build_time=median_build_time,
            median_lint_time=median_lint_time,
            median_test_time=median_test_time,
            median_ls_time=median_ls_time,
        )


class MetricsTransposed(BaseModel):
    meta: list[ReportMeta]
    workspace: list[str]
    scarb_version: list[str]
    foundry_version: list[str]
    maat_commit: list[str]
    created_at: list[datetime]
    total_execution_time: list[timedelta]
    total_projects: list[int]
    mean_build_time: list[timedelta]
    mean_lint_time: list[timedelta]
    mean_test_time: list[timedelta]
    mean_ls_time: list[timedelta]
    median_build_time: list[timedelta]
    median_lint_time: list[timedelta]
    median_test_time: list[timedelta]
    median_ls_time: list[timedelta]

    @classmethod
    def new(cls, metrics_list: list[Metrics]) -> Self:
        result = {}
        # noinspection PyUnresolvedReferences
        for k in cls.model_fields.keys():
            result[k] = [getattr(item, k) for item in metrics_list]
        return cls(**result)


# noinspection PyUnresolvedReferences
def _assert_transposed_fields():
    assert Metrics.model_fields.keys() == MetricsTransposed.model_fields.keys(), (
        "Field names do not match."
    )
    for field_name, field_info in Metrics.model_fields.items():
        metric_type = field_info.annotation
        transposed_type = MetricsTransposed.model_fields[field_name].annotation
        assert transposed_type == list[metric_type], (
            f"Type mismatch for field '{field_name}': {metric_type} != {transposed_type}"
        )


_assert_transposed_fields()


def _timedelta_mean(tds: list[timedelta], /) -> timedelta:
    if not tds:
        return timedelta()
    seconds = [td.total_seconds() for td in tds]
    return timedelta(seconds=statistics.mean(seconds))


def _timedelta_median(tds: list[timedelta], /) -> timedelta:
    if not tds:
        return timedelta()
    seconds = [td.total_seconds() for td in tds]
    return timedelta(seconds=statistics.median(seconds))
