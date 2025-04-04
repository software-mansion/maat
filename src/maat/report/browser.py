import tempfile
from collections.abc import Sized
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator, Self

import jinja2
from pydantic import BaseModel

from maat.report.metrics import Metrics
from maat.utils.smart_sort import smart_sort_key
from maat.utils.templating import clsx


def render_html(metrics: list[Metrics]) -> Path:
    view_model = _build_view_model(metrics)

    with _jinja_env() as env:
        template = env.get_template("index.html")
        html = template.render(**view_model.model_dump())
        return _save_html_as_temp_file(html)


class CellViewModel(BaseModel):
    value: str
    class_name: str | None = None

    @classmethod
    def new(
        cls, value: Any, *, class_name: str | None = None, float_precision: int = 2
    ) -> Self:
        s: str
        match value:
            case datetime():
                s = value.strftime("%Y-%m-%d %H:%M:%S")
            case timedelta():
                mm, ss = divmod(value.seconds, 60)
                hh, mm = divmod(mm, 60)
                s = "%d:%02d:%02d" % (hh, mm, ss)
                if value.days:

                    def plural(n):
                        return n, abs(n) != 1 and "s" or ""

                    s = ("%d day%s, " % plural(value.days)) + s
                if value.microseconds:
                    # Round to the nearest 1/(10**float_precision)th of a second.
                    # For example, 0:07:12.211526 -> 0:07:12.21 (when float_precision = 2).
                    ms = round(value.microseconds / 10**6, float_precision)
                    # Add fractional seconds, omit leading `0` with that `[1:]`.
                    s += f"{ms:.{float_precision}f}"[1:]
            case float():
                s = f"{value:.{float_precision}f}"
            case _:
                s = str(value)

        return cls(
            value=s,
            class_name=clsx(
                f"type-{type(value).__name__.split('.')[-1]}",
                class_name,
            ),
        )

    @classmethod
    def len(cls, iterable: Sized, **kwargs) -> Self:
        return cls.new(len(iterable), **kwargs)


class RowViewModel(BaseModel):
    title: str
    cells: list[CellViewModel]

    @classmethod
    def map(
        cls,
        title: str,
        cells: Iterator[Any],
        func: Callable[[Any], CellViewModel] = CellViewModel.new,
    ) -> Self:
        return cls(title=title, cells=[func(val) for val in cells])


class SectionViewModel(BaseModel):
    title: str
    rows: list[RowViewModel]


class RootViewModel(BaseModel):
    column_titles: list[str]
    sections: list[SectionViewModel]


def _build_view_model(metrics: list[Metrics]) -> RootViewModel:
    # Sort columns
    metrics.sort(key=lambda m: smart_sort_key(m.file_stem))

    # Create column titles from file_stem of each metrics object
    column_titles = [metric.file_stem for metric in metrics]

    # Create sections for different categories of metrics
    sections = []

    # Metadata section
    metadata_rows = [
        RowViewModel.map("Workspace", (metric.workspace for metric in metrics)),
        RowViewModel.map("Scarb Version", (metric.scarb_version for metric in metrics)),
        RowViewModel.map(
            "Foundry Version", (metric.foundry_version for metric in metrics)
        ),
        RowViewModel.map("Ma'at Commit", (metric.maat_commit for metric in metrics)),
        RowViewModel.map("Created At", (metric.created_at for metric in metrics)),
        RowViewModel.map(
            "Total Execution Time", (metric.total_execution_time for metric in metrics)
        ),
    ]
    sections.append(SectionViewModel(title="Metadata", rows=metadata_rows))

    # Time metrics section
    time_rows = [
        RowViewModel.map(
            "Avg. Build Time", (metric.avg_build_time for metric in metrics)
        ),
        RowViewModel.map(
            "Avg. Lint Time", (metric.avg_lint_time for metric in metrics)
        ),
        RowViewModel.map(
            "Avg. Test Time", (metric.avg_test_time for metric in metrics)
        ),
    ]
    sections.append(SectionViewModel(title="Time Metrics", rows=time_rows))

    # Build metrics section
    build_rows = [
        RowViewModel.map("Clean Builds", (metric.clean_builds for metric in metrics)),
        RowViewModel.map("Dirty Builds", (metric.dirty_builds for metric in metrics)),
        RowViewModel.map(
            "Avg. Warnings in Dirty Build",
            (metric.avg_warnings_in_dirty_build for metric in metrics),
            func=lambda val: CellViewModel.new(val, float_precision=1),
        ),
        RowViewModel.map(
            "Avg. Errors in Dirty Build",
            (metric.avg_errors_in_dirty_build for metric in metrics),
            func=lambda val: CellViewModel.new(val, float_precision=1),
        ),
    ]
    sections.append(SectionViewModel(title="Build Metrics", rows=build_rows))

    # Lint metrics section
    lint_rows = [
        RowViewModel.map("Clean Lints", (metric.clean_lints for metric in metrics)),
        RowViewModel.map("Dirty Lints", (metric.dirty_lints for metric in metrics)),
    ]
    sections.append(SectionViewModel(title="Lint Metrics", rows=lint_rows))

    # Test metrics section
    test_rows = [
        RowViewModel.map("Clean Tests", (metric.clean_tests for metric in metrics)),
        RowViewModel.map("Dirty Tests", (metric.dirty_tests for metric in metrics)),
        RowViewModel.map(
            "Failed Tests Ratio", (metric.failed_tests_ratio for metric in metrics)
        ),
    ]
    sections.append(SectionViewModel(title="Test Metrics", rows=test_rows))

    # Other metrics section
    other_rows = [
        RowViewModel.map(
            "Total Compiled Proc Macros",
            (metric.compiled_procmacros_from_source for metric in metrics),
            func=CellViewModel.len,
        ),
    ]
    sections.append(SectionViewModel(title="Other Metrics", rows=other_rows))

    return RootViewModel(column_titles=column_titles, sections=sections)


@contextmanager
def _jinja_env() -> Iterator[jinja2.Environment]:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("maat.report"),
        autoescape=jinja2.select_autoescape(),
    )
    env.filters["clsx"] = clsx
    yield env


def _save_html_as_temp_file(html: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
        temp_file.write(html.encode("utf-8"))
        return Path(temp_file.name)
