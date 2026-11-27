import re
from typing import Literal

type VersionKind = Literal["stable", "prerelease", "nightly", "dev", "other"]

_STABLE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PRERELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-([0-9A-Za-z.]+)$")
_DATED = re.compile(r"^(nightly|dev)-(\d{4}-\d{2}-\d{2})(?:\.(\d+))?$")


def version_kind(version: str) -> VersionKind:
    if _STABLE.match(version):
        return "stable"
    if _PRERELEASE.match(version):
        return "prerelease"
    if m := _DATED.match(version):
        return m.group(1)  # type: ignore[return-value]
    return "other"


def is_release_version(version: str) -> bool:
    return version_kind(version) in ("stable", "prerelease")


def semver_key(version: str) -> tuple:
    """
    Proper semver ordering key (``2.21.0-rc.0 < 2.21.0``), with dated builds ordered by date.

    Versions of different kinds are not meant to be compared with each other, but the key is
    still total so that sorting never crashes.
    """
    if m := _STABLE.match(version):
        return (0, int(m[1]), int(m[2]), int(m[3]), 1, ())
    if m := _PRERELEASE.match(version):
        pre = tuple(
            (0, int(p), "") if p.isdigit() else (1, 0, p) for p in m[4].split(".")
        )
        return (0, int(m[1]), int(m[2]), int(m[3]), 0, pre)
    if m := _DATED.match(version):
        return (1, m[2], int(m[3] or 0))
    return (2, version)


def same_base_version(a: str, b: str) -> bool:
    """Whether two release versions share ``MAJOR.MINOR.PATCH``."""
    ma = _STABLE.match(a) or _PRERELEASE.match(a)
    mb = _STABLE.match(b) or _PRERELEASE.match(b)
    return bool(ma and mb and ma.groups()[:3] == mb.groups()[:3])
