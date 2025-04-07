import functools
import shutil
from pathlib import Path

import click
import rich.traceback
from python_on_whales import DockerClient
from rich.console import Console

from maat import sandbox
from maat.ecosystem import build_test_suite
from maat.installation import REPO
from maat.model import Report
from maat.report import browser
from maat.report.analysis import analyse_report
from maat.report.metrics import Metrics
from maat.report.reporter import Reporter
from maat.runner.ephemeral_volume import ephemeral_volume
from maat.runner.local import docker_run_step, execute_test_suite_locally
from maat.semver import Semver, SemverParamType
from maat.workspace import Workspace

pass_console = click.make_pass_decorator(Console, ensure=True)
pass_docker = click.make_pass_decorator(DockerClient, ensure=True)


PathParamType = click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)


def load_workspace(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        workspace_name: str | None = kwargs.pop("workspace", None)
        if not workspace_name:
            raise click.UsageError("--workspace is required")
        workspace = Workspace.load(workspace_name)
        return ctx.invoke(f, *args, **kwargs, workspace=workspace)

    return functools.update_wrapper(new_func, f)


@click.group(help="Run experimental software builds across Cairo language ecosystem.")
def cli() -> None:
    pass


@cli.command(help="Run an experiment locally.")
@click.option(
    "-w",
    "--workspace",
    envvar="MAAT_WORKSPACE",
    default="local",
    help="Workspace name.",
    metavar="WORKSPACE",
)
@click.option(
    "--scarb",
    envvar="MAAT_SCARB_VERSION",
    prompt="Scarb version",
    help="Version of Scarb to experiment on.",
    type=SemverParamType,
)
@click.option(
    "--foundry",
    envvar="MAAT_FOUNDRY_VERSION",
    prompt="Starknet Foundry version",
    help="Version of Starknet Foundry to experiment on.",
    type=SemverParamType,
)
@click.option(
    "-j",
    "--jobs",
    metavar="N",
    help="Allow N jobs at once; defaults to number of CPUs.",
    type=int,
    default=None,
)
@load_workspace
@pass_docker
@pass_console
def run_local(
    console: Console,
    docker: DockerClient,
    workspace: Workspace,
    scarb: Semver,
    foundry: Semver,
    jobs: int | None,
) -> None:
    console.log(f":test_tube: Running experiment within workspace: [bold]{workspace}")

    reporter = Reporter(workspace_name=workspace.name, scarb=scarb, foundry=foundry)

    sandbox_image = sandbox.build(
        scarb=scarb, foundry=foundry, docker=docker, console=console
    )

    test_suite = build_test_suite(
        ecosystem=workspace.settings.ecosystem,
        sandbox=sandbox_image.id,
        console=console,
    )

    execute_test_suite_locally(
        test_suite=test_suite,
        jobs=jobs,
        docker=docker,
        reporter=reporter,
        console=console,
    )

    report = reporter.finish()

    analyse_report(
        report=report,
        console=console,
    )

    report.save()


@cli.command(help="Build the sandbox image for the given environment.")
@click.option(
    "--scarb",
    envvar="MAAT_SCARB_VERSION",
    prompt="Scarb version",
    help="Version of Scarb to experiment on.",
    type=SemverParamType,
)
@click.option(
    "--foundry",
    envvar="MAAT_FOUNDRY_VERSION",
    prompt="Starknet Foundry version",
    help="Version of Starknet Foundry to experiment on.",
    type=SemverParamType,
)
@pass_docker
@pass_console
def build_sandbox(
    console: Console,
    docker: DockerClient,
    scarb: Semver,
    foundry: Semver,
) -> None:
    sandbox.build(scarb=scarb, foundry=foundry, docker=docker, console=console)


@cli.command(help="Open and display one or more reports in a web browser.")
@click.argument("reports", type=PathParamType, nargs=-1, required=True)
@pass_console
def open(console: Console, reports: tuple[Path, ...]) -> None:
    all_metrics = []
    for path in reports:
        report = Report.model_validate_json(path.read_bytes())
        metrics = Metrics.compute(report=report, path=path)
        all_metrics.append(metrics)

    html_path = browser.render_html(all_metrics)
    console.log("Report generated at:", html_path)

    console.log("Opening report in browser...")
    click.launch(str(html_path))


@cli.command(help="Reanalyse an existing report and update it.")
@click.argument("report", type=PathParamType, required=False)
@click.option(
    "--all", is_flag=True, help="Reanalyse all reports in the reports directory."
)
@pass_console
def reanalyse(console: Console, report: Path = None, all: bool = False) -> None:
    def reanalyse_file(report_file: Path):
        report_obj: Report = Report.model_validate_json(report_file.read_bytes())
        analyse_report(report=report_obj, console=console)
        report_obj.save()

    match (report, all):
        case (None, False):
            raise click.UsageError("Either --all or report must be specified")
        case (None, True):
            reports_dir = REPO / "reports"
            report_files = list(reports_dir.glob("*.json"))
            if not report_files:
                console.log("No reports found in the reports directory.")
                return

            for report_file in report_files:
                console.log(f"Reanalysing report: {report_file.name}")
                reanalyse_file(report_file)
        case (report, False):
            reanalyse_file(report)
        case (report, True):
            raise click.UsageError("Cannot specify both --all and report")


@cli.command(
    help="Run setup steps for a test and dump workbench to the checkouts directory."
)
@click.argument("test_name", required=True)
@click.option(
    "-w",
    "--workspace",
    envvar="MAAT_WORKSPACE",
    default="local",
    help="Workspace name.",
    metavar="WORKSPACE",
)
@click.option(
    "--scarb",
    envvar="MAAT_SCARB_VERSION",
    prompt="Scarb version",
    help="Version of Scarb to experiment on.",
    type=SemverParamType,
)
@click.option(
    "--foundry",
    envvar="MAAT_FOUNDRY_VERSION",
    prompt="Starknet Foundry version",
    help="Version of Starknet Foundry to experiment on.",
    type=SemverParamType,
)
@load_workspace
@pass_docker
@pass_console
def checkout(
    console: Console,
    docker: DockerClient,
    workspace: Workspace,
    test_name: str,
    scarb: Semver,
    foundry: Semver,
) -> None:
    sandbox_image = sandbox.build(
        scarb=scarb, foundry=foundry, docker=docker, console=console
    )

    test_suite = build_test_suite(
        ecosystem=workspace.settings.ecosystem,
        sandbox=sandbox_image.id,
        console=console,
    )

    test = test_suite.test_by_name(test_name)
    if test is None:
        raise click.UsageError(
            f"test '{test_name}' not found in workspace '{workspace.name}'"
        )

    setup_steps = [step for step in test.steps if step.meta.setup]
    if not setup_steps:
        raise RuntimeError(f"no setup steps found for test: {test_name}")

    checkout_dir = REPO / "checkouts" / test_name
    if checkout_dir.exists():
        console.log(f"Removing existing checkout directory: {checkout_dir}")
        shutil.rmtree(checkout_dir)
    checkout_dir.mkdir(parents=True, exist_ok=True)

    with (
        console.status("Running setup steps...") as status,
        ephemeral_volume(docker) as cache_volume,
        ephemeral_volume(docker) as workbench_volume,
    ):
        for step in setup_steps:
            status.update(step.name)
            docker_run_step(
                docker=docker,
                image=sandbox_image,
                command=step.run if isinstance(step.run, list) else step.run.split(),
                cache_volume=cache_volume,
                workbench_volume=workbench_volume,
                raise_on_nonzero_exit=True,
            )

        status.update("Copying workbench contents...")
        docker.volume.copy(
            source=(workbench_volume, "."),
            destination=checkout_dir,
        )

    console.log(f":file_folder: Checked out {checkout_dir}")


if __name__ == "__main__":
    rich.traceback.install(show_locals=True)
    cli()
