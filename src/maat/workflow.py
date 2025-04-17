from rich.console import Console

from maat.ecosystem.spec import Ecosystem
from maat.ecosystem.utils import flatten_ecosystem
from maat.model import ImageId, Step, Test, TestSuite


def build_test_suite(
    ecosystem: Ecosystem,
    sandbox: ImageId,
    console: Console,
) -> TestSuite:
    with console.status("Collecting ecosystem..."):
        suite = TestSuite(sandbox=sandbox)

        for project in flatten_ecosystem(ecosystem):
            steps = project.setup() + _workflow()
            test = Test(name=project.name, rev=project.fetch_rev(), steps=steps)
            suite.tests.append(test)

        return suite


def _workflow() -> list[Step]:
    # NOTE: Each test needs to get a new Step instance, as they create unique IDs on init.
    return [
        Step(run="maat-check-versions", setup=True),
        Step(run="maat-patch", setup=True),
        Step(name="fetch", run="scarb fetch", setup=True),
        Step(name="build", run="scarb build --workspace --test"),
        Step(name="lint", run="scarb lint --workspace --deny-warnings"),
        Step(name="test", run="scarb test --workspace"),
    ]
