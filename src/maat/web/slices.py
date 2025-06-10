from collections import defaultdict
from typing import Callable, Iterable, Iterator

from pydantic import BaseModel, Field

from maat.web.report_info import ReportInfo


class Slice(BaseModel):
    title: str
    reports: list[ReportInfo] = Field(min_length=1)
    default: bool = False


def make_slices(reports: list[ReportInfo]) -> list[Slice]:
    slices = []

    def push_slice(title: str, reps: list[ReportInfo], default: bool = False):
        if reps:
            sl = Slice(title=title, reports=reps, default=default)
            slices.append(sl)

    latest_nightly = [t for t in reports if t.meta.name == "nightly-latest"]

    all_release = [t for t in reports if t.report.workspace == "release"]

    latest_release_by_scarb = max(
        all_release,
        default=None,
        key=lambda t: t.report.by_version_preferring_scarb,
    )

    latest_release_by_foundry = max(
        all_release,
        default=None,
        key=lambda t: t.report.by_version_preferring_foundry,
    )

    # If there is one report with both the highest scarb and highest foundry version,
    # then this will be one item. Otherwise, this will be a pair.
    latest_release: list[ReportInfo] = []
    if latest_release_by_scarb:
        latest_release.append(latest_release_by_scarb)

        if (
            latest_release_by_foundry
            and latest_release_by_foundry != latest_release_by_scarb
        ):
            latest_release.append(latest_release_by_foundry)

    # Nightly vs (Latest) Release
    if latest_nightly and latest_release:
        push_slice(
            "Nightly vs Release", [*latest_nightly, *latest_release], default=True
        )

    # Last N(<=3) Scarbs
    last_n_scarbs = list(
        unique_by(
            # Deduplicate same-scarb-different-foundry runs.
            sorted(
                all_release,
                key=lambda t: t.report.by_version_preferring_scarb,
            ),
            key=lambda t: t.report.scarb,
        )
    )[-3:]
    push_slice(f"Last {len(last_n_scarbs)} Scarbs", last_n_scarbs)

    # Last N(<=3) Foundries. Foundry targets 3 last release Scarb versions, so we add all of them.
    last_n_foundries = list(
        unique_by_at_most(
            sorted(
                all_release,
                key=lambda t: t.report.by_version_preferring_foundry,
            ),
            n=3,
            m=3,
            key=lambda t: t.report.foundry,
        )
    )

    push_slice(
        f"Last {len({x.report.foundry for x in last_n_foundries})} Foundries",
        last_n_foundries,
    )

    # Finally, the "All" slice.
    push_slice("All", reports)

    return slices


def unique_by[T, K](iterable: Iterable[T], /, key: Callable[[T], K]) -> Iterator[T]:
    seen = set()
    for item in iterable:
        k = key(item)
        if k not in seen:
            seen.add(k)
            yield item


def unique_by_at_most[T, K](
    iterable: Iterable[T],
    /,
    n: int,
    m: int,
    key: Callable[[T], K],
) -> Iterator[T]:
    buckets = defaultdict(list)
    for item in iterable:
        k = key(item)
        buckets[k].append(item)
    for bucket in list(buckets.values())[-n:]:
        for item in bucket[-m:]:
            yield item
