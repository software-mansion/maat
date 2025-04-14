import base64
import importlib.resources
import tempfile
from collections.abc import Sized
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Self

import jinja2
from pydantic import BaseModel, RootModel

from maat.model import ClassifiedDiagnostic
from maat.report.metrics import Metrics, MetricsTransposed
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

    @classmethod
    def name_count_dict(cls, d: dict[str, int], /):
        return cls.new(
            "\n".join(f"{count:4} {name}" for name, count in d.items()),
        )

    @classmethod
    def classified_diagnostic(cls, diag: ClassifiedDiagnostic) -> Self:
        return cls.new(
            "\n".join(f"{d.count:6} {d.severity.upper():5} {d.message}" for d in diag),
            class_name="classified-diagnostic",
        )


class DetailsViewModel(RootModel):
    root: list[CellViewModel]

    @classmethod
    def map(
        cls,
        cells: Iterable[Any],
        /,
        func: Callable[[Any], CellViewModel] = CellViewModel.new,
    ) -> Self:
        return cls(root=[func(val) for val in cells])


class RowViewModel(BaseModel):
    title: str
    cells: list[CellViewModel]
    details: DetailsViewModel | None = None

    @classmethod
    def map(
        cls,
        title: str,
        cells: Iterable[Any],
        /,
        func: Callable[[Any], CellViewModel] = CellViewModel.new,
        **kwargs,
    ) -> Self:
        return cls(title=title, cells=[func(val) for val in cells], **kwargs)


class SectionViewModel(BaseModel):
    title: str
    rows: list[RowViewModel]


class RootViewModel(BaseModel):
    column_titles: list[str]
    sections: list[SectionViewModel]


def _build_view_model(metrics: list[Metrics]) -> RootViewModel:
    # Sort and transpose columns.
    metrics.sort(key=lambda m: smart_sort_key(m.file_stem))
    t = MetricsTransposed.new(metrics)

    # Create column titles from file_stem of each metrics object.
    column_titles = t.file_stem

    # Create sections for different categories of metrics,
    sections = []

    # Metadata section
    metadata_rows = [
        RowViewModel.map("Workspace", t.workspace),
        RowViewModel.map("Scarb Version", t.scarb_version),
        RowViewModel.map("Foundry Version", t.foundry_version),
        RowViewModel.map("Ma'at Commit", t.maat_commit),
        RowViewModel.map("Created At", t.created_at),
        RowViewModel.map("Total Execution Time", t.total_execution_time),
        RowViewModel.map("Total Projects", t.total_projects),
    ]
    sections.append(SectionViewModel(title="Metadata", rows=metadata_rows))

    # Time metrics section.
    time_rows = [
        RowViewModel.map("Avg. Build Time", t.avg_build_time),
        RowViewModel.map("Avg. Lint Time", t.avg_lint_time),
        RowViewModel.map("Avg. Test Time", t.avg_test_time),
    ]
    sections.append(SectionViewModel(title="Time Metrics", rows=time_rows))

    # Build metrics section.
    build_rows = [
        RowViewModel.map("Clean Builds", t.clean_builds),
        RowViewModel.map(
            "Dirty Builds",
            t.dirty_builds,
            details=DetailsViewModel.map(
                t.build_diagnostics, func=CellViewModel.classified_diagnostic
            ),
        ),
        RowViewModel.map(
            "Avg. Warnings in Dirty Build",
            t.avg_warnings_in_dirty_build,
            func=lambda val: CellViewModel.new(val, float_precision=1),
        ),
        RowViewModel.map(
            "Avg. Errors in Dirty Build",
            t.avg_errors_in_dirty_build,
            func=lambda val: CellViewModel.new(val, float_precision=1),
        ),
    ]
    sections.append(SectionViewModel(title="Build Metrics", rows=build_rows))

    # Lint metrics section.
    lint_rows = [
        RowViewModel.map("Clean Lints", t.clean_lints),
        RowViewModel.map(
            "Dirty Lints",
            t.dirty_lints,
            details=DetailsViewModel.map(
                t.lint_diagnostics, func=CellViewModel.classified_diagnostic
            ),
        ),
    ]
    sections.append(SectionViewModel(title="Lint Metrics", rows=lint_rows))

    # Test metrics section.
    test_rows = [
        RowViewModel.map("Clean Tests", t.clean_tests),
        RowViewModel.map("Dirty Tests", t.dirty_tests),
        RowViewModel.map("Failed Tests Ratio", t.failed_tests_ratio),
    ]
    sections.append(SectionViewModel(title="Test Metrics", rows=test_rows))

    # All other metrics section.
    other_rows = [
        RowViewModel.map(
            "Total Compiled Proc Macros",
            t.compiled_procmacros_from_source,
            func=CellViewModel.len,
            details=DetailsViewModel.map(
                t.compiled_procmacros_from_source,
                func=CellViewModel.name_count_dict,
            ),
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

    # Get logo.png using importlib.resources and base64 encode it
    logo_data = (
        importlib.resources.files("maat.report")
        .joinpath("templates/logo.png")
        .read_bytes()
    )
    logo_base64 = base64.b64encode(logo_data).decode("utf-8")
    env.globals["logo_base64"] = f"data:image/png;base64,{logo_base64}"

    yield env


def _save_html_as_temp_file(html: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
        temp_file.write(html.encode("utf-8"))
        return Path(temp_file.name)
