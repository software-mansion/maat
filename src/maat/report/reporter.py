import time
from datetime import timedelta
from typing import Literal, Self

from maat import Report
from maat.model import Semver, Step, StepReport, Test, TestReport


class StepReporter:
    def __init__(self, report: StepReport):
        self._report = report
        self._timer: _ExecutionTimer | None = None
        self._log_builder: list[bytes] = []

    def set_exit_code(self, exit_code: int):
        self._report.exit_code = exit_code

    def log(self, source: Literal["stdout", "stderr"], line: bytes):
        match source:
            case "stdout":
                source_tag = b"out"
            case "stderr":
                source_tag = b"err"
            case unknown:
                raise ValueError(unknown)

        self._log_builder.extend((b"[", source_tag, b"] ", line))
        if not line.endswith(b"\n"):
            self._log_builder.append(b"\n")

    def __enter__(self) -> Self:
        self._timer = _ExecutionTimer()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self._timer is not None
        self._report.execution_time = self._timer.stop()

        self._report.log = b"".join(self._log_builder)

        return False  # Don't suppress exceptions.


class TestReporter:
    def __init__(self, report: Report, test: Test):
        self._report = report

        self._test_report = test_report = TestReport(
            name=test.name,
            rev=test.rev,
            steps=[StepReport.blueprint(step) for step in test.steps],
        )
        report.tests.append(test_report)

    def step(self, step: Step) -> StepReporter:
        step_report = next(
            (sr for sr in self._test_report.steps if sr.name == step.name), None
        )
        assert step_report is not None, (
            f"step with name {step.name} not found in the report"
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
        self._timer = _ExecutionTimer()

    def test(self, test: Test) -> TestReporter:
        return TestReporter(self._report, test)

    def finish(self) -> Report:
        self._report.total_execution_time = self._timer.stop()
        return self._report


class _ExecutionTimer:
    def __init__(self):
        self._start_time = time.perf_counter()

    def stop(self) -> timedelta:
        return timedelta(seconds=time.perf_counter() - self._start_time)
