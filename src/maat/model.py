import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, NamedTuple, Self

from pydantic import (
    BaseModel,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from maat.installation import REPO, this_maat_commit
from maat.utils.shell import join_command
from maat.utils.unique_id import unique_id

type Semver = str
type ImageId = str

type Analyser = Callable[[TestReport], None]
type Severity = Literal["error", "warn"]


class Step(BaseModel):
    id: int = Field(default_factory=unique_id)
    run: str | list[str]
    name: str = Field(default_factory=lambda data: join_command(data["run"]))
    setup: bool = False
    """
    Setup steps halt test on failure and progress bars behaves differently for these.
    """


class Test(BaseModel):
    id: int = Field(default_factory=unique_id)
    name: str
    rev: str
    steps: list[Step]


class TestSuite(BaseModel):
    sandbox: ImageId
    tests: list[Test] = []

    def test_by_name(self, name: str) -> Test | None:
        for test in self.tests:
            if test.name == name:
                return test
        return None


class CompiledProcMacrosFromSource(BaseModel):
    package_ids: list[str]


class ClassifiedDiagnostic(NamedTuple):
    severity: Severity
    message: str
    count: int


class ClassifyDiagnostics(BaseModel):
    warnings: int
    errors: int
    total: int
    diagnostics_by_message_and_severity: list[ClassifiedDiagnostic]


class TestsSummary(BaseModel):
    passed: int
    failed: int
    skipped: int
    ignored: int

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.ignored


class Analyses(BaseModel):
    compiled_procmacros_from_source: CompiledProcMacrosFromSource | None = None
    classify_diagnostics: ClassifyDiagnostics | None = None
    tests_summary: TestsSummary | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, nxt: SerializerFunctionWrapHandler):
        return {k: v for k, v in nxt(self).items() if v is not None}


class StepReport(BaseModel):
    id: int
    name: str
    run: str
    exit_code: int | None
    execution_time: timedelta | None

    # This one is kept last because it takes significant chunks of view area.
    log: bytes | None = None

    @classmethod
    def blueprint(cls, step: Step):
        return cls(
            id=step.id,
            name=step.name,
            run=join_command(step.run),
            exit_code=None,
            execution_time=None,
            log=None,
        )

    @property
    def log_str(self) -> str | None:
        if self.log is None:
            return None
        return self.log.decode("utf-8", errors="replace")

    def stdout_jsonlines(self) -> Iterable[dict[str, Any]]:
        if self.log is None:
            return

        for line in self.log.splitlines():
            if payload := line.removeprefix(b"[out] "):
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    pass


class TestReport(BaseModel):
    id: int
    name: str
    rev: str | None = None
    steps: list[StepReport] = []
    analyses: Analyses = Analyses()

    @property
    def name_and_rev(self) -> str:
        return f"{self.name}-{self.rev}"

    @property
    def execution_time(self) -> timedelta:
        total = timedelta()
        for step in self.steps:
            if step.execution_time is not None:
                total += step.execution_time
        return total

    def step(self, name: str) -> StepReport | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def combined_log(self) -> bytes:
        chunks = []
        chunks.extend(("=== ", self.name_and_rev, " ===\n"))
        for step in self.steps:
            chunks.extend(("\n>>> ", step.run, "\n"))
            if step.log is not None:
                chunks.append(step.log)
            if step.exit_code is not None and step.exit_code != 0:
                chunks.append(f"Process finished with exit code {step.exit_code}\n")
        return b"".join(
            (chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8"))
            for chunk in chunks
        )


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

    def sort(self):
        self.tests.sort(key=lambda t: t.name)

    def save(self):
        self.sort()
        with open(REPO / "reports" / f"{self.name}.json", "w") as f:
            f.write(self.model_dump_json(indent=2) + "\n")

    def test(self, name: str) -> TestReport | None:
        for test in self.tests:
            if test.name == name:
                return test
        return None

    def tests_by_name(self) -> dict[str, TestReport]:
        return {test.name: test for test in self.tests}


class ReportMeta(BaseModel):
    """Some metadata about the report file itself."""

    name: str

    @classmethod
    def new(cls, path: Path) -> Self:
        return cls(name=path.stem)
