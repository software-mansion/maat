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

    mean_build_time: timedelta | None
    mean_lint_time: timedelta | None
    mean_test_time: timedelta | None
    mean_ls_time: timedelta | None

    median_build_time: timedelta | None
    median_lint_time: timedelta | None
    median_test_time: timedelta | None
    median_ls_time: timedelta | None

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


def _timedelta_mean(tds: list[timedelta], /) -> timedelta | None:
    if not tds:
        return None
    seconds = [td.total_seconds() for td in tds]
    return timedelta(seconds=statistics.mean(seconds))


def _timedelta_median(tds: list[timedelta], /) -> timedelta | None:
    if not tds:
        return None
    seconds = [td.total_seconds() for td in tds]
    return timedelta(seconds=statistics.median(seconds))
