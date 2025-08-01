import csv
import json
import shutil
from pathlib import Path

from maat.model import Report, ReportMeta
from maat.report.metrics import Metrics
from maat.utils.smart_sort import smart_sort_key
from maat.web.report_info import ReportInfo
from maat.web.slices import make_slices
from maat.web.view_model import (
    ViewModel,
    archives_path,
    ecosystem_csv_path,
    ecosystem_json_path,
    logs_txt_path,
)


def export_assets(
    reports: list[tuple[Report, ReportMeta]], view_model_path: Path, assets_path: Path
):
    view_model_path.parent.mkdir(parents=True, exist_ok=True)

    if assets_path.exists():
        shutil.rmtree(assets_path)
    assets_path.mkdir(parents=True, exist_ok=True)

    reports.sort(key=lambda t: smart_sort_key(t[1].name))

    reports = [
        ReportInfo(
            report=report,
            meta=meta,
            metrics=Metrics.compute(report, meta),
        )
        for report, meta in reports
    ]

    _write_logs(reports, assets_path)
    _write_archives(reports, assets_path)

    sls = make_slices(reports)

    vm = ViewModel.new(reports, sls)

    view_model_path.write_text(
        vm.model_dump_json(indent=2, by_alias=True), encoding="utf-8"
    )


def _write_logs(reports: list[ReportInfo], output: Path):
    for report, meta, _ in reports:
        for test in report.tests:
            log_file = output / logs_txt_path(meta, test)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_bytes(test.combined_log())


def _write_archives(reports: list[ReportInfo], output: Path):
    # Ensure the archives directory exists.
    (output / archives_path).mkdir(parents=True, exist_ok=True)

    for report, meta, _ in reports:
        ecosystem = [
            {"project": test.name, "revision": test.rev} for test in report.tests
        ]

        # Create the ecosystem CSV archive.
        with open(
            output / ecosystem_csv_path(meta), "w", newline="", encoding="utf-8"
        ) as f:
            if ecosystem:
                writer = csv.DictWriter(f, fieldnames=ecosystem[0].keys())
                writer.writeheader()
                writer.writerows(ecosystem)

        # Create the JSON archive.
        with open(output / ecosystem_json_path(meta), "w", encoding="utf-8") as f:
            json.dump(ecosystem, f)
