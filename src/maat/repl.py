"""
Various utility functions that are awesome for debugging Ma'at via Python REPL.

Run: `from maat.repl import *`
"""

import pathlib
import re
from collections import defaultdict

from maat.model import Report, TestReport


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
            stdout_combined = step.stdout_utf8continuous()
            if compiled_pattern.search(stdout_combined):
                result.add(test.name)
                break  # Avoid duplicating test names
    return list(sorted(result))


def zip_tests(*args: Report) -> list[tuple[TestReport, ...]]:
    lists = defaultdict(lambda: [None] * len(args))
    for i, report in enumerate(args):
        for test in report.tests:
            lists[test.name][i] = test
    return list(map(tuple, lists.values()))
