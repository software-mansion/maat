from maat.model import Step


def workflow() -> list[Step]:
    return [
        Step.setup("maat-patch"),
    ]
