import importlib.resources
import shutil
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterator

import jinja2
import minify_html
from pydantic import BaseModel

from maat.model import Report, ReportMeta
from maat.report.metrics import Metrics
from maat.utils.smart_sort import smart_sort_key
from maat.web import filters
from maat.web.view_model import ReportInfo, build_view_model, logs_txt_path


def build(reports: list[tuple[Report, ReportMeta]], output: Path):
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    reports.sort(key=lambda t: smart_sort_key(t[1].name))

    # NOTE: The last report will be the reference, and thus it will be rendered as index.html.
    reports = [
        ReportInfo(
            report=report,
            meta=meta,
            metrics=Metrics.compute(report, meta),
            pivot_path=pivot_path,
        )
        for (report, meta), pivot_path in zip(reports, _pivot_paths(reports))
    ]

    _copy_traversable(
        importlib.resources.files("maat.web.templates._assets"),
        output / "_assets",
    )
    _write_logs(reports, output)

    for i, reference_report in enumerate(reports):
        vm = build_view_model(reports, reference_report_idx=i)
        with _jinja_env() as env:
            _render_to(
                template="index.html",
                vm=vm,
                path=output / reference_report.pivot_path,
                env=env,
            )


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


def _pivot_paths(iterable: list) -> Iterator[str]:
    for i in range(len(iterable)):
        if i < len(iterable) - 1:
            yield f"pivot-{i}.html"
        else:
            yield "index.html"


def _render_to(
    template: str,
    vm: BaseModel,
    path: Path,
    env: jinja2.Environment,
):
    template = env.get_template(template)
    rendered = template.render(**vm.model_dump())
    minified = minify_html.minify(
        rendered,
        # These two keep `npx live-server` working, which is useful in development.
        keep_html_and_head_opening_tags=True,
        keep_closing_tags=True,
        minify_js=True,
    )
    path.write_text(minified, encoding="utf-8")


def _copy_traversable(traversable: Traversable, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for child in traversable.iterdir():
        if child.is_dir():
            _copy_traversable(child, dest / child.name)
        else:
            dest_child = dest / child.name
            dest_child.write_bytes(child.read_bytes())


def _write_logs(reports: list[ReportInfo], output: Path):
    for report, meta, _, _ in reports:
        for test in report.tests:
            log_file = output / logs_txt_path(meta, test)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_bytes(test.combined_log())
