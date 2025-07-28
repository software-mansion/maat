from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from maat.model import ReportMeta
from maat.report.metrics import Metrics
from maat.web.report_info import ReportInfo
from maat.web.slices import Slice

ViewModelConfig = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    alias_generator=to_camel,
)


class ReportViewModel(BaseModel):
    model_config = ViewModelConfig

    title: str
    ecosystem_csv_href: str
    ecosystem_json_href: str
    metrics: Metrics

    @classmethod
    def new(cls, report_info: ReportInfo) -> Self:
        return cls(
            title=report_info.meta.name,
            ecosystem_csv_href=str(ecosystem_csv_path(report_info.meta)),
            ecosystem_json_href=str(ecosystem_json_path(report_info.meta)),
            metrics=report_info.metrics,
        )


class SliceViewModel(BaseModel):
    model_config = ViewModelConfig

    title: str
    report_ids: list[int] = Field(min_length=1)
    default: bool = False

    @classmethod
    def new(cls, slice: Slice, reports: list[ReportInfo]) -> Self:
        return cls(
            title=slice.title,
            report_ids=[reports.index(r) for r in slice.reports],
            default=slice.default,
        )


class ViewModel(BaseModel):
    model_config = ViewModelConfig

    reports: list[ReportViewModel]
    slices: list[SliceViewModel]

    @classmethod
    def new(cls, reports: list[ReportInfo], slices: list[Slice]) -> Self:
        return cls(
            reports=[ReportViewModel.new(r) for r in reports],
            slices=[SliceViewModel.new(s, reports) for s in slices],
        )


archives_path = Path() / "archives"


def ecosystem_csv_path(meta: ReportMeta) -> Path:
    return archives_path / f"{meta.name}-ecosystem.csv"


def ecosystem_json_path(meta: ReportMeta) -> Path:
    return archives_path / f"{meta.name}-ecosystem.json"
