from dataclasses import dataclass

from maat.utils.log import track
from python_on_whales import DockerClient, Image

from maat.ecosystem.spec import EcosystemProject, ReportNameGenerationContext
from maat.ecosystem.utils import flatten_ecosystem
from maat.model import Plan, Step, Test, TestSuite
from maat.sandbox import tool_versions
from maat.utils.docker import image_id
from maat.utils.semver import is_unstable_semver
from maat.workspace import Workspace


def _workflow(project: EcosystemProject, scarb: str) -> list[Step]:
    env: dict[str, str] = {}

    # We need to disable cairo-version checks for unstable versions, as otherwise scarb would reject
    # building dependencies that require stable Cairo versions (which is majority out there).
    # Only dependencies matter here because toplevel packages are already patched.
    if is_unstable_semver(scarb):
        # NOTE: Scarb doesn't accept `1` here, weird.
        env["SCARB_IGNORE_CAIRO_VERSION"] = "true"

    return [
        Step(run="maat-check-versions", setup=True, workdir=project.workdir),
        Step(run="maat-patch", setup=True, workdir=project.workdir),
        Step(
            name="fetch",
            run="scarb fetch",
            setup=True,
            checkout=False,
            workdir=project.workdir,
        ),
        # Show what dependencies were resolved in logs.
        # This is just for debugging purposes, so it doesn't make sense for it to be a setup step.
        Step(name="tree", run="scarb tree -q --workspace", workdir=project.workdir),
        Step(
            name="build",
            run="scarb build --workspace --test",
            workdir=project.workdir,
            env=env,
        ),
        Step(
            name="lint",
            run="scarb lint --workspace --deny-warnings",
            workdir=project.workdir,
            env=env,
        ),
        Step(
            name="test",
            run="scarb test --workspace",
            env={
                **env,
                "SNFORGE_FUZZER_SEED": "1",
                "SNFORGE_IGNORE_FORK_TESTS": "1",
            },
            workdir=project.workdir,
        ),
        Step(name="ls", run="maat-test-ls", workdir=project.workdir, env=env),
    ]


def prepare_plan(
    workspace: Workspace,
    sandbox: Image | str,
    partitions: int,
    docker: DockerClient,
) -> Plan:
    scarb, foundry = tool_versions(sandbox, docker)

    with track("Collecting ecosystem"):
        tests = []
        for project in flatten_ecosystem(workspace.settings.ecosystem):
            steps = project.setup() + _workflow(project=project, scarb=scarb)
            test = Test(name=project.name, rev=project.fetch_rev(), steps=steps)
            tests.append(test)

        suite = TestSuite(tests=tests)

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
