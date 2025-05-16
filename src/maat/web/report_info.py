from typing import NamedTuple

from maat.model import Report, ReportMeta
from maat.report.metrics import Metrics


class ReportInfo(NamedTuple):
    report: Report
    meta: ReportMeta
    metrics: Metrics
