from maat.model import StepMeta, Step

LintMeta = StepMeta(name="lint")


def workflow() -> list[Step]:
    return [
        Step(meta=LintMeta, run="scarb --json lint"),
    ]
