from datetime import timedelta

from pydantic import BaseModel

from maat.model import TestReport
from maat.report.trends import Trend, trends_row_with_optionals
from maat.web import ReportInfo


class ProjectTimings(BaseModel):
    values: list[timedelta | None]
    trends: list[Trend]


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
) -> FullTimings:
    all_tests_by_names: list[dict[str, TestReport]] = [
        report.tests_by_name() for report, _, _ in reports
    ]
    reference_tests_by_names = all_tests_by_names[reference_report_idx]

    kwargs = {}
    for step_name in ["build", "lint", "test", "ls"]:
        step_timings: StepTimings = {}

        for project in reference_tests_by_names.keys():
            values: list[timedelta | None] = []
            for tests_by_names in all_tests_by_names:
                value: timedelta | None = None
                if test := tests_by_names.get(project):
                    if step := test.step(step_name):
                        value = step.execution_time

                values.append(value)

            project_timings = ProjectTimings(
                values=values,
                trends=trends_row_with_optionals(values, reference_report_idx),
            )
            step_timings[project] = project_timings

        kwargs[step_name] = step_timings

    return FullTimings(**kwargs)
