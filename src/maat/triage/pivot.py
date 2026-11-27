"""
Deterministic pivot selection.

The pivot is the report the target is compared against. Choosing it in code (rather than
asking the LLM) keeps the analysis reproducible and cheap; the reason is recorded and shown
to both the LLM and humans.
"""

from typing import Literal

from pydantic import BaseModel

from maat.triage.catalog import ReportRef
from maat.triage.versions import (
    is_release_version,
    same_base_version,
    semver_key,
    version_kind,
)

MAX_PIVOTS = 2

type TargetKind = Literal["release", "nightly", "dev", "custom"]


class Pivot(BaseModel):
    name: str
    reason: str


def target_kind(ref: ReportRef) -> TargetKind:
    h = ref.header
    if ref.name.startswith("custom-"):
        return "custom"
    if h.workspace == "nightly":
        return "nightly"
    if is_release_version(h.scarb) and is_release_version(h.foundry):
        return "release"
    return "dev"


def choose_pivots(target: ReportRef, catalog: list[ReportRef]) -> list[Pivot]:
    # Only reports that existed when the target was produced are eligible. This also makes
    # offline replay of old reports behave like it would have in CI.
    cands = [
        c
        for c in catalog
        if c.name != target.name and c.header.created_at < target.header.created_at
    ]

    match target_kind(target):
        case "release":
            picks = _release_pivots(target, cands)
        case "nightly":
            picks = _nightly_pivots(cands)
        case "dev":
            picks = _dev_pivots(target, cands)
        case "custom":
            picks = _custom_pivots(target, cands)

    result: list[Pivot] = []
    for pick in picks:
        if pick is None:
            continue
        ref, reason = pick
        if all(p.name != ref.name for p in result):
            result.append(Pivot(name=ref.name, reason=reason))
        if len(result) == MAX_PIVOTS:
            break
    return result


type _Pick = tuple[ReportRef, str] | None


def _latest(refs: list[ReportRef]) -> ReportRef | None:
    return max(refs, key=lambda r: r.header.created_at, default=None)


def _releases(cands: list[ReportRef], stable_only: bool = False) -> list[ReportRef]:
    ok = ("stable",) if stable_only else ("stable", "prerelease")
    return [
        c
        for c in cands
        if c.header.workspace == "release"
        and not c.name.startswith("custom-")
        and version_kind(c.header.scarb) in ok
        and version_kind(c.header.foundry) in ok
    ]


def _nightlies(cands: list[ReportRef]) -> list[ReportRef]:
    return [
        c
        for c in cands
        if c.header.workspace == "nightly" and c.name.startswith("nightly-")
    ]


def _best_scarb_below(
    refs: list[ReportRef], scarb: str, prefer_foundry: str
) -> ReportRef | None:
    below = [r for r in refs if semver_key(r.header.scarb) < semver_key(scarb)]
    if not below:
        return None
    top = max(semver_key(r.header.scarb) for r in below)
    at_top = [r for r in below if semver_key(r.header.scarb) == top]
    same_foundry = [r for r in at_top if r.header.foundry == prefer_foundry]
    if same_foundry:
        return _latest(same_foundry)
    top_f = max(semver_key(r.header.foundry) for r in at_top)
    return _latest([r for r in at_top if semver_key(r.header.foundry) == top_f])


def _release_pivots(target: ReportRef, cands: list[ReportRef]) -> list[_Pick]:
    s, f = target.header.scarb, target.header.foundry
    releases = _releases(cands)
    stable = _releases(cands, stable_only=True)

    identical = _latest(
        [r for r in releases if (r.header.scarb, r.header.foundry) == (s, f)]
    )
    rerun = identical and (
        identical,
        "earlier run with identical tool versions (noise/flakiness baseline)",
    )

    older_foundry = [
        r
        for r in releases
        if r.header.scarb == s and semver_key(r.header.foundry) < semver_key(f)
    ]
    prev_foundry = None
    if older_foundry:
        top_f = max(semver_key(r.header.foundry) for r in older_foundry)
        prev_foundry = _latest(
            [r for r in older_foundry if semver_key(r.header.foundry) == top_f]
        )
    prev_foundry_pick = prev_foundry and (
        prev_foundry,
        f"same Scarb {s}, previous Starknet Foundry {prev_foundry.header.foundry} (isolates the Foundry change)",
    )

    if version_kind(s) == "prerelease":
        prev_pre = _best_scarb_below(
            [r for r in releases if same_base_version(r.header.scarb, s)], s, f
        )
        prev_stable = _best_scarb_below(stable, s, f)
        # A first RC is cut from main, so the latest nightly tells whether a change is
        # already on main or specific to the release branch.
        nightly = _latest(_nightlies(cands))
        return [
            prev_pre
            and (
                prev_pre,
                f"previous pre-release of the same version ({prev_pre.header.scarb})",
            ),
            prev_stable
            and (
                prev_stable,
                f"previous stable release ({prev_stable.header.scarb} / {prev_stable.header.foundry})",
            ),
            prev_foundry_pick,
            rerun,
            nightly
            and (nightly, "most recent nightly (already on main or new in the RC?)"),
        ]

    prev_scarb = _best_scarb_below(stable or releases, s, f)
    prev_scarb_pick = prev_scarb and (
        prev_scarb,
        f"previous stable Scarb {prev_scarb.header.scarb}"
        + (
            " with the same Foundry (isolates the Scarb change)"
            if prev_scarb.header.foundry == f
            else f" (Foundry {prev_scarb.header.foundry})"
        ),
    )

    # The release candidate of this version: rc → final should differ very little.
    same_base_pre = [
        r
        for r in releases
        if version_kind(r.header.scarb) == "prerelease"
        and same_base_version(r.header.scarb, s)
    ]
    latest_pre = _best_scarb_below(same_base_pre, s, f) if same_base_pre else None
    pre_pick = latest_pre and (
        latest_pre,
        f"release candidate of this version ({latest_pre.header.scarb} / {latest_pre.header.foundry})",
    )

    scarb_is_new = not any(r.header.scarb == s for r in releases)
    if scarb_is_new:
        return [prev_scarb_pick, prev_foundry_pick, pre_pick, rerun]
    # Scarb was tested before, so the new thing is Foundry (or this is a rerun).
    return [prev_foundry_pick, prev_scarb_pick, rerun]


def _latest_stable_release(cands: list[ReportRef]) -> _Pick:
    stable = _releases(cands, stable_only=True)
    if not stable:
        return None
    best = max(
        stable,
        key=lambda r: (
            semver_key(r.header.scarb),
            semver_key(r.header.foundry),
            r.header.created_at,
        ),
    )
    return (
        best,
        f"latest stable release ({best.header.scarb} / {best.header.foundry}) — drift from stable",
    )


def _nightly_pivots(cands: list[ReportRef]) -> list[_Pick]:
    prev = _latest(_nightlies(cands))
    return [
        prev and (prev, "previous nightly"),
        _latest_stable_release(cands),
    ]


def _dev_pivots(target: ReportRef, cands: list[ReportRef]) -> list[_Pick]:
    dev_kinds = ("dev", "nightly")
    prev_dev = _latest(
        [
            c
            for c in cands
            if c.header.workspace == target.header.workspace
            and not c.name.startswith("custom-")
            and version_kind(c.header.scarb) in dev_kinds
        ]
    )
    nightly = _latest(_nightlies(cands))
    return [
        prev_dev and (prev_dev, f"previous dev build (Scarb {prev_dev.header.scarb})"),
        nightly and (nightly, "most recent nightly"),
        _latest_stable_release(cands),
    ]


def _custom_pivots(target: ReportRef, cands: list[ReportRef]) -> list[_Pick]:
    series = strip_run_number(target.name)
    same_series = _latest([c for c in cands if strip_run_number(c.name) == series])
    picks: list[_Pick] = [
        same_series and (same_series, "previous run of this custom experiment"),
    ]
    if target.header.workspace == "nightly":
        nightly = _latest(_nightlies(cands))
        picks.append(nightly and (nightly, "most recent nightly"))
    picks.append(_latest_stable_release(cands))
    return picks


def strip_run_number(name: str) -> str:
    head, sep, tail = name.rpartition("-")
    return head if sep and tail.isdigit() else name
