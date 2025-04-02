from datetime import timedelta, datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel

from maat.model import Report, Severity


class Metrics(BaseModel):
    file_stem: str
    workspace: str
    scarb_version: str
    foundry_version: str
    maat_commit: str
    created_at: datetime
    total_execution_time: timedelta

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

    build_diagnostics: list[tuple[Severity, str, int]]
    """List of all build diagnostics from all build runs."""
    lint_diagnostics: list[tuple[Severity, str, int]]
    """List of all lint diagnostics (lint-specific, no build ones) from all linter runs."""

    failed_tests_ratio: float
    """N failed tests / N tests"""

    compiled_procmacros_from_source: list[str]
    """List of proc macro package IDs that were compiled from source."""

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

        build_diagnostics = []
        lint_diagnostics = []

        total_tests = 0
        failed_tests = 0

        compiled_procmacros = []

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

                            # Add diagnostics to the list
                            for (
                                severity,
                                message,
                                count,
                            ) in diag.diagnostics_by_message_and_severity:
                                build_diagnostics.append((severity, message, count))
                        else:
                            clean_builds += 1

                    if step.analyses.compiled_procmacros_from_source:
                        compiled_procmacros.extend(
                            step.analyses.compiled_procmacros_from_source.package_ids
                        )

                # Process lint steps
                elif step.name == "lint":
                    if step.execution_time:
                        lint_times.append(step.execution_time)

                    if step.analyses.classify_diagnostics:
                        diag = step.analyses.classify_diagnostics
                        if diag.total > 0:
                            dirty_lints += 1

                            # Add diagnostics to the list
                            for (
                                severity,
                                message,
                                count,
                            ) in diag.diagnostics_by_message_and_severity:
                                lint_diagnostics.append((severity, message, count))
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

        # Remove duplicates from compiled_procmacros
        compiled_procmacros = sorted(set(compiled_procmacros))

        # Create and return the Metrics object
        return cls(
            file_stem=path.stem,
            workspace=report.workspace,
            scarb_version=report.scarb,
            foundry_version=report.foundry,
            maat_commit=report.maat_commit,
            created_at=report.created_at,
            total_execution_time=report.total_execution_time,
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
