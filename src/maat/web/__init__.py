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
from maat.web.report_info import ReportInfo
from maat.web.slices import make_slices
from maat.web.view_model import build_view_model, logs_txt_path


def build(reports: list[tuple[Report, ReportMeta]], output: Path):
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    reports.sort(key=lambda t: smart_sort_key(t[1].name))

    reports = [
        ReportInfo(
            report=report,
            meta=meta,
            metrics=Metrics.compute(report, meta),
        )
        for report, meta in reports
    ]

    _copy_traversable(
        importlib.resources.files("maat.web.templates._assets"),
        output / "_assets",
    )
    _write_logs(reports, output)

    sls = make_slices(reports)
    for slice_idx, sl in enumerate(sls):
        for report_idx, reference_report in enumerate(sl.reports):
            vm = build_view_model(
                sl.reports,
                reference_report_idx=report_idx,
                slices=sls,
                curr_slice_idx=slice_idx,
            )

            with _jinja_env() as env:
                _render_to(
                    template="index.html",
                    vm=vm,
                    path=output / vm.report_names[report_idx].pivot_href,
                    env=env,
                )


@contextmanager
def _jinja_env() -> Iterator[jinja2.Environment]:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("maat.web", "templates"),
        autoescape=jinja2.select_autoescape(),
        undefined=jinja2.StrictUndefined,
    )

    env.globals["len"] = len
    env.globals["round"] = round
    env.globals["zip"] = zip

    # Create a dictionary of filter functions from the filters module
    env.filters.update(
        {
            name: getattr(filters, name)
            for name in dir(filters)
            if not name.startswith("_") and callable(getattr(filters, name))
        }
    )

    yield env


def _render_to(
    template: str,
    vm: BaseModel,
    path: Path,
    env: jinja2.Environment,
):
    template = env.get_template(template)
    rendered = template.render(**dict(vm))
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
    for report, meta, _ in reports:
        for test in report.tests:
            log_file = output / logs_txt_path(meta, test)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_bytes(test.combined_log())
