import re
from collections import defaultdict

from maat.model import (
    ClassifyDiagnostics,
    CompiledProcMacrosFromSource,
    Step,
    StepMeta,
    StepReport,
    TestReport,
)
from maat.utils.data import jsonlines

BuildMeta = StepMeta(
    name="build",
    analysers=lambda: [
        compiled_procmacros_from_source,
        classify_diagnostics,
    ],
)

LintMeta = StepMeta(
    name="lint",
    analysers=lambda: [
        classify_diagnostics,
    ],
)


def workflow() -> list[Step]:
    return [
        Step(meta=BuildMeta, run="scarb --json build --test"),
        Step(meta=LintMeta, run="scarb --json lint"),
    ]


def compiled_procmacros_from_source(test: TestReport, step: StepReport):
    candidates = {}
    package_ids = []
    for msg in jsonlines(step.stdout):
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
    step.analyses.compiled_procmacros_from_source = CompiledProcMacrosFromSource(
        package_ids=package_ids
    )


def classify_diagnostics(test: TestReport, step: StepReport):
    warnings = 0
    errors = 0
    message_severity_count = defaultdict(int)

    for msg in jsonlines(step.stdout):
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
        diagnostics_by_message_and_severity.append((severity, message, count))
    diagnostics_by_message_and_severity.sort(key=lambda x: (x[2], x[1]))

    step.analyses.classify_diagnostics = ClassifyDiagnostics(
        warnings=warnings,
        errors=errors,
        total=warnings + errors,
        diagnostics_by_message_and_severity=diagnostics_by_message_and_severity,
    )
