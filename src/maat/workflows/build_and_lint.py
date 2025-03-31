import re

from maat.model import Step, StepMeta, StepReport, TestReport
from maat.utils.data import jsonlines

BuildMeta = StepMeta(
    name="build",
    analysers=lambda: [
        compiled_procmacros_from_source,
        count_warnings_and_errors,
    ],
)

LintMeta = StepMeta(
    name="lint",
    analysers=lambda: [
        count_warnings_and_errors,
    ],
)


def workflow() -> list[Step]:
    return [
        Step(meta=BuildMeta, run="scarb --json build --test"),
        Step(meta=LintMeta, run="scarb --json lint"),
    ]


def compiled_procmacros_from_source(test: TestReport, step: StepReport):
    candidates = {}
    found = []
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
                    found.append(candidates[target_name])
    step.analyses["compiled_procmacros_from_source"] = found


def count_warnings_and_errors(test: TestReport, step: StepReport):
    """
    Analyzes the build output to count warnings and errors.

    Warnings are identified by {"type": "warn"} in the JSON output.
    Errors are identified by {"type": "error"} in the JSON output.

    The counts are stored in step.analyses["build_warnings_and_errors"].
    """
    warnings = 0
    errors = 0

    for msg in jsonlines(step.stdout):
        match msg:
            case {"type": "warn"}:
                warnings += 1
            case {"type": "error"}:
                errors += 1

    step.analyses["build_warnings_and_errors"] = {
        "warnings": warnings,
        "errors": errors,
        "total": warnings + errors,
    }
