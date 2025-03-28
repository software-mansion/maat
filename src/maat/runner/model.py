from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from maat.utils.shell import join_command
from maat.utils.unique_id import unique_id

type Command = str | list[str]
type ImageId = str


class StepMeta(BaseModel):
    name: str | None = None
    """
    A predefined, globally unique name for significant steps.
    Steps with name defined via meta can be analyzed etc.
    """

    setup: bool = False
    """
    Setup steps are not analysed in reports and progress bars behaves differently for these.
    """


DefaultStepMeta = StepMeta()
SetupStepMeta = StepMeta(setup=True)


def _step_name_default(data: dict[str, Any]) -> str:
    meta: StepMeta = data["meta"]
    if meta.name is not None:
        return meta.name

    run: Command = data["run"]
    return join_command(run)


class Step(BaseModel):
    meta: StepMeta = DefaultStepMeta
    id: int = Field(default_factory=unique_id)
    run: Command
    name: str = Field(default_factory=_step_name_default)

    @model_validator(mode="after")
    def _check_name(self) -> Self:
        if self.meta.name is not None and self.name != self.meta.name:
            raise ValueError(
                f"step name '{self.name}' does not match step meta name '{self.meta.name}'"
            )
        return self

    @classmethod
    def setup(cls, run: Command) -> Self:
        """Shortcut for creating setup steps that are irrelevant to analysis."""
        return cls(meta=SetupStepMeta, run=run)


class Test(BaseModel):
    id: int = Field(default_factory=unique_id)
    name: str
    steps: list[Step]


class TestSuite(BaseModel):
    sandbox: ImageId
    tests: list[Test] = []
