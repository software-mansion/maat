import importlib.resources
import shutil
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterator

import jinja2

from maat.model import Report, ReportMeta
from maat.report.metrics import Metrics
from maat.web import filters
from maat.web.view_model import build_view_model, logs_txt_path


def build(reports: list[tuple[Report, ReportMeta]], output: Path):
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    reports = [
        (
            report,
            meta,
            Metrics.compute(report, meta),
        )
        for report, meta in reports
    ]

    _copy_traversable(importlib.resources.files("maat.web.resources"), output)
    _write_logs(reports, output)

    vm = build_view_model(reports)
    with _jinja_env() as env:
        index_html = env.get_template("index.html").render(**vm.model_dump())
        (output / "index.html").write_text(index_html, encoding="utf-8")


@contextmanager
def _jinja_env() -> Iterator[jinja2.Environment]:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("maat.web", "templates"),
        autoescape=jinja2.select_autoescape(),
        undefined=jinja2.StrictUndefined,
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


def _write_logs(reports: list[tuple[Report, ReportMeta, Metrics]], output: Path):
    for report, meta, _ in reports:
        for test in report.tests:
            log_file = output / logs_txt_path(meta, test)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_bytes(test.combined_log())
