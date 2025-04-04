from typing import Iterable

from rich.console import Console
from rich.progress import track

from maat.model import Analyser, Report, StepMeta, StepReport, TestReport


def analyse_report(report: Report, console: Console):
    for analyser, args in track(
        list(_collect_analysis_jobs(report)),
        console=console,
        description="Analysing results...",
        transient=True,
    ):
        analyser(*args)


def _collect_analysis_jobs(
    report: Report,
) -> Iterable[tuple[Analyser, tuple[TestReport, StepReport]]]:
    for test in report.tests:
        for step in test.steps:
            step_meta = StepMeta.by_name(step.name)
            if step_meta is not None and step_meta.analysers is not None:
                for analyser in step_meta.analysers():
                    yield analyser, (test, step)
