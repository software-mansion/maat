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

    # Look for the test summary line.
    match = re.search(r"^(?:Tests: |test result: ).*", stdout, re.M)
    if match:
        line = match.group(0)

        def extract_count(pattern: str, text: str, default: int | None = None) -> int:
            m = re.search(pattern, text)
            if default is None:
                return int(m.group(1))
            else:
                return int(m.group(1)) if m else default

        passed = extract_count(r"(\d+)\s+passed", line)
        failed = extract_count(r"(\d+)\s+failed", line)
        skipped = extract_count(r"(\d+)\s+skipped", line, 0)
        ignored = extract_count(r"(\d+)\s+ignored", line)

        step.analyses.tests_summary = TestsSummary(
            passed=passed,
            failed=failed,
            skipped=skipped,
            ignored=ignored,
        )
