import re

from rich.console import Console
from rich.progress import track

from maat.model import (
    Analyser,
    Label,
    LabelCategory,
    Labels,
    Report,
    StepReport,
    TestReport,
    TestsSummary,
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
    labels = Labels()

    if (fetch := test.step("fetch")) and fetch.was_executed and fetch.exit_code != 0:
        labels.add(_fetch_label(fetch))

    if (build := test.step("build")) and build.was_executed and build.exit_code != 0:
        labels.add(_build_label(build))

    if not any(lbl.category is LabelCategory.BUILD_FAIL for lbl in labels):
        # Don't add these labels if more critical failures have been identified.

        if (lint := test.step("lint")) and lint.was_executed and lint.exit_code != 0:
            labels.add(_lint_label(lint))

        # Test summary is populated only if a test step has been executed, not checking twice.
        if ts := test.analyses.tests_summary:
            lbl = _test_label(ts)
            labels.add(lbl)

        # Check if CairoLS reports errors while building succeeded.
        if (ls := test.step("ls")) and ls.was_executed:
            if lbl := _ls_label(ls, build_failed=False):
                labels.add(lbl)

    else:
        # Build failed, check if CairoLS reports no errors.
        if (ls := test.step("ls")) and ls.was_executed:
            if lbl := _ls_label(ls, build_failed=True):
                labels.add(lbl)

    assert labels, f"no labels were finally assigned for {test.name}"
    test.analyses.labels = labels


def _fetch_label(fetch: StepReport) -> Label:
    if lbl := _fatal_panic(fetch):
        return lbl

    if re.search(
        r"^\[out] error: version solving failed:"
        r"|^\[out] error: failed to lookup for `.*` in registry:"
        r"|^\[out] error: found dependencies on the same package `.*` coming from incompatible sources:",
        fetch.log_str,
        re.M,
    ):
        return Label.new(LabelCategory.BROKEN, "unsolvable deps")

    if re.search(
        r"^\[out] Scarb does not have real version solving algorithm yet."
        r"|^\[out] Caused by:\n\[out]\s+cannot find package `",
        fetch.log_str,
        re.M,
    ):
        return Label.new(LabelCategory.BROKEN, "pubgrub required")

    return Label.new(LabelCategory.BROKEN, "unknown deps error")


def _build_label(build: StepReport) -> Label | None:
    if lbl := _fatal_panic(build):
        return lbl

    if re.search(
        r"^\[out] error: could not compile `.*` due to previous error",
        build.log_str,
        re.M,
    ):
        return Label.new(LabelCategory.BUILD_FAIL, "compiler error")

    return Label.new(LabelCategory.BROKEN, "broken build")


def _lint_label(lint: StepReport) -> Label:
    if (
        b"[out] error: scarb was not compiled with the `lint` command enabled"
        in lint.log
    ) or b"[out] error: no such command: `lint`" in lint.log:
        return Label.new(LabelCategory.LINT_FAIL, "no linter")

    if b"[err] error: unexpected argument '--deny-warnings' found" in lint.log:
        return Label.new(LabelCategory.LINT_FAIL, "no --deny-warnings")

    return Label.new(LabelCategory.LINT_FAIL, "lint violations")


def _test_label(ts: TestsSummary) -> Label:
    if ts.failed > 0:
        return Label.new(LabelCategory.TEST_FAIL, f"{ts.failed} failed")
    else:
        return Label.new(LabelCategory.TEST_PASS, "tests passed")


def _fatal_panic(step: StepReport) -> Label | None:
    m = re.search(r"^\[err] thread '.*' panicked at (?P<path>.*):", step.log_str, re.M)

    if not m:
        return None

    path = m.group("path")
    if "cairo-lang-" in path:
        source = "compiler"
    elif "scarb" in path:
        source = "scarb"
    else:
        source = "unknown"
    return Label.new(LabelCategory.BROKEN, f"{source} panic")


def _ls_label(ls: StepReport, build_failed: bool) -> Label | None:
    """
    Creates a label based on language server diagnostics and build status.
    Returns a label only when there's an inconsistency between build and LS statuses.
    """
    has_errors = _ls_has_errors(ls)

    if ls.exit_code != 0:
        return Label.new(LabelCategory.LS_FAIL, "ls crashed")
    elif build_failed and not has_errors:
        return Label.new(LabelCategory.LS_FAIL, "build failed but ls didn't")
    elif not build_failed and has_errors:
        return Label.new(LabelCategory.LS_FAIL, "ls failed but build didn't")
    else:
        # No inconsistency so no labels to add.
        return None


def _ls_has_errors(ls: StepReport) -> bool:
    # Check for total errors count greater than 0.
    match = re.search(r"total: (\d+) errors", ls.log_str, re.M)
    return match and int(match.group(1)) > 0
