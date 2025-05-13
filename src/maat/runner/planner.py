from dataclasses import dataclass

from python_on_whales import DockerClient, Image
from rich.console import Console

from maat.ecosystem.spec import ReportNameGenerationContext
from maat.ecosystem.utils import flatten_ecosystem
from maat.model import Plan, Step, Test, TestSuite
from maat.sandbox import tool_versions
from maat.utils.docker import image_id
from maat.workspace import Workspace

_WORKFLOW = [
    Step(run="maat-check-versions", setup=True),
    Step(run="maat-patch", setup=True),
    Step(name="fetch", run="scarb fetch", setup=True, checkout=False),
    Step(name="build", run="scarb build --workspace --test"),
    Step(name="lint", run="scarb lint --workspace --deny-warnings"),
    Step(
        name="test",
        run="scarb test --workspace",
        env={
            "SNFORGE_FUZZER_SEED": "1",
            "SNFORGE_IGNORE_FORK_TESTS": "1",
        },
    ),
    Step(name="ls", run="maat-test-ls"),
]


def prepare_plan(
    workspace: Workspace,
    sandbox: Image | str,
    partitions: int,
    docker: DockerClient,
    console: Console,
) -> Plan:
    with console.status("Collecting ecosystem..."):
        suite = TestSuite()

        for project in flatten_ecosystem(workspace.settings.ecosystem):
            steps = project.setup() + _WORKFLOW
            test = Test(name=project.name, rev=project.fetch_rev(), steps=steps)
            suite.tests.append(test)

    scarb, foundry = tool_versions(sandbox, docker)

    report_name = workspace.settings.generate_report_name(
        _PlanningReportNameGenerationContext(
            workspace=workspace.name,
            scarb=scarb,
            foundry=foundry,
        )
    )

    partitioned_suite = suite.partition(partitions)

    return Plan(
        workspace=workspace.name,
        scarb=scarb,
        foundry=foundry,
        report_name=report_name,
        sandbox=image_id(sandbox),
        partitions=partitioned_suite,
    )


@dataclass
class _PlanningReportNameGenerationContext(ReportNameGenerationContext):
    workspace: str
    scarb: str
    foundry: str
