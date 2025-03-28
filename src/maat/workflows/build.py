from maat.runner.model import Step, StepMeta

BuildMeta = StepMeta(name="build")


def workflow() -> list[Step]:
    return [
        Step(meta=BuildMeta, run="scarb --json build --test"),
    ]
