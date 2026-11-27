"""
Human-maintained list of known issues (``known_issues.toml`` at the repo root).

Matching is deterministic (shell-style globs), so a known issue never depends on the LLM
noticing it. The LLM is told which failures matched and may propose new entries.
"""

from fnmatch import fnmatchcase
from pathlib import Path
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
    """
    note: str
    link: str | None = None

    def matches_project(self, project: str) -> bool:
        return any(fnmatchcase(project, p) for p in self.projects)

    def matches(self, project: str, labels: list[str]) -> bool:
        if not self.matches_project(project):
            return False
        return any(fnmatchcase(lbl, pat) for lbl in labels for pat in self.labels)


def load_known_issues(path: Path = KNOWN_ISSUES_PATH) -> list[KnownIssue]:
    if not path.exists():
        return []
    doc = tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    return [KnownIssue.model_validate(item) for item in doc.get("issue", [])]


def match_known_issue(
    issues: list[KnownIssue], project: str, labels: list[str]
) -> KnownIssue | None:
    return next((i for i in issues if i.matches(project, labels)), None)
