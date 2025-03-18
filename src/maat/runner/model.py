from itertools import count

from pydantic import BaseModel, Field

_next_id = count()


def next_id() -> int:
    global _next_id
    return next(_next_id)


type Command = str | list[str]
type ImageId = str


class TestStep(BaseModel):
    id: int = Field(default_factory=next_id)
    name: str
    run: Command
    setup: bool = False
    """Setup steps are not analyzed in reports."""


class Test(BaseModel):
    id: int = Field(default_factory=next_id)
    name: str
    steps: list[TestStep]


class TestSuite(BaseModel):
    sandbox: ImageId
    tests: list[Test] = []
