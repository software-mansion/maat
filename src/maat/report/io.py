from pathlib import Path
from typing import Self

from maat.installation import REPO
from maat.model import Report
from maat.workspace import Workspace


def _read_report(path: Path) -> Report:
    return Report.model_validate_json(path.read_bytes())


def _save_report(report: Report, path: Path):
    report.before_save()
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


class ReportCreator:
    def __init__(self, workspace: Workspace):
        self._workspace = workspace

    def save(self, report: Report):
        report_name = self._workspace.settings.generate_report_name(report)
        path = REPO / "reports" / f"{report_name}.json"
        _save_report(report, path)


class ReportEditor:
    def __init__(self, report: Report, path: Path):
        self.report = report
        self.path = path

    @classmethod
    def read(cls, path: Path) -> Self:
        report = _read_report(path)
        return cls(report=report, path=path)

    def save(self):
        return _save_report(self.report, self.path)
