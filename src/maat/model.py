from datetime import datetime, timedelta
from typing import Any, Callable, Self, Literal, NamedTuple

from pydantic import (
    BaseModel,
    Field,
    model_validator,
    model_serializer,
    SerializerFunctionWrapHandler,
)

from maat.installation import REPO, this_maat_commit
from maat.semver import Semver
from maat.utils.shell import join_command
from maat.utils.unique_id import unique_id

type ImageId = str

type Analyser = Callable[[TestReport, StepReport], None]
type Severity = Literal["error", "warn"]


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

    analysers: Callable[[], list[Analyser]] | None = None
    """
    List of analyser functions that are called on outputs of this step when analysing reports.
    """

    def __init__(self, /, **data: Any) -> None:
        super().__init__(**data)

        if self.name is not None:
            if self.name in _meta_registry:
                raise ValueError(
                    f"step meta with name '{self.name}' is already registered"
                )

            _meta_registry[self.name] = self

    @model_validator(mode="after")
    def _check_name_is_set(self) -> Self:
        has_prop_requiring_name = self.analysers is not None
        if has_prop_requiring_name and self.name is None:
            raise ValueError("unnamed step meta specifies props that require a name")
        return self

    @classmethod
    def by_name(cls, name: str) -> Self | None:
        # Ensure all workflows are loaded as they're the place where other StepMetas are created.
        from maat.workflows import ALL

        _ = ALL

        return _meta_registry.get(name)


_meta_registry: dict[str, StepMeta] = {}

DefaultStepMeta = StepMeta()
SetupStepMeta = StepMeta(setup=True)


def _step_name_default(data: dict[str, Any]) -> str:
    meta: StepMeta = data["meta"]
    if meta.name is not None:
        return meta.name

    run: str | list[str] = data["run"]
    return join_command(run)


class Step(BaseModel):
    meta: StepMeta = DefaultStepMeta
    id: int = Field(default_factory=unique_id)
    run: str | list[str]
    name: str = Field(default_factory=_step_name_default)

    @model_validator(mode="after")
    def _check_name(self) -> Self:
        if self.meta.name is not None and self.name != self.meta.name:
            raise ValueError(
                f"step name '{self.name}' does not match step meta name '{self.meta.name}'"
            )
        return self

    @classmethod
    def setup(cls, run: str | list[str]) -> Self:
        """Shortcut for creating setup steps that are irrelevant to analysis."""
        return cls(meta=SetupStepMeta, run=run)


class Test(BaseModel):
    id: int = Field(default_factory=unique_id)
    name: str
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

    analyses: Analyses = Analyses()

    # These two are kept last because they take significant chunks of view area.
    stdout: list[bytes] | None
    stderr: list[bytes] | None

    @classmethod
    def blueprint(cls, step: Step):
        return cls(
            id=step.id,
            name=step.name,
            run=join_command(step.run),
            exit_code=None,
            execution_time=None,
            stdout=None,
            stderr=None,
        )


class TestReport(BaseModel):
    id: int
    name: str
    steps: list[StepReport] = []

    @property
    def execution_time(self) -> timedelta:
        total = timedelta()
        for step in self.steps:
            if step.execution_time is not None:
                total += step.execution_time
        return total

    def get_step_by_name(self, name: str) -> StepReport | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None


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

    def tests_by_name(self) -> dict[str, TestReport]:
        return {test.name: test for test in self.tests}
