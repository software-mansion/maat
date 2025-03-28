from pydantic import BaseModel, Field

from maat.utils.shell import join_command
from maat.utils.unique_id import unique_id

type Command = str | list[str]
type ImageId = str


class TestStep(BaseModel):
    id: int = Field(default_factory=unique_id)
    run: Command
    name: str = Field(default_factory=lambda data: join_command(data["run"]))
    setup: bool = False
    """Setup steps are not analysed in reports."""


class Test(BaseModel):
    id: int = Field(default_factory=unique_id)
    name: str
    steps: list[TestStep]


class TestSuite(BaseModel):
    sandbox: ImageId
    tests: list[Test] = []
