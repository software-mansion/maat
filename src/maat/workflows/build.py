import json
import re
from typing import Iterable

from maat.model import Step, StepMeta, StepReport, TestReport

BuildMeta = StepMeta(
    name="build",
    analysers=lambda: [
        compiled_procmacros_from_source,
    ],
)


def workflow() -> list[Step]:
    return [
        Step(meta=BuildMeta, run="scarb --json build --test"),
    ]


def compiled_procmacros_from_source(test: TestReport, step: StepReport):
    candidates = {}
    found = []
    for msg in jsonlines(step.stdout or []):
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


def jsonlines(output: list[str]) -> Iterable[dict]:
    for line in output:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            pass
