import statistics
from datetime import timedelta
from itertools import islice

from pydantic import BaseModel

from maat.model import TestReport, logs_txt_path
from maat.report.trends import Trend, trends_row_with_optionals
from maat.web import ReportInfo


class ProjectTimings(BaseModel):
    values: list[timedelta | None]
    trends: list[Trend | None]
    log_links: list[str | None]

    def variance(self, expected_value_idx: int) -> float:
        """
        Computes sample variance for this record, taking one of the values as the expected value.
        This is useful for comparing how various ProjectTimings vary from the reference.
        """

        if all(v is None for v in self.values):
            return 0.0

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
        return -st[1].variance(reference_report_idx), st[0]

    kwargs = {}
    for step_name in ["build", "lint", "test", "ls"]:
        step_timings: StepTimings = {}

        for project in reference_tests_by_names.keys():
            values: list[timedelta | None] = []
            log_links: list[str | None] = []
            for report_idx, (_, report_meta, _) in enumerate(reports):
                tests_by_names = all_tests_by_names[report_idx]
                value: timedelta | None = None
                log_link: str | None = None
                if (
                    (test := tests_by_names.get(project))
                    and (step := test.step(step_name))
                    and step.exit_code == 0
                ):
                    value = step.execution_time
                    log_link = str(logs_txt_path(report_meta, test))

                values.append(value)
                log_links.append(log_link)

            project_timings = ProjectTimings(
                values=values,
                trends=trends_row_with_optionals(values, reference_report_idx),
                log_links=log_links,
            )

            # Ignore rows where there are no timings or only one.
            # These don't make sense from the perspective of comparing timings.
            if sum(1 for trend in project_timings.trends if trend is not None) < 2:
                continue

            step_timings[project] = project_timings

        # Pick at most `limit` rows, preferring ones with the highest variance (relative to the reference value).
        selected_step_timings = dict(
            islice(
                sorted(
                    step_timings.items(),
                    key=step_timing_sorting_key,
                ),
                limit,
            )
        )

        kwargs[step_name] = selected_step_timings

    return FullTimings(**kwargs)
