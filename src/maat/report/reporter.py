import time
from datetime import timedelta

from maat.report.model import Report, StepReport, TestReport
from maat.runner.model import Test, TestStep
from maat.semver import Semver


class StepReporter:
    def __init__(self, report: StepReport):
        self._report = report

    def set_exit_code(self, exit_code: int):
        self._report.exit_code = exit_code

    def append_stdout_line(self, line: bytes):
        if self._report.stdout is None:
            self._report.stdout = []
        self._report.stdout.append(line)

    def append_stderr_line(self, line: bytes):
        if self._report.stderr is None:
            self._report.stderr = []
        self._report.stderr.append(line)


class TestReporter:
    def __init__(self, report: Report, test: Test):
        self._report = report

        self._test_report = test_report = TestReport(
            id=test.id,
            name=test.name,
            steps=[StepReport.blueprint(step) for step in test.steps],
        )
        report.tests.append(test_report)

    def step(self, step: TestStep) -> StepReporter:
        step_report = next(
            (sr for sr in self._test_report.steps if sr.id == step.id), None
        )
        assert step_report is not None, (
            f"step with ID {step.id} not found in the report"
        )
        return StepReporter(step_report)


class Reporter:
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

    def test(self, test: Test) -> TestReporter:
        return TestReporter(self._report, test)

    def finish(self) -> Report:
        self._report.total_execution_time = timedelta(
            seconds=time.perf_counter() - self._start_time
        )
        return self._report
