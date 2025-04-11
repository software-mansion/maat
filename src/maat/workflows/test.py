import re

from maat.model import Step, StepMeta, StepReport, TestReport, TestsSummary

TestMeta = StepMeta(
    name="test",
    analysers=lambda: [
        tests_summary,
    ],
)


def workflow() -> list[Step]:
    return [
        Step(meta=TestMeta, run="scarb --json test --workspace"),
    ]


def tests_summary(test: TestReport, step: StepReport):
    """
    Analyses the test output to extract the number of passed, failed, and ignored tests.
    """
    stdout = step.stdout_utf8continuous()

    # Find all test summary lines.
    matches = re.findall(r"^(?:Tests: |test result: ).*", stdout, re.M)

    passed, failed, skipped, ignored = 0, 0, 0, 0
    for line in matches:
        passed += _extract_count(r"(\d+)\s+passed", line, 0)
        failed += _extract_count(r"(\d+)\s+failed", line, 0)
        skipped += _extract_count(r"(\d+)\s+skipped", line, 0)
        ignored += _extract_count(r"(\d+)\s+ignored", line, 0)

    if matches:
        step.analyses.tests_summary = TestsSummary(
            passed=passed,
            failed=failed,
            skipped=skipped,
            ignored=ignored,
        )


def _extract_count(pattern: str, text: str, default: int | None = None) -> int:
    m = re.search(pattern, text)
    if default is None:
        return int(m.group(1))
    else:
        return int(m.group(1)) if m else default
