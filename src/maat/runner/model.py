import shlex
from itertools import count
from typing import Any

from pydantic import BaseModel, Field

_next_id = count()


def next_id() -> int:
    global _next_id
    return next(_next_id)


def _default_step_name(data: dict[str, Any]) -> str:
    run = data["run"]
    return shlex.join(run) if isinstance(run, list) else str(run)


type Command = str | list[str]
type ImageId = str


class TestStep(BaseModel):
    id: int = Field(default_factory=next_id)
    run: Command
    name: str = Field(default_factory=_default_step_name)
    setup: bool = False
    """Setup steps are not analyzed in reports."""


class Test(BaseModel):
    id: int = Field(default_factory=next_id)
    name: str
    steps: list[TestStep]


class TestSuite(BaseModel):
    sandbox: ImageId
    tests: list[Test] = []
