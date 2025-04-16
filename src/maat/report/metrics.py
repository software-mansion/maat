from datetime import datetime, timedelta
from pathlib import Path
from typing import Self

import pydantic
from pydantic import BaseModel

from maat.model import ClassifiedDiagnostic, Report


class Metrics(pydantic.BaseModel):
    file_stem: str
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

    failed_tests_ratio: float
    """N failed tests / N tests"""

    @classmethod
    def compute(cls, report: Report, path: Path) -> Self:
        # Initialize counters and accumulators.
        build_times = []
        lint_times = []
        test_times = []

        total_tests = 0
        failed_tests = 0

        # Process each test and step
        for test in report.tests:
            if (step := test.step("build")) is not None:
                if step.execution_time:
                    build_times.append(step.execution_time)

            if (step := test.step("lint")) is not None:
                if step.execution_time:
                    lint_times.append(step.execution_time)

            if (step := test.step("test")) is not None:
                if step.execution_time:
                    test_times.append(step.execution_time)

                if step.analyses.tests_summary:
                    summary = step.analyses.tests_summary
                    total_tests += summary.total
                    failed_tests += summary.failed

        # Calculate averages
        avg_build_time = sum(build_times, timedelta()) / max(len(build_times), 1)
        avg_lint_time = sum(lint_times, timedelta()) / max(len(lint_times), 1)
        avg_test_time = sum(test_times, timedelta()) / max(len(test_times), 1)

        # Calculate the failed test ratio.
        failed_tests_ratio = (
            failed_tests / max(total_tests, 1) if total_tests > 0 else 0.0
        )

        # Create and return the Metrics object
        return cls(
            file_stem=path.stem,
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
            failed_tests_ratio=failed_tests_ratio,
        )


def _classified_diagnostics_sort_key(d: ClassifiedDiagnostic) -> tuple:
    """
    Returns a key that can be used to sort diagnostics in the following order:
    1. Higher count first (descending order).
    2. Severity, where "error" is higher than "warn".
    3. Alphabetically by diagnostic message.
    """
    severity_priority = {"error": 1, "warn": 2}
    return -d.count, severity_priority[d.severity], d.message


class MetricsTransposed(BaseModel):
    file_stem: list[str]
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
    failed_tests_ratio: list[float]

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
