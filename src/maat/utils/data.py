"""
Utilities for data mining.
"""

import json
from typing import Iterable


def jsonlines(output: list[str] | None) -> Iterable[dict]:
    if output is None:
        return

    for line in output:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            pass


def utf8continuous(output: list[bytes] | None) -> str:
    if output is None:
        return ""

    return b"".join(output).decode("utf-8", errors="replace")
