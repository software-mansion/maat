from typing import Iterator

from maat.ecosystem.spec import Ecosystem, EcosystemProject


def flatten_ecosystem(entry: Ecosystem) -> Iterator[EcosystemProject]:
    if isinstance(entry, EcosystemProject):
        yield entry
    elif callable(entry):
        yield from flatten_ecosystem(entry())
    elif isinstance(entry, list):
        for item in entry:
            yield from flatten_ecosystem(item)
    else:
        raise TypeError(f"unsupported ecosystem spec entry: {entry!r}")
