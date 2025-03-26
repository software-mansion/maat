from typing import Iterator

from rich.console import Console

from maat import tests
from maat.ecosystem.spec import Ecosystem, EcosystemProject
from maat.runner.model import ImageId, Test, TestSuite


def build_test_suite(
    ecosystem: Ecosystem, sandbox: ImageId, console: Console
) -> TestSuite:
    with console.status("Collecting ecosystem..."):
        suite = TestSuite(sandbox=sandbox)

        for project in flatten_ecosystem(ecosystem):
            steps = project.setup()
            for test in tests.All:
                steps.extend(test.steps())

            test = Test(name=project.name, steps=steps)
            suite.tests.append(test)

        return suite


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
