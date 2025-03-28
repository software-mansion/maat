from maat.model import StepMeta, Step

TestMeta = StepMeta(name="test")


def workflow() -> list[Step]:
    return [
        Step(meta=TestMeta, run="scarb --json test"),
    ]
