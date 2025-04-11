import re
from functools import total_ordering
from typing import Self


@total_ordering
class _Key:
    __slots__ = ("_key",)

    def __init__(self, key: int | str):
        self._key = key

    def __eq__(self, other: Self):
        return self._key == other._key

    def __lt__(self, other: Self):
        if type(self._key) is type(other._key):
            return self._key < other._key
        else:
            # Ints are lower than strings.
            return isinstance(self._key, int)


def smart_sort_key(text: str) -> list[_Key]:
    """
    Split a string (e.g. a semver) into components suitable for smart sorting.

    ```
    1.2.3 -> [1, 2, 3]
    0.1.0-alpha -> [0, 1, 0, "alpha"]
    0.1.0-alpha.1 -> [0, 1, 0, "alpha", 1]
    0.1.0-alpha.1+2024 -> [0, 1, 0, "alpha", 1, 2024]
    ```
    """

    components = re.split(r"[.\-+]", text)
    return [_Key(_try_int(c)) for c in components]


def _try_int(c: str) -> int | str:
    if c.isdigit():
        return int(c)
    else:
        return c
