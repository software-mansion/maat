import re


def smart_sort_key(text: str) -> list[int | str]:
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
    return [_try_int(c) for c in components]


def _try_int(c: str) -> int | str:
    if c.isdigit():
        return int(c)
    else:
        return c
