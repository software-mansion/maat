"""
Human-maintained list of known issues (``known_issues.toml`` at the repo root).

Matching is deterministic (shell-style globs), so a known issue never depends on the LLM
noticing it. The LLM is told which failures matched and may propose new entries.
"""

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

import tomlkit
from pydantic import BaseModel

from maat.installation import REPO

KNOWN_ISSUES_PATH = REPO / "known_issues.toml"


class KnownIssue(BaseModel):
    id: str
    projects: list[str]
    """Glob patterns matched against project names."""
    labels: list[str] = ["*"]
    """
    Glob patterns matched against label strings, e.g. ``build-fail*``. Omitted: any label.
    An explicit empty list matches no failures (useful for performance-only entries).
    """
    scope: Literal["failures", "performance", "all"] = "failures"
    """
    ``failures``: matching failures are marked known and stop counting as news.
    ``performance``: matching projects are excluded from performance aggregates (their own
    numbers are still shown separately). ``all``: both.
    """
    note: str
    link: str | None = None

    def matches_project(self, project: str) -> bool:
        return any(fnmatchcase(project, p) for p in self.projects)

    def matches(self, project: str, labels: list[str]) -> bool:
        if self.scope == "performance" or not self.matches_project(project):
            return False
        return any(fnmatchcase(lbl, pat) for lbl in labels for pat in self.labels)

    def covers_performance(self, project: str) -> bool:
        return self.scope in ("performance", "all") and self.matches_project(project)


def load_known_issues(path: Path = KNOWN_ISSUES_PATH) -> list[KnownIssue]:
    if not path.exists():
        return []
    doc = tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    return [KnownIssue.model_validate(item) for item in doc.get("issue", [])]


def match_known_issue(
    issues: list[KnownIssue], project: str, labels: list[str]
) -> KnownIssue | None:
    return next((i for i in issues if i.matches(project, labels)), None)
