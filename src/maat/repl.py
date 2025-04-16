"""
Various utility functions that are awesome for debugging Ma'at via Python REPL.

Run: `from maat.repl import *`
"""

import pathlib
import re
from collections import defaultdict

from maat.model import Report, TestReport


def open_report(path: str | pathlib.Path) -> Report:
    """
    Opens and parses a Ma'at report from a file.

    Args:
        path: Path to the report file can be a string or a Path object.

    Returns:
        A validated Report object containing the report data.
    """
    path = pathlib.Path(path)
    return Report.model_validate_json(path.read_bytes())


def list_test_names_containing_pattern_in_log(
    report: Report, pattern: str
) -> list[str]:
    """
    Finds test names where the log (stdout+stderr) contains a specific pattern.

    Returns:
        A sorted list of test names that contain the pattern in their log.
    """
    compiled_pattern = re.compile(pattern)
    result = set()
    for test in report.tests:
        for step in test.steps:
            if compiled_pattern.search(step.log_str or ""):
                result.add(test.name)
                break
    return list(sorted(result))


def list_test_names_with_non_zero_exit_code_for_step(
    report: Report, step_name: str
) -> list[str]:
    """
    Retrieves a list of test names from the provided report that have non-zero exit codes
    for a specific step.

    :param report:
        The report object which contains test details such as test names and their steps.
    :param step_name:
        The name of the step to filter tests by identifying only the relevant failing steps.
    :return:
        A sorted list of strings, each representing the name of a test with the specified step
        that has a non-zero exit code.
    """
    result = set()
    for test in report.tests:
        for step in test.steps:
            if step.name == step_name and step.exit_code != 0:
                result.add(test.name)
    return list(sorted(result))


def zip_tests(*args: Report) -> list[tuple[TestReport, ...]]:
    """
    Combines multiple reports by matching tests with the same name.

    This function takes multiple Report objects and creates tuples of TestReport objects
    that share the same test name across reports. If a test is missing in a report,
    its position in the tuple will be None.

    Args:
        *args: Multiple Report objects to be combined.

    Returns:
        A list of tuples, where each tuple contains TestReport objects (or None)
        from each input report that share the same test name.
    """
    lists = defaultdict(lambda: [None] * len(args))
    for i, report in enumerate(args):
        for test in report.tests:
            lists[test.name][i] = test
    return list(map(tuple, lists.values()))
