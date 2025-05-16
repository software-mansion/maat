from pathlib import Path
from typing import IO, Self

from maat.model import Report


def read_report(path: Path) -> Report:
    return Report.model_validate_json(path.read_bytes())


def save_report(report: Report, output: Path | IO):
    report.before_save()
    json = report.model_dump_json(indent=2) + "\n"
    if isinstance(output, Path):
        output.write_text(json, encoding="utf-8")
    else:
        output.write(json)


class ReportEditor:
    def __init__(self, report: Report, path: Path):
        self.report = report
        self.path = path

    @classmethod
    def read(cls, path: Path) -> Self:
        report = read_report(path)
        return cls(report=report, path=path)

    def save(self):
        return save_report(self.report, self.path)
