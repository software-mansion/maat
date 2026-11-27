from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from maat.triage.changelog import ToolChangelog
from maat.triage.diff import ReportDiff
from maat.triage.pivot import Pivot

type Status = Literal["green", "amber", "red"]


# --- Persisted analysis ----------------------------------------------------------------------


class Analysis(BaseModel):
    report: str
    generated_at: datetime
    target_versions: dict[str, str]
    pivots: list[Pivot]
    diffs: list[ReportDiff]
    changelogs: list[ToolChangelog]
    """Changelog against the primary pivot."""
    status: Status
    status_notes: list[str] = []
    """Why the status is what it is, when that isn't obvious from the diff."""
    headline: str
    rerun_command: str
    run_url: str | None = None

    @property
    def primary(self) -> ReportDiff | None:
        return self.diffs[0] if self.diffs else None
