"""
Upstream changelog correlation.

Each tool version is resolved to a git ref of its source repository:

* stable / pre-release versions → the ``v<version>`` tag,
* Scarb nightlies and dev builds → the source commit listed in the
  ``software-mansion/scarb-nightlies`` release notes (which also name the Cairo commit),
* Foundry nightlies → the source commit listed in the
  ``software-mansion-labs/starknet-foundry-nightlies`` release notes.

The commits between the pivot and target refs are then fetched from the GitHub compare
API. Everything is best-effort: failures are recorded, never raised.
"""

import os
import re
import subprocess

import requests
from pydantic import BaseModel

from maat.triage.versions import version_kind

SCARB_REPO = "software-mansion/scarb"
SCARB_NIGHTLIES = "software-mansion/scarb-nightlies"
CAIRO_REPO = "starkware-libs/cairo"
CAIRO_LINT_REPO = "software-mansion/cairo-lint"
FOUNDRY_REPO = "foundry-rs/starknet-foundry"
FOUNDRY_NIGHTLIES = "software-mansion-labs/starknet-foundry-nightlies"

MAX_COMMITS = 150
_TIMEOUT = 20


class Commit(BaseModel):
    sha: str
    subject: str
    url: str


class ToolChangelog(BaseModel):
    component: str
    repo: str
    base: str
    head: str
    compare_url: str | None = None
    commits: list[Commit] = []
    total_commits: int = 0
    direction: str | None = None
    """``ahead`` (normal), ``behind`` (target is older than the pivot), ``diverged`` or ``identical``."""
    error: str | None = None


class _Refs(BaseModel):
    main: str | None = None
    cairo: str | None = None
    cairo_lint: str | None = None


def changelogs(
    pivot_versions: dict[str, str], target_versions: dict[str, str]
) -> list[ToolChangelog]:
    gh = _GitHub()
    result: list[ToolChangelog] = []

    ps, ts = pivot_versions["scarb"], target_versions["scarb"]
    if ps != ts:
        p_refs, t_refs = gh.scarb_refs(ps), gh.scarb_refs(ts)
        result.append(gh.compare("Scarb", SCARB_REPO, p_refs.main, t_refs.main, ps, ts))
        if p_refs.cairo and t_refs.cairo and p_refs.cairo != t_refs.cairo:
            result.append(
                gh.compare("Cairo", CAIRO_REPO, p_refs.cairo, t_refs.cairo, ps, ts)
            )
        # Lint diagnostic changes are attributed to these commits (or to Cairo's).
        if (
            p_refs.cairo_lint
            and t_refs.cairo_lint
            and p_refs.cairo_lint != t_refs.cairo_lint
        ):
            result.append(
                gh.compare(
                    "cairo-lint",
                    CAIRO_LINT_REPO,
                    p_refs.cairo_lint,
                    t_refs.cairo_lint,
                    ps,
                    ts,
                )
            )

    pf, tf = pivot_versions["foundry"], target_versions["foundry"]
    if pf != tf:
        result.append(
            gh.compare(
                "Starknet Foundry",
                FOUNDRY_REPO,
                gh.foundry_ref(pf),
                gh.foundry_ref(tf),
                pf,
                tf,
            )
        )

    return result


def _github_token() -> str | None:
    if token := os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return token
    # Local runs: reuse the gh CLI login to avoid the anonymous rate limit.
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


class _GitHub:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/vnd.github+json"
        if token := _github_token():
            self.session.headers["Authorization"] = f"Bearer {token}"
        self._manifests: dict[str, str | None] = {}

    def _get(self, path: str) -> dict:
        r = self.session.get(f"https://api.github.com/{path}", timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _release_body(self, repo: str, tag: str) -> str | None:
        try:
            return self._get(f"repos/{repo}/releases/tags/{tag}").get("body") or ""
        except requests.RequestException:
            return None

    def scarb_refs(self, version: str) -> _Refs:
        kind = version_kind(version)
        if kind in ("stable", "prerelease"):
            main = f"v{version}"
            return _Refs(
                main=main,
                cairo=self._dep_ref_from_manifest(main, "cairo-lang-compiler"),
                cairo_lint=self._dep_ref_from_manifest(main, "cairo-lint"),
            )
        if kind in ("nightly", "dev"):
            body = self._release_body(SCARB_NIGHTLIES, version)
            if body is None:
                return _Refs()
            scarb = re.search(
                r"github\.com/software-mansion/scarb/commit/([0-9a-f]{7,40})", body
            )
            cairo = re.search(
                r"github\.com/starkware-libs/cairo/commit/([0-9a-f]{7,40})", body
            )
            main = scarb and scarb.group(1)
            return _Refs(
                main=main,
                cairo=(cairo and cairo.group(1))
                or (main and self._dep_ref_from_manifest(main, "cairo-lang-compiler")),
                cairo_lint=main and self._dep_ref_from_manifest(main, "cairo-lint"),
            )
        return _Refs()

    def _scarb_manifest(self, scarb_ref: str) -> str | None:
        if scarb_ref not in self._manifests:
            try:
                r = self.session.get(
                    f"https://raw.githubusercontent.com/{SCARB_REPO}/{scarb_ref}/Cargo.toml",
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                self._manifests[scarb_ref] = r.text
            except requests.RequestException:
                self._manifests[scarb_ref] = None
        return self._manifests[scarb_ref]

    def _dep_ref_from_manifest(self, scarb_ref: str, crate: str) -> str | None:
        """
        Ref of a dependency (``cairo-lang-compiler``, ``cairo-lint``) used by Scarb at
        ``scarb_ref``: a git rev or the ``v<version>`` tag (both repos tag ``v<version>``).
        """
        manifest = self._scarb_manifest(scarb_ref)
        if manifest is None:
            return None
        m = re.search(rf"^{re.escape(crate)}\s*=\s*(.+)$", manifest, re.M)
        if not m:
            return None
        spec = m.group(1)
        if rev := re.search(r'rev\s*=\s*"([0-9a-f]{7,40})"', spec):
            return rev.group(1)
        if ver := re.search(r'^"=?([^"]+)"', spec.strip()):
            return f"v{ver.group(1)}"
        if ver := re.search(r'version\s*=\s*"=?([^"]+)"', spec):
            return f"v{ver.group(1)}"
        return None

    def foundry_ref(self, version: str) -> str | None:
        kind = version_kind(version)
        if kind in ("stable", "prerelease"):
            return f"v{version}"
        if kind == "nightly":
            body = self._release_body(FOUNDRY_NIGHTLIES, version)
            if body and (m := re.search(r"/commit/([0-9a-f]{7,40})", body)):
                return m.group(1)
        return None

    def compare(
        self,
        component: str,
        repo: str,
        base: str | None,
        head: str | None,
        base_version: str,
        head_version: str,
    ) -> ToolChangelog:
        entry = ToolChangelog(
            component=component,
            repo=repo,
            base=base or base_version,
            head=head or head_version,
        )
        if not base or not head:
            entry.error = "could not resolve source revision for one of the versions"
            return entry
        try:
            data = self._get(f"repos/{repo}/compare/{base}...{head}")
        except requests.RequestException as e:
            entry.error = f"GitHub compare failed: {e}"
            return entry

        entry.compare_url = data.get("html_url")
        entry.direction = data.get("status")
        entry.total_commits = data.get("total_commits", 0)
        commits = data.get("commits", [])
        if entry.direction == "behind":
            # Target is older than the pivot: list what the target is missing instead.
            try:
                data = self._get(f"repos/{repo}/compare/{head}...{base}")
                commits = data.get("commits", [])
                entry.total_commits = data.get("total_commits", 0)
            except requests.RequestException:
                commits = []
        # Newest first, which is what humans scan.
        for c in reversed(commits[-MAX_COMMITS:]):
            entry.commits.append(
                Commit(
                    sha=c["sha"][:10],
                    subject=c["commit"]["message"].splitlines()[0][:200],
                    url=c["html_url"],
                )
            )
        return entry
