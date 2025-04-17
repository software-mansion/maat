import re

from rich.console import Console
from rich.progress import track

from maat.model import (
    Analyser,
    Label,
    LabelCategory,
    Report,
    TestReport,
    TestsSummary,
    StepReport,
)


def analyse_report(report: Report, console: Console):
    analyzers: list[Analyser] = [
        tests_summary,
        label,  # NOTE: This analyser depends on all previous ones.
    ]

    jobs: list[tuple[Analyser, TestReport]] = [
        (analyzer, test) for test in report.tests for analyzer in analyzers
    ]

    for analyser, test in track(
        jobs,
        console=console,
        description="Analysing results...",
        transient=True,
    ):
        analyser(test)


def tests_summary(test: TestReport):
    """
    Analyses the test output to extract the number of passed, failed, and ignored tests.
    """
    step = test.step("test")
    if step is None:
        return

    # Find all test summary lines.
    matches = re.findall(r"^\[out]\s*(?:Tests: |test result: ).*", step.log_str, re.M)

    passed, failed, skipped, ignored = 0, 0, 0, 0
    for line in matches:
        passed += _extract_count(r"(\d+)\s+passed", line, 0)
        failed += _extract_count(r"(\d+)\s+failed", line, 0)
        skipped += _extract_count(r"(\d+)\s+skipped", line, 0)
        ignored += _extract_count(r"(\d+)\s+ignored", line, 0)

    if matches:
        test.analyses.tests_summary = TestsSummary(
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


def label(test: TestReport):
    """
    Assign various labels to the test.
    """
    labels: list[Label] = []

    if (fetch := test.step("fetch")) and fetch.was_executed and fetch.exit_code != 0:
        labels.append(Label.new(LabelCategory.BROKEN, _why_fetch_failed(fetch)))

    if (build := test.step("build")) and build.was_executed and build.exit_code != 0:
        if build_fail_reason := _why_build_failed(build):
            lbl = Label.new(LabelCategory.BUILD_FAIL, build_fail_reason)
        else:
            lbl = Label.new(LabelCategory.BROKEN, "broken build")
        labels.append(lbl)

    if not any(lbl.category is LabelCategory.BUILD_FAIL for lbl in labels):
        # Don't add these labels if more critical failures have been identified.

        if (lint := test.step("lint")) and lint.was_executed and lint.exit_code != 0:
            labels.append(Label.new(LabelCategory.LINT_FAIL, _why_lint_failed(lint)))

        # Test summary is populated only if a test step has been executed, not checking twice.
        if ts := test.analyses.tests_summary:
            if ts.failed > 0:
                lbl = Label.new(LabelCategory.TEST_FAIL, f"{ts.failed} failed")
            else:
                lbl = Label.new(LabelCategory.TEST_PASS, "tests passed")
            labels.append(lbl)

    assert labels, f"no labels were finally assigned for {test.name}"
    labels.sort(key=Label.priority)
    test.analyses.labels = labels


def _why_fetch_failed(fetch: StepReport) -> str:
    return "unknown deps error"


def _why_build_failed(build: StepReport) -> str | None:
    if re.search(
        r"^\[out] error: could not compile `.*` due to previous error",
        build.log_str,
        re.M,
    ):
        return "compiler error"

    return None


def _why_lint_failed(lint: StepReport) -> str:
    if (
        b"[out] error: scarb was not compiled with the `lint` command enabled"
        in lint.log
    ) or b"[out] error: no such command: `lint`" in lint.log:
        return "no linter"

    if b"[err] error: unexpected argument '--deny-warnings' found" in lint.log:
        return "no --deny-warnings"

    return "lint violations"
