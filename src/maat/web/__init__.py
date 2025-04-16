import importlib.resources
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterator

import jinja2
from pydantic import BaseModel

from maat.model import Report, ReportMeta
from maat.report.metrics import Metrics, MetricsTransposed
from maat.utils.smart_sort import smart_sort_key
from maat.web import filters


def build(reports: list[tuple[Report, ReportMeta]], output: Path):
    metrics = [Metrics.compute(report, meta) for report, meta in reports]

    _copy_traversable(importlib.resources.files("maat.web.resources"), output)

    view_model = _build_view_model(metrics)

    with _jinja_env() as env:
        index_html = env.get_template("index.html").render(**view_model.model_dump())
        (output / "index.html").write_text(index_html, encoding="utf-8")


class RootViewModel(BaseModel):
    report_names: list[str]
    metrics: MetricsTransposed


def _build_view_model(metrics: list[Metrics]) -> RootViewModel:
    # Sort and transpose columns.
    metrics.sort(key=lambda m: smart_sort_key(m.meta.name))
    metrics_transposed = MetricsTransposed.new(metrics)

    report_names = [m.name for m in metrics_transposed.meta]

    return RootViewModel(report_names=report_names, metrics=metrics_transposed)


@contextmanager
def _jinja_env() -> Iterator[jinja2.Environment]:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("maat.web", "templates"),
        autoescape=jinja2.select_autoescape(),
    )

    # Create a dictionary of filter functions from the filters module
    env.filters.update(
        {
            name: getattr(filters, name)
            for name in dir(filters)
            if not name.startswith("_") and callable(getattr(filters, name))
        }
    )

    yield env


def _copy_traversable(traversable: Traversable, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for child in traversable.iterdir():
        if child.is_dir():
            _copy_traversable(child, dest / child.name)
        else:
            dest_child = dest / child.name
            dest_child.write_bytes(child.read_bytes())
