import re

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
from maat.utils.log import track


def analyse_report(report: Report):
    analyzers: list[Analyser] = [
        tests_summary,
        test_runner,
        label,  # NOTE: This analyser depends on all previous ones.
    ]

    jobs: list[tuple[Analyser, TestReport]] = [
        (analyzer, test) for test in report.tests for analyzer in analyzers
    ]

    with track("Analysing results"):
        for analyser, test in jobs:
            analyser(test)


def tests_summary(test: TestReport):
    """
    Analyses the test output to extract the number of passed, failed, and ignored tests.
    """
    step = test.step("test")
    if step is None:
        return

    # Find all test summary lines.
    matches = re.findall(
        r"^\[(?:out|err)]\s*(?:Error:\s*)?(?:Tests: |test result: ).*",
        step.log_str,
        re.M,
    )

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


def test_runner(test: TestReport):
    """
    Detect which test runner was used based on the log output.
    """
    step = test.step("test")
    if step is None or not step.was_executed:
        return

    runner = _detect_test_runner(step)
    if runner:
        test.analyses.test_runner = runner


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

    if (fetch := test.step("fetch")) and fetch.was_executed:
        if lbl := _fetch_label(fetch):
            labels.add(lbl)

    if (build := test.step("build")) and build.was_executed:
        if lbl := _build_label(build):
            labels.add(lbl)

    if not labels:
        # Don't add these labels if more critical failures have been identified.

        if (lint := test.step("lint")) and lint.was_executed:
            if lbl := _lint_label(lint):
                labels.add(lbl)

        if (rep := test.step("test")) and rep.was_executed:
            if lbl := _test_label(rep, test.analyses.tests_summary):
                labels.add(lbl)

    # Check if CairoLS reports errors XOR building succeeded (i.e., there is a diagnostics mismatch).
    if (ls := test.step("ls")) and ls.was_executed:
        build_failed = any(lbl.category is LabelCategory.BUILD_FAIL for lbl in labels)
        if lbl := _ls_label(ls, build_failed=build_failed):
            labels.add(lbl)

    if not labels:
        lbl = Label.new(LabelCategory.ERROR, ":monkas:")
        labels.add(lbl)

    test.analyses.labels = labels


def _fetch_label(fetch: StepReport) -> Label | None:
    if fetch.exit_code == 0:
        return None

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

    return Label.new(LabelCategory.ERROR, "unknown deps error")


def _build_label(build: StepReport) -> Label | None:
    if build.exit_code == 0:
        return None

    if lbl := _fatal_panic(build):
        return lbl

    if re.search(
        r"^\[out] error: could not compile `.*` due to",
        build.log_str,
        re.M,
    ):
        return Label.new(LabelCategory.BUILD_FAIL, "compilation error")

    return Label.new(LabelCategory.ERROR, "build errored")


def _lint_label(lint: StepReport) -> Label:
    if lbl := _fatal_panic(lint, category=LabelCategory.LINT_FAIL):
        return lbl

    if (
        b"[out] error: scarb was not compiled with the `lint` command enabled"
        in lint.log
    ) or b"[out] error: no such command: `lint`" in lint.log:
        return Label.new(LabelCategory.LINT_BROKEN, "no linter")

    if b"[err] error: unexpected argument '--deny-warnings' found" in lint.log:
        return Label.new(LabelCategory.LINT_BROKEN, "no --deny-warnings")

    return Label.new(LabelCategory.LINT_FAIL, "lint violations")


def _detect_test_runner(rep: StepReport) -> str | None:
    """
    Detect which test runner was used based on the log output.
    Returns 'snforge', 'cairo-test', or None if the runner cannot be determined.
    """
    if rep.log_str is None:
        return None

    # Look for "Running test <package> (snforge test ...)" pattern
    if re.search(r"^\[out]\s+Running test\s+\S+\s+\(snforge test\b", rep.log_str, re.M):
        return "snforge"

    # Look for "Running test <package> (scarb cairo-test)" pattern
    if re.search(
        r"^\[out]\s+Running test\s+\S+\s+\(scarb cairo-test\)", rep.log_str, re.M
    ):
        return "cairo-test"

    return None


def _test_label(rep: StepReport, ts: TestsSummary | None) -> Label:
    runner = _detect_test_runner(rep)
    has_missing_summaries = _has_missing_test_summaries(rep)
    if ts is None or has_missing_summaries:
        if b"Not enough gas to call function." in rep.log:
            return Label.new(LabelCategory.TEST_ERROR, "cairo-test: not enough gas")
        elif b"[ERROR] Error while calling RPC method" in rep.log:
            return Label.new(LabelCategory.TEST_ERROR, "snforge: rpc error")
        elif b"Error: Failed setting up runner." in rep.log:
            return Label.new(
                LabelCategory.TEST_ERROR, "cairo-test: failed setting up runner"
            )
        else:
            return Label.new(LabelCategory.TEST_ERROR, "unknown test runner error")
    elif ts.failed > 0:
        if runner is None:
            return Label.new(LabelCategory.TEST_FAIL, f"{ts.failed} failed")
        else:
            return Label.new(LabelCategory.TEST_FAIL, f"{runner} {ts.failed} failed")
    else:
        if runner is None:
            return Label.new(LabelCategory.TEST_PASS, "tests passed")
        else:
            return Label.new(LabelCategory.TEST_PASS, f"{runner} passed")


def _has_missing_test_summaries(step: StepReport) -> bool:
    """
    Check if workspace tests failed to produce summaries by comparing
    the number of test runs with the number of test summaries found.
    """
    if step.log_str is None:
        return False

    # Find all test summary lines
    matches = re.findall(
        r"^\[(?:out|err)]\s*(?:Error:\s*)?(?:Tests: |test result: ).*",
        step.log_str,
        re.M,
    )

    # Look for "Running test" lines to identify individual test runs
    test_runs = re.findall(
        r"^\[out]\s+Running test\s+.*",
        step.log_str,
        re.M,
    )

    return len(test_runs) > len(matches) if test_runs else False


def _fatal_panic(
    step: StepReport,
    category: LabelCategory = LabelCategory.ERROR,
) -> Label | None:
    if m := re.search(
        r"^\[err] thread '.*' panicked at (?P<path>.*):", step.log_str, re.M
    ):
        path = m.group("path")
        if "cairo-lang-" in path:
            source = "compiler"
        elif "scarb" in path:
            source = "scarb"
        else:
            source = "unknown"
        return Label.new(category, f"{step.name}: {source} panic")

    return None


def _ls_label(ls: StepReport, build_failed: bool) -> Label | None:
    """
    Creates a label based on language server diagnostics and build status.
    Returns a label only when there is an inconsistency between build and LS statuses.
    """
    has_errors = _ls_has_errors(ls)

    if lbl := _fatal_panic(ls, category=LabelCategory.LS_FAIL):
        return lbl
    elif build_failed and not has_errors:
        return Label.new(LabelCategory.LS_FAIL, "ls misses errors")
    elif not build_failed and has_errors:
        return Label.new(LabelCategory.LS_FAIL, "ls has new errors")
    else:
        # No inconsistency so no labels to add.
        return None


def _ls_has_errors(ls: StepReport) -> bool:
    # Check for total errors count greater than 0.
    match = re.search(r"total: (\d+) errors", ls.log_str, re.M)
    return match and int(match.group(1)) > 0
