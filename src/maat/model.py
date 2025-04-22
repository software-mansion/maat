import enum
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    RootModel,
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

EXIT_RUNNER_SKIPPED = -1
"""Exit code set for steps which were skipped by the runner."""


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


@enum.unique
class LabelCategory(enum.StrEnum):
    # The higher the category here, the higher the priority when sorting for human presentation.
    ERROR = "error"
    BUILD_FAIL = "build-fail"
    LINT_FAIL = "lint-fail"
    TEST_FAIL = "test-fail"
    TEST_PASS = "test-pass"
    BROKEN = "broken"

    @enum.property
    def help(self) -> str:
        return {
            self.ERROR: "A serious error occurred before project could be built.",
            self.BUILD_FAIL: "Build failed.",
            self.LINT_FAIL: "Build succeeded but linting failed. Take these results with grain of salt because cairo-lint is not reliable .",
            self.TEST_FAIL: "Build succeeded but tests failed.",
            self.TEST_PASS: 'Build succeeded and tests passed. This is the "clean" state.',
            self.BROKEN: "Something is broken for this project in Ma'at context. This requires Ma'at maintainers investigation. Please ping them.",
        }[self]


_label_category_regex = "|".join(LabelCategory.__members__.values())


class Label(RootModel):
    root: str = Field(pattern=f"^(?:{_label_category_regex})(?:\([^()]+\))?$")

    @classmethod
    def new(cls, category: LabelCategory, comment: str | None = None) -> Self:
        return cls(root=category if comment is None else f"{category}({comment})")

    @property
    def category(self) -> LabelCategory:
        return LabelCategory(self.root.split("(")[0])

    @property
    def comment(self) -> str | None:
        parts = self.root.split("(", 1)
        if len(parts) > 1:
            return parts[1].rstrip(")")
        return None

    @staticmethod
    def priority(label: "Label") -> Any:
        """Returns a sorting key for this label when sorting for human presentation."""
        return list(LabelCategory).index(label.category), label.root


class TestsSummary(BaseModel):
    passed: int
    failed: int
    skipped: int
    ignored: int

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.ignored


class Analyses(BaseModel):
    labels: list[Label] | None = None
    tests_summary: TestsSummary | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, nxt: SerializerFunctionWrapHandler):
        return {k: v for k, v in nxt(self).items() if v is not None}

    def has_label_category(self, category: LabelCategory) -> bool:
        if self.labels is None:
            return False

        return any(label.category == category for label in self.labels)

    def label_by_category(self, category: LabelCategory) -> Label | None:
        if self.labels is None:
            return None
        for label in self.labels:
            if label.category == category:
                return label
        return None


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

    @property
    def was_executed(self) -> bool:
        return self.exit_code is not None and self.exit_code != EXIT_RUNNER_SKIPPED


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

    def tests_with_label_category(self, category: LabelCategory) -> list[TestReport]:
        return [
            test for test in self.tests if test.analyses.has_label_category(category)
        ]


class ReportMeta(BaseModel):
    """Some metadata about the report file itself."""

    name: str

    @classmethod
    def new(cls, path: Path) -> Self:
        return cls(name=path.stem)
