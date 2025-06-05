import statistics
from datetime import timedelta
from itertools import islice

from pydantic import BaseModel

from maat.model import TestReport
from maat.report.trends import Trend, trends_row_with_optionals
from maat.web import ReportInfo


class ProjectTimings(BaseModel):
    values: list[timedelta | None]
    trends: list[Trend | None]

    def variance(self, expected_value_idx: int) -> float:
        """
        Computes sample variance for this record, taking one of the values as the expected value.
        This is useful for comparing how various ProjectTimings vary from the reference.
        """

        if (td := self.values[expected_value_idx]) is not None:
            xbar = td.total_seconds()
        else:
            xbar = 0.0

        sample = [td.total_seconds() if td is not None else 0.0 for td in self.values]

        return statistics.variance(sample, xbar)


type ProjectName = str
type StepTimings = dict[ProjectName, ProjectTimings]


class FullTimings(BaseModel):
    build: StepTimings
    lint: StepTimings
    test: StepTimings
    ls: StepTimings


def collect_timings(
    reports: list[ReportInfo],
    reference_report_idx: int,
    limit: int = 10,
) -> FullTimings:
    all_tests_by_names: list[dict[str, TestReport]] = [
        report.tests_by_name() for report, _, _ in reports
    ]
    reference_tests_by_names = all_tests_by_names[reference_report_idx]

    def step_timing_sorting_key(st: tuple[ProjectName, ProjectTimings]):
        return st[1].variance(reference_report_idx), st[0]

    kwargs = {}
    for step_name in ["build", "lint", "test", "ls"]:
        step_timings: StepTimings = {}

        for project in reference_tests_by_names.keys():
            values: list[timedelta | None] = []
            for tests_by_names in all_tests_by_names:
                value: timedelta | None = None
                if (
                    (test := tests_by_names.get(project))
                    and (step := test.step(step_name))
                    and step.exit_code == 0
                ):
                    value = step.execution_time

                values.append(value)

            project_timings = ProjectTimings(
                values=values,
                trends=trends_row_with_optionals(values, reference_report_idx),
            )
            step_timings[project] = project_timings

        selected_step_timings = dict(
            islice(
                sorted(
                    step_timings.items(),
                    key=step_timing_sorting_key,
                    reverse=True,
                ),
                limit,
            )
        )

        kwargs[step_name] = selected_step_timings

    return FullTimings(**kwargs)
