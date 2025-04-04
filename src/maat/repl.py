"""
Various utility functions that are awesome for debugging Ma'at via Python REPL.

Run: `from maat.repl import *`
"""

import pathlib
import re

from maat.model import Report
from maat.utils.data import utf8continuous


def open_report(path: str | pathlib.Path) -> Report:
    path = pathlib.Path(path)
    return Report.model_validate_json(path.read_bytes())


def list_test_names_containing_pattern_in_stdout(
    report: Report, pattern: str
) -> list[str]:
    compiled_pattern = re.compile(pattern)
    result = set()
    for test in report.tests:
        for step in test.steps:
            stdout_combined = utf8continuous(step.stdout)
            if compiled_pattern.search(stdout_combined):
                result.add(test.name)
                break  # Avoid duplicating test names
    return list(sorted(result))
