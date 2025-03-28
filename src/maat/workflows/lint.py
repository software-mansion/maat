from maat.runner.model import Step, StepMeta

LintMeta = StepMeta(name="lint")


def workflow() -> list[Step]:
    return [
        Step(meta=LintMeta, run="scarb --json lint"),
    ]
