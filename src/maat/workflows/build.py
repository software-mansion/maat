from maat.model import StepMeta, Step

BuildMeta = StepMeta(name="build")


def workflow() -> list[Step]:
    return [
        Step(meta=BuildMeta, run="scarb --json build --test"),
    ]
