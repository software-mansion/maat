import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import jinja2
from pydantic import BaseModel

from maat.report.metrics import Metrics
from maat.utils.smart_sort import smart_sort_key


def render_html(metrics: list[Metrics]) -> Path:
    view_model = _build_view_model(metrics)

    with _jinja_env() as env:
        template = env.get_template("index.html")
        html = template.render(**view_model.model_dump())
        return _save_html_as_temp_file(html)


class CellViewModel(BaseModel):
    value: str
    class_name: str | None = None


class RowViewModel(BaseModel):
    title: str
    cells: list[CellViewModel]


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
        RowViewModel(
            title="Workspace",
            cells=[CellViewModel(value=str(metric.workspace)) for metric in metrics],
        ),
        RowViewModel(
            title="Scarb Version",
            cells=[
                CellViewModel(value=str(metric.scarb_version)) for metric in metrics
            ],
        ),
        RowViewModel(
            title="Foundry Version",
            cells=[
                CellViewModel(value=str(metric.foundry_version)) for metric in metrics
            ],
        ),
        RowViewModel(
            title="Ma'at Commit",
            cells=[CellViewModel(value=str(metric.maat_commit)) for metric in metrics],
        ),
        RowViewModel(
            title="Created At",
            cells=[
                CellViewModel(value=metric.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                for metric in metrics
            ],
        ),
        RowViewModel(
            title="Total Execution Time",
            cells=[
                CellViewModel(value=str(metric.total_execution_time))
                for metric in metrics
            ],
        ),
    ]
    sections.append(SectionViewModel(title="Metadata", rows=metadata_rows))

    # Time metrics section
    time_rows = [
        RowViewModel(
            title="Avg. Build Time",
            cells=[
                CellViewModel(value=str(metric.avg_build_time)) for metric in metrics
            ],
        ),
        RowViewModel(
            title="Avg. Lint Time",
            cells=[
                CellViewModel(value=str(metric.avg_lint_time)) for metric in metrics
            ],
        ),
        RowViewModel(
            title="Avg. Test Time",
            cells=[
                CellViewModel(value=str(metric.avg_test_time)) for metric in metrics
            ],
        ),
    ]
    sections.append(SectionViewModel(title="Time Metrics", rows=time_rows))

    # Build metrics section
    build_rows = [
        RowViewModel(
            title="Clean Builds",
            cells=[CellViewModel(value=str(metric.clean_builds)) for metric in metrics],
        ),
        RowViewModel(
            title="Dirty Builds",
            cells=[CellViewModel(value=str(metric.dirty_builds)) for metric in metrics],
        ),
        RowViewModel(
            title="Avg. Warnings in Dirty Build",
            cells=[
                CellViewModel(value=f"{metric.avg_warnings_in_dirty_build:.1f}")
                for metric in metrics
            ],
        ),
        RowViewModel(
            title="Avg. Errors in Dirty Build",
            cells=[
                CellViewModel(value=f"{metric.avg_errors_in_dirty_build:.1f}")
                for metric in metrics
            ],
        ),
    ]
    sections.append(SectionViewModel(title="Build Metrics", rows=build_rows))

    # Lint metrics section
    lint_rows = [
        RowViewModel(
            title="Clean Lints",
            cells=[CellViewModel(value=str(metric.clean_lints)) for metric in metrics],
        ),
        RowViewModel(
            title="Dirty Lints",
            cells=[CellViewModel(value=str(metric.dirty_lints)) for metric in metrics],
        ),
    ]
    sections.append(SectionViewModel(title="Lint Metrics", rows=lint_rows))

    # Test metrics section
    test_rows = [
        RowViewModel(
            title="Clean Tests",
            cells=[CellViewModel(value=str(metric.clean_tests)) for metric in metrics],
        ),
        RowViewModel(
            title="Dirty Tests",
            cells=[CellViewModel(value=str(metric.dirty_tests)) for metric in metrics],
        ),
        RowViewModel(
            title="Failed Tests Ratio",
            cells=[
                CellViewModel(value=str(metric.failed_tests_ratio))
                for metric in metrics
            ],
        ),
    ]
    sections.append(SectionViewModel(title="Test Metrics", rows=test_rows))

    # Other metrics section
    other_rows = [
        RowViewModel(
            title="Total Compiled Proc Macros",
            cells=[
                CellViewModel(value=str(len(metric.compiled_procmacros_from_source)))
                for metric in metrics
            ],
        ),
    ]
    sections.append(SectionViewModel(title="Other Metrics", rows=other_rows))

    return RootViewModel(column_titles=column_titles, sections=sections)


@contextmanager
def _jinja_env() -> Iterator[jinja2.Environment]:
    yield jinja2.Environment(
        loader=jinja2.PackageLoader("maat.report"),
        autoescape=jinja2.select_autoescape(),
    )


def _save_html_as_temp_file(html: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
        temp_file.write(html.encode("utf-8"))
        return Path(temp_file.name)
