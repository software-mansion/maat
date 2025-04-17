import re
from collections import defaultdict

from rich.console import Console
from rich.progress import track

from maat.model import (
    Analyser,
    Report,
    TestReport,
    CompiledProcMacrosFromSource,
    ClassifiedDiagnostic,
    ClassifyDiagnostics,
    TestsSummary,
)


def analyse_report(report: Report, console: Console):
    analyzers: list[Analyser] = [
        compiled_procmacros_from_source,
        classify_diagnostics,
        tests_summary,
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


def compiled_procmacros_from_source(test: TestReport):
    step = test.step("build")
    if step is None:
        return

    candidates = {}
    package_ids = []
    for msg in step.stdout_jsonlines():
        match msg:
            # "{\"status\":\"compiling\",\"message\":\"snforge_scarb_plugin v0.34.1\"}\n",
            case {"status": "compiling", "message": message}:
                match = re.match(r"^(?P<name>.+?)\s+v(?P<version>.+)$", message)
                if match:
                    candidates[match.group("name")] = message
            # "{\"reason\":\"compiler-artifact\",\"target\":{...,\"name\":\"snforge_scarb_plugin\",...},...}\n",
            case {"reason": "compiler-artifact", "target": {"name": target_name}}:
                if target_name in candidates:
                    package_ids.append(candidates[target_name])
    test.analyses.compiled_procmacros_from_source = CompiledProcMacrosFromSource(
        package_ids=package_ids
    )


def classify_diagnostics(test: TestReport):
    step = test.step("build")
    if step is None:
        return

    warnings = 0
    errors = 0
    message_severity_count = defaultdict(int)

    for msg in step.stdout_jsonlines():
        match msg:
            case {"type": "warn"}:
                warnings += 1
            case {"type": "error"}:
                errors += 1

        match msg:
            case {"type": severity, "message": message}:
                first_line = message.split("\n")[0]
                message_severity_count[(severity, first_line)] += 1

    diagnostics_by_message_and_severity = []
    for (severity, message), count in message_severity_count.items():
        diagnostics_by_message_and_severity.append(
            ClassifiedDiagnostic(severity, message, count)
        )
    diagnostics_by_message_and_severity.sort(
        key=lambda x: (x.severity, x.message, x.count)
    )

    test.analyses.classify_diagnostics = ClassifyDiagnostics(
        warnings=warnings,
        errors=errors,
        total=warnings + errors,
        diagnostics_by_message_and_severity=diagnostics_by_message_and_severity,
    )


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
