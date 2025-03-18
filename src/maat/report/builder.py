import time
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from maat.report.model import Report, StepReport, TestReport
from maat.runner.model import Test, TestStep
from maat.semver import Semver


class TestReportBuilder:
    def __init__(self, test: Test):
        self._test = test
        self._reported_steps: dict[int, StepReport] = {}

    def report(self, step: TestStep, exit_code: int, stdout: str, stderr: str) -> None:
        self._reported_steps[step.id] = StepReport.from_test_step(
            step,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def finish(self) -> TestReport:
        steps = []
        for step in self._test.steps:
            if step.id in self._reported_steps:
                steps.append(self._reported_steps[step.id])
            else:
                steps.append(StepReport.blueprint(step))

        return TestReport(id=self._test.id, name=self._test.name, steps=steps)


class ReportBuilder:
    def __init__(
        self,
        workspace_name: str,
        scarb: Semver,
        foundry: Semver,
    ):
        self._report = Report(
            workspace=workspace_name,
            scarb=scarb,
            foundry=foundry,
            total_execution_time=timedelta.max,
        )
        self._start_time = time.perf_counter()

    @contextmanager
    def test(self, test: Test) -> Iterator[TestReportBuilder]:
        trb = TestReportBuilder(test)
        try:
            yield trb
        finally:
            self._report.tests.append(trb.finish())

    def finish(self) -> Report:
        self._report.total_execution_time = timedelta(
            seconds=time.perf_counter() - self._start_time
        )
        return self._report
