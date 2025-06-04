from datetime import datetime, timedelta
from typing import Self

import pydantic
from pydantic import BaseModel

from maat.model import Report, ReportMeta


class Metrics(pydantic.BaseModel):
    meta: ReportMeta
    workspace: str
    scarb_version: str
    foundry_version: str
    maat_commit: str
    created_at: datetime
    total_execution_time: timedelta
    total_projects: int
    """Total number of projects tested in the experiment."""

    avg_build_time: timedelta
    avg_lint_time: timedelta
    avg_test_time: timedelta
    avg_ls_time: timedelta

    @classmethod
    def compute(cls, report: Report, meta: ReportMeta) -> Self:
        # Initialize counters and accumulators.
        build_times = []
        lint_times = []
        test_times = []
        ls_times = []

        total_tests = 0
        failed_tests = 0

        # Process each test and step
        for test in report.tests:
            if step := test.step("build"):
                if step.execution_time:
                    build_times.append(step.execution_time)

            if step := test.step("lint"):
                if step.execution_time:
                    lint_times.append(step.execution_time)

            if step := test.step("test"):
                if step.execution_time:
                    test_times.append(step.execution_time)

            if step := test.step("ls"):
                if step.execution_time:
                    ls_times.append(step.execution_time)

            if summary := test.analyses.tests_summary:
                total_tests += summary.total
                failed_tests += summary.failed

        # Calculate averages
        avg_build_time = sum(build_times, timedelta()) / max(len(build_times), 1)
        avg_lint_time = sum(lint_times, timedelta()) / max(len(lint_times), 1)
        avg_test_time = sum(test_times, timedelta()) / max(len(test_times), 1)
        avg_ls_time = sum(ls_times, timedelta()) / max(len(ls_times), 1)

        # Create and return the Metrics object
        return cls(
            meta=meta,
            workspace=report.workspace,
            scarb_version=report.scarb,
            foundry_version=report.foundry,
            maat_commit=report.maat_commit,
            created_at=report.created_at,
            total_execution_time=report.total_execution_time,
            total_projects=len(report.tests),
            avg_build_time=avg_build_time,
            avg_lint_time=avg_lint_time,
            avg_test_time=avg_test_time,
            avg_ls_time=avg_ls_time,
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
    avg_build_time: list[timedelta]
    avg_lint_time: list[timedelta]
    avg_test_time: list[timedelta]
    avg_ls_time: list[timedelta]

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
