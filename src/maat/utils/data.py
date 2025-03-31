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
