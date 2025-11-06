from datetime import timedelta
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from maat.model import Label, LabelCategory, ReportMeta, StepReport, TestReport
from maat.report.metrics import Metrics
from maat.web.report_info import ReportInfo
from maat.web.slices import Slice

type ReportTitle = str
type SliceTitle = str

ViewModelConfig = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    alias_generator=to_camel,
)


class MetricsViewModel(Metrics):
    model_config = ViewModelConfig

    @classmethod
    def new(cls, metrics: Metrics) -> Self:
        return cls(**metrics.model_dump())


class LabelViewModel(BaseModel):
    model_config = ViewModelConfig

    category: LabelCategory
    comment: str | None

    @classmethod
    def new(cls, label: Label) -> Self:
        return cls(
            category=label.category,
            comment=label.comment,
        )


class StepViewModel(BaseModel):
    model_config = ViewModelConfig

    execution_time: timedelta | None
    exit_code: int | None

    @classmethod
    def new(cls, step: StepReport) -> Self:
        return cls(
            execution_time=step.execution_time,
            exit_code=step.exit_code,
        )


class TestViewModel(BaseModel):
    model_config = ViewModelConfig

    name: str
    rev: str
    labels: list[LabelViewModel]
    logs_href: str
    test_runner: Literal["snforge", "cairo-test"] | None

    build: StepViewModel | None
    test: StepViewModel | None
    lint: StepViewModel | None
    ls: StepViewModel | None

    @classmethod
    def new(cls, test: TestReport, report_meta: ReportMeta) -> Self:
        return cls(
            name=test.name,
            rev=test.rev,
            labels=[LabelViewModel.new(label) for label in test.analyses.labels],
            logs_href=str(logs_txt_path(report_meta, test)),
            test_runner=test.analyses.test_runner,
            build=(step := test.step("build")) and StepViewModel.new(step),
            test=(step := test.step("test")) and StepViewModel.new(step),
            lint=(step := test.step("lint")) and StepViewModel.new(step),
            ls=(step := test.step("ls")) and StepViewModel.new(step),
        )


class ReportViewModel(BaseModel):
    model_config = ViewModelConfig

    title: ReportTitle
    ecosystem_csv_href: str
    ecosystem_json_href: str
    metrics: MetricsViewModel
    tests: list[TestViewModel]

    @classmethod
    def new(cls, report_info: ReportInfo) -> Self:
        return cls(
            title=report_info.meta.name,
            ecosystem_csv_href=str(ecosystem_csv_path(report_info.meta)),
            ecosystem_json_href=str(ecosystem_json_path(report_info.meta)),
            metrics=MetricsViewModel.new(report_info.metrics),
            tests=[
                TestViewModel.new(t, report_info.meta) for t in report_info.report.tests
            ],
        )


class SliceViewModel(BaseModel):
    model_config = ViewModelConfig

    title: SliceTitle
    reports: list[ReportTitle] = Field(min_length=1)
    default: bool = False

    @classmethod
    def new(cls, slice: Slice) -> Self:
        return cls(
            title=slice.title,
            reports=[r.meta.name for r in slice.reports],
            default=slice.default,
        )


class ViewModel(BaseModel):
    model_config = ViewModelConfig

    reports: dict[str, ReportViewModel]
    slices: dict[str, SliceViewModel]
    label_categories: list[LabelCategory]

    @classmethod
    def new(cls, reports: list[ReportInfo], slices: list[Slice]) -> Self:
        return cls(
            reports={r.meta.name: ReportViewModel.new(r) for r in reports},
            slices={s.title: SliceViewModel.new(s) for s in slices},
            label_categories=list(LabelCategory),
        )


def logs_txt_path(meta: ReportMeta, test: TestReport) -> Path:
    return Path() / meta.name / test.name_and_rev / "logs.txt"


archives_path = Path() / "archives"


def ecosystem_csv_path(meta: ReportMeta) -> Path:
    return archives_path / f"{meta.name}-ecosystem.csv"


def ecosystem_json_path(meta: ReportMeta) -> Path:
    return archives_path / f"{meta.name}-ecosystem.json"
