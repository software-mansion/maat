import enum
from collections.abc import MutableSet
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    RootModel,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from maat.installation import REPO, this_maat_commit
from maat.utils.shell import join_command, inline_env, add_workdir
from maat.utils.smart_sort import smart_sort_key

type Semver = str
type ImageId = str

type Analyser = Callable[[TestReport], None]
type Severity = Literal["error", "warn"]

EXIT_RUNNER_SKIPPED = -1
"""Exit code set for steps which were skipped by the runner."""


class Step(BaseModel):
    run: str | list[str]
    name: str = Field(default_factory=lambda data: join_command(data["run"]))
    setup: bool = False
    """
    Setup steps halt test on failure and progress bars behaves differently for these.
    """
    checkout: bool = Field(default_factory=lambda data: data["setup"])
    """
    Whether this step is executed as part of checkout command.
    """
    env: dict[str, str] = {}
    """
    Environment variables to be set for this step.
    """
    workdir: str | None = None
    """
    Working directory for this step. If None, the default working directory is used.
    """

    @model_serializer(mode="wrap")
    def serialize_model(self, nxt: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Skip serialising fields which aren't required and have default values."""

        data = nxt(self)
        model_fields = self.__class__.model_fields

        return {
            k: v
            for k, v in data.items()
            if model_fields[k].is_required()
            or v
            != model_fields[k].get_default(
                call_default_factory=True,
                validated_data=data,
            )
        }


class Test(BaseModel):
    name: str
    rev: str
    steps: list[Step]


class TestSuite(BaseModel):
    tests: list[Test] = []

    def test_by_name(self, name: str) -> Test | None:
        for test in self.tests:
            if test.name == name:
                return test
        return None

    def partition(self, n: int) -> list[Self]:
        assert n > 0

        if n == 1:
            return [self]

        buckets: list[list[Test]] = [[] for _ in range(n)]
        for idx, test in enumerate(self.tests):
            buckets[idx % n].append(test)
        return [self.__class__(tests=bucket) for bucket in buckets]


@enum.unique
class LabelCategory(enum.StrEnum):
    # NOTE: If adding a new category, remember to add new CSS styles associated with it.

    # The higher the category here, the higher the priority when sorting for human presentation.
    ERROR = "error"
    BUILD_FAIL = "build-fail"
    TEST_FAIL = "test-fail"
    TEST_PASS = "test-pass"
    LINT_FAIL = "lint-fail"
    LS_FAIL = "ls-fail"
    BROKEN = "broken"
    LINT_BROKEN = "lint-broken"
    LS_BROKEN = "ls-broken"

    @enum.property
    def help(self) -> str:
        return {
            self.ERROR: "A serious error occurred before project could be built.",
            self.BUILD_FAIL: "Build failed.",
            self.TEST_FAIL: "Build succeeded but tests failed.",
            self.TEST_PASS: 'Build succeeded and tests passed. This is the "clean" state.',
            self.LINT_FAIL: "Build succeeded but linting failed. Take these results with grain of salt because cairo-lint is not reliable.",
            self.LS_FAIL: 'Build succeeded but CairoLS reports errors or vice versa. We expect CairoLS to produce same diagnostics as "scarb build".',
            self.BROKEN: "Something is broken in a known way for this project in Ma'at context, this should be probably ignored.",
            self.LINT_BROKEN: "Linting is broken in a known way for this project in Ma'at context, this should be probably ignored.",
            self.LS_BROKEN: "CairoLS is broken in a known way for this project in Ma'at context, this should be probably ignored.",
        }[self]


_label_category_regex = "|".join(LabelCategory.__members__.values())


class Label(RootModel):
    root: str = Field(pattern=rf"^(?:{_label_category_regex})(?:\([^()]+\))?$")

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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.root})"

    def __str__(self) -> str:
        return self.root


class TestsSummary(BaseModel):
    passed: int
    failed: int
    skipped: int
    ignored: int

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.ignored


class Labels(MutableSet[Label], RootModel):
    root: list[Label] = Field(default_factory=list)

    def __contains__(self, item: Label | LabelCategory) -> bool:
        if isinstance(item, LabelCategory):
            return any(label.category == item for label in self.root)

        return item in self.root

    def __iter__(self) -> Iterator[Label]:
        return iter(self.root)

    def add(self, label: Label):
        self.root.append(label)
        self.root.sort(key=Label.priority)

    def discard(self, label: Label):
        if label in self.root:
            self.root.remove(label)

    def __len__(self):
        return len(self.root)

    def prioritize(self, category: LabelCategory) -> list[Label]:
        """
        Returns a new list of labels with the given category's labels first.
        """
        new = list(self)
        new.sort(key=lambda label: label.category != category)
        return new

    def __repr__(self):
        return f"{self.__class__.__name__}[{', '.join(map(str, self.root))}]"

    def __str__(self):
        return f"[{', '.join(map(str, self.root))}]"


class Analyses(BaseModel):
    labels: Labels | None = None
    tests_summary: TestsSummary | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, nxt: SerializerFunctionWrapHandler):
        return {k: v for k, v in nxt(self).items() if v is not None}


class StepReport(BaseModel):
    name: str
    run: str
    exit_code: int | None
    execution_time: timedelta | None

    # This one is kept last because it takes significant chunks of view area.
    log: bytes | None = None

    @classmethod
    def blueprint(cls, step: Step):
        return cls(
            name=step.name,
            run=inline_env(join_command(step.run), add_workdir(step.env, step.workdir)),
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
    def by_version_preferring_scarb(self):
        return smart_sort_key(self.scarb), smart_sort_key(self.foundry)

    @property
    def by_version_preferring_foundry(self):
        return smart_sort_key(self.foundry), smart_sort_key(self.scarb)

    @model_validator(mode="after")
    def validate_unique_test_names(self) -> Self:
        test_names = [test.name for test in self.tests]
        if len(test_names) != len(set(test_names)):
            duplicates = [
                name for name in set(test_names) if test_names.count(name) > 1
            ]
            duplicates.sort()
            limit = 3
            if len(duplicates) > limit:
                msg = f"duplicate tests found: {', '.join(duplicates[:limit])} ({len(duplicates) - limit} more)"
            else:
                msg = f"duplicate tests found: {', '.join(duplicates)}"
            raise ValueError(msg)
        return self

    @classmethod
    def merge(cls, reports: list[Self]) -> Self:
        assert len(reports) > 0

        for field in ["workspace", "scarb", "foundry", "maat_commit"]:
            if not all(
                getattr(r, field) == getattr(reports[0], field) for r in reports
            ):
                raise ValueError(f"cannot merge reports with varying '{field}' values")

        return Report(
            workspace=reports[0].workspace,
            scarb=reports[0].scarb,
            foundry=reports[0].foundry,
            maat_commit=reports[0].maat_commit,
            created_at=max(r.created_at for r in reports),
            total_execution_time=sum(
                (r.total_execution_time for r in reports), timedelta()
            ),
            tests=[t for r in reports for t in r.tests],
        )

    def before_save(self):
        """
        Perform some cleaning up before saving the report.

        This method mutates the report object in place.
        """
        self.tests.sort(key=lambda t: t.name)

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


class Plan(BaseModel):
    workspace: str
    scarb: Semver
    foundry: Semver

    report_name: str
    sandbox: str

    partitions: list[TestSuite]

    def partition_views(self) -> list["PlanPartitionView"]:
        return [
            PlanPartitionView(plan=self, partition=i)
            for i in range(len(self.partitions))
        ]

    def report_path(
        self,
        base: Path | str | None = None,
        partition: int | None = None,
    ) -> Path:
        if base is None:
            base = REPO / "reports"
        base = Path(base)

        if partition is not None:
            file_name = f"{self.report_name}-{partition}.json"
        else:
            file_name = f"{self.report_name}.json"

        return base / file_name


class PlanPartitionView(BaseModel):
    plan: Plan
    partition: int

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        assert 0 <= self.partition < len(self.plan.partitions), (
            "partition index out of range"
        )
        return self

    @property
    def test_suite(self) -> TestSuite:
        return self.plan.partitions[self.partition]


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    """Generate the path to the logs file for a given test."""
    return Path() / meta.name / test.name_and_rev / "logs.txt"
