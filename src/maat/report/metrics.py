from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Self

import pydantic
from pydantic import BaseModel

from maat.model import ClassifiedDiagnostic, Report, Severity


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

    clean_builds: int
    """Total number of clean builds."""
    clean_lints: int
    """Total number of clean linter runs."""
    clean_tests: int
    """Total number of test runs where all tests passed or were skipped or filtered out."""
    dirty_builds: int
    """Total number of build runs that produced warnings or errors."""
    dirty_lints: int
    """Total number of linter runs that produced warnings or errors."""
    dirty_tests: int
    """Total number of test runs where some tests have failed)."""

    avg_warnings_in_dirty_build: float
    avg_errors_in_dirty_build: float

    build_diagnostics: list[ClassifiedDiagnostic]
    """List of all build diagnostics from all build runs."""
    lint_diagnostics: list[ClassifiedDiagnostic]
    """List of all lint diagnostics (lint-specific, no build ones) from all linter runs."""

    failed_tests_ratio: float
    """N failed tests / N tests"""

    compiled_procmacros_from_source: dict[str, int]
    """Package ID->Total Count dict of proc macros that were compiled from source."""

    @classmethod
    def compute(cls, report: Report, path: Path) -> Self:
        # Initialize counters and accumulators.
        build_times = []
        lint_times = []
        test_times = []

        clean_builds = 0
        clean_lints = 0
        clean_tests = 0
        dirty_builds = 0
        dirty_lints = 0
        dirty_tests = 0

        warnings_in_dirty_build = []
        errors_in_dirty_build = []

        build_diagnostics_set = ClassifiedDiagnosticsSet()
        lint_diagnostics_set = ClassifiedDiagnosticsSet()

        total_tests = 0
        failed_tests = 0

        compiled_procmacros = defaultdict(int)

        # Process each test and step
        for test in report.tests:
            for step in test.steps:
                # Process build steps
                if step.name == "build":
                    if step.execution_time:
                        build_times.append(step.execution_time)

                    if step.analyses.classify_diagnostics:
                        diag = step.analyses.classify_diagnostics
                        if diag.total > 0:
                            dirty_builds += 1
                            warnings_in_dirty_build.append(diag.warnings)
                            errors_in_dirty_build.append(diag.errors)

                            build_diagnostics_set.extend(
                                diag.diagnostics_by_message_and_severity
                            )
                        else:
                            clean_builds += 1

                    if step.analyses.compiled_procmacros_from_source:
                        for (
                            package_id
                        ) in step.analyses.compiled_procmacros_from_source.package_ids:
                            compiled_procmacros[package_id] += 1

                # Process lint steps
                elif step.name == "lint":
                    if step.execution_time:
                        lint_times.append(step.execution_time)

                    if step.analyses.classify_diagnostics:
                        diag = step.analyses.classify_diagnostics
                        if diag.total > 0:
                            dirty_lints += 1

                            lint_diagnostics_set.extend(
                                diag.diagnostics_by_message_and_severity
                            )
                        else:
                            clean_lints += 1

                # Process test steps
                elif step.name == "test":
                    if step.execution_time:
                        test_times.append(step.execution_time)

                    if step.analyses.tests_summary:
                        summary = step.analyses.tests_summary
                        total_tests += summary.total
                        failed_tests += summary.failed

                        if summary.failed > 0:
                            dirty_tests += 1
                        else:
                            clean_tests += 1

        # Calculate averages
        avg_build_time = sum(build_times, timedelta()) / max(len(build_times), 1)
        avg_lint_time = sum(lint_times, timedelta()) / max(len(lint_times), 1)
        avg_test_time = sum(test_times, timedelta()) / max(len(test_times), 1)

        # Calculate average warnings and errors in dirty builds
        avg_warnings = (
            sum(warnings_in_dirty_build) / max(len(warnings_in_dirty_build), 1)
            if warnings_in_dirty_build
            else 0.0
        )
        avg_errors = (
            sum(errors_in_dirty_build) / max(len(errors_in_dirty_build), 1)
            if errors_in_dirty_build
            else 0.0
        )

        # Calculate the failed test ratio.
        failed_tests_ratio = (
            failed_tests / max(total_tests, 1) if total_tests > 0 else 0.0
        )

        # Reorder compiled_procmacros in the dictionary.
        compiled_procmacros = dict(
            sorted(compiled_procmacros.items(), key=lambda x: (-x[1], x[0]))
        )

        # Sort diagnostics.
        build_diagnostics = list(build_diagnostics_set)
        build_diagnostics.sort(key=_classified_diagnostics_sort_key)
        lint_diagnostics = list(lint_diagnostics_set)
        lint_diagnostics.sort(key=_classified_diagnostics_sort_key)

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
            clean_builds=clean_builds,
            clean_lints=clean_lints,
            clean_tests=clean_tests,
            dirty_builds=dirty_builds,
            dirty_lints=dirty_lints,
            dirty_tests=dirty_tests,
            avg_warnings_in_dirty_build=avg_warnings,
            avg_errors_in_dirty_build=avg_errors,
            build_diagnostics=build_diagnostics,
            lint_diagnostics=lint_diagnostics,
            failed_tests_ratio=failed_tests_ratio,
            compiled_procmacros_from_source=compiled_procmacros,
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
    clean_builds: list[int]
    clean_lints: list[int]
    clean_tests: list[int]
    dirty_builds: list[int]
    dirty_lints: list[int]
    dirty_tests: list[int]
    avg_warnings_in_dirty_build: list[float]
    avg_errors_in_dirty_build: list[float]
    build_diagnostics: list[list[ClassifiedDiagnostic]]
    lint_diagnostics: list[list[ClassifiedDiagnostic]]
    failed_tests_ratio: list[float]
    compiled_procmacros_from_source: list[dict[str, int]]

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


class ClassifiedDiagnosticsSet:
    def __init__(self):
        self._data: dict[(Severity, str), int] = defaultdict(int)

    def add(self, diag: ClassifiedDiagnostic):
        self._data[(diag.severity, diag.message)] += diag.count

    def extend(self, other: Iterable[ClassifiedDiagnostic]):
        for diag in other:
            self.add(diag)

    def __iter__(self):
        for (severity, message), count in self._data.items():
            yield ClassifiedDiagnostic(severity=severity, message=message, count=count)
