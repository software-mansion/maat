from maat.runner.model import Step, StepMeta

TestMeta = StepMeta(name="test")


def workflow() -> list[Step]:
    return [
        Step(meta=TestMeta, run="scarb --json test"),
    ]
