from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from maat.installation import REPO, this_maat_commit
from maat.runner.model import Step
from maat.semver import Semver
from maat.utils.shell import join_command

type Command = str
type TestName = str
type StepName = str


class StepReport(BaseModel):
    id: int
    name: StepName
    run: Command
    exit_code: int | None
    stdout: list[bytes] | None
    stderr: list[bytes] | None
    execution_time: timedelta | None

    @classmethod
    def blueprint(cls, step: Step):
        return cls(
            id=step.id,
            name=step.name,
            run=join_command(step.run),
            exit_code=None,
            stdout=None,
            stderr=None,
            execution_time=None,
        )


class TestReport(BaseModel):
    id: int
    name: TestName
    steps: list[StepReport] = []

    @property
    def execution_time(self) -> timedelta:
        total = timedelta()
        for step in self.steps:
            if step.execution_time is not None:
                total += step.execution_time
        return total


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
