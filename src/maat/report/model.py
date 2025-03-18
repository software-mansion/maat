import shlex
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from maat.installation import REPO, this_maat_commit
from maat.runner.model import TestStep
from maat.semver import Semver

type Command = str
type TestName = str
type StepName = str


class StepReport(BaseModel):
    id: int
    name: StepName
    run: Command
    setup: bool
    exit_code: int | None
    stdout: str | None
    stderr: str | None

    @classmethod
    def blueprint(cls, test_step: TestStep):
        return cls.from_test_step(
            test_step,
            exit_code=None,
            stdout=None,
            stderr=None,
        )

    @classmethod
    def from_test_step(cls, test_step: TestStep, **kwargs):
        return cls(
            id=test_step.id,
            name=test_step.name,
            run=normalize_command(test_step.run),
            setup=test_step.setup,
            **kwargs,
        )


class TestReport(BaseModel):
    id: int
    name: TestName
    steps: list[StepReport] = []


class Report(BaseModel):
    workspace: str
    scarb: Semver
    foundry: Semver
    maat_commit: str = Field(default_factory=this_maat_commit)
    created_at: datetime = Field(default_factory=datetime.now)
    total_execution_time: timedelta
    tests: list[TestReport] = []

    @property
    def name(self) -> str:
        return f"{self.workspace}-{self.scarb}-{self.foundry}"

    def save(self):
        with open(REPO / "reports" / f"{self.name}.json", "w") as f:
            f.write(self.model_dump_json(indent=2) + "\n")


def normalize_command(run: str | list[str]) -> str:
    if isinstance(run, list):
        return shlex.join(run)
    return run
