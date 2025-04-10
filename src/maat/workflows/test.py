import re

from maat.model import Step, StepMeta, StepReport, TestReport, TestsSummary
from maat.utils.data import utf8continuous

TestMeta = StepMeta(
    name="test",
    analysers=lambda: [
        tests_summary,
    ],
)


def workflow() -> list[Step]:
    return [
        Step(meta=TestMeta, run="scarb --json test"),
    ]


def tests_summary(test: TestReport, step: StepReport):
    """
    Analyses the test output to extract the number of passed, failed, and ignored tests.
    """
    stdout = utf8continuous(step.stdout)

    # Look for the test summary line
    match = re.search(
        r"Tests: (\d+) passed, (\d+) failed, (\d+) skipped, (\d+) ignored",
        stdout,
    )
    if match:
        passed = int(match.group(1))
        failed = int(match.group(2))
        skipped = int(match.group(3))
        ignored = int(match.group(4))

        step.analyses.tests_summary = TestsSummary(
            passed=passed,
            failed=failed,
            skipped=skipped,
            ignored=ignored,
        )
