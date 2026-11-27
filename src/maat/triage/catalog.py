"""
Inventory of all reports that can serve as pivots.

``gc-reports`` regularly prunes old reports from ``reports/``, so the catalog also looks
into git history and can load a deleted report from the commit preceding its deletion.
Only the report header is read when building the catalog; full reports are loaded lazily.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, field_validator

from maat.installation import REPO
from maat.model import Report
from maat.utils.log import log

_HEADER_BYTES = 4096
_HEADER_FIELDS = ("workspace", "scarb", "foundry", "maat_commit", "created_at")


class ReportHeader(BaseModel):
    workspace: str
    scarb: str
    foundry: str
    maat_commit: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        # Some old reports were written with naive timestamps.
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


@dataclass
class ReportRef:
    name: str
    header: ReportHeader
    path: Path | None = None
    """Path in the working tree, if the report is still there."""
    git_rev: str | None = None
    """Git revision where the report file exists (used for reports pruned by gc)."""
    _cache: Report | None = field(default=None, repr=False, compare=False)

    @property
    def in_tree(self) -> bool:
        return self.path is not None

    def load(self) -> Report:
        if self._cache is None:
            if self.path is not None:
                data = self.path.read_bytes()
            else:
                data = subprocess.check_output(
                    ["git", "show", f"{self.git_rev}:reports/{self.name}.json"],
                    cwd=REPO,
                )
            self._cache = Report.model_validate_json(data)
        return self._cache


def parse_header(head: bytes) -> ReportHeader | None:
    """Extract top-level scalar fields from the beginning of a report JSON file."""
    text = head.decode("utf-8", errors="replace")
    values = {}
    for name in _HEADER_FIELDS:
        m = re.search(rf'^\s*"{name}":\s*("(?:[^"\\]|\\.)*")', text, re.M)
        if not m:
            return None
        values[name] = json.loads(m.group(1))
    return ReportHeader.model_validate(values)


def ref_for_path(path: Path) -> ReportRef:
    with path.open("rb") as f:
        header = parse_header(f.read(_HEADER_BYTES))
    if header is None:
        raise ValueError(f"cannot parse report header: {path}")
    return ReportRef(name=path.stem, header=header, path=path)


def build_catalog(include_history: bool = True) -> list[ReportRef]:
    refs: dict[str, ReportRef] = {}

    for path in sorted((REPO / "reports").glob("*.json")):
        try:
            refs[path.stem] = ref_for_path(path)
        except Exception as e:  # noqa: BLE001 - a broken file must not break triage
            log(f"⚠️ skipping {path.name}: {e}")

    if include_history:
        for name, rev in _deleted_reports().items():
            if name in refs:
                continue
            header = _git_header(rev, name)
            if header is not None:
                refs[name] = ReportRef(name=name, header=header, git_rev=rev)

    return list(refs.values())


def _deleted_reports() -> dict[str, str]:
    """Map of report name -> revision where it still existed (parent of the deleting commit)."""
    try:
        out = subprocess.check_output(
            [
                "git",
                "log",
                "--diff-filter=D",
                "--format=@%H",
                "--name-only",
                "--",
                "reports/",
            ],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    result: dict[str, str] = {}
    commit = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("@"):
            commit = line[1:]
        elif line.startswith("reports/") and line.endswith(".json") and commit:
            name = Path(line).stem
            # `git log` is newest-first; keep the most recent deletion.
            result.setdefault(name, f"{commit}^")
    return result


def _git_header(rev: str, name: str) -> ReportHeader | None:
    try:
        proc = subprocess.Popen(
            ["git", "show", f"{rev}:reports/{name}.json"],
            cwd=REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert proc.stdout is not None
        head = proc.stdout.read(_HEADER_BYTES)
        proc.kill()
        proc.wait()
        return parse_header(head)
    except Exception:  # noqa: BLE001
        return None
