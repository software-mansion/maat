import functools
from pathlib import Path

import click
from python_on_whales import DockerClient
from rich import traceback
from rich.console import Console

from maat import sandbox
from maat.ecosystem import build_test_suite
from maat.installation import REPO
from maat.report.analysis import analyse_report
from maat.model import Report
from maat.report.reporter import Reporter
from maat.runner.local import execute_test_suite_locally
from maat.semver import Semver, SemverParamType
from maat.workspace import Workspace

# TODO: Reports need to be sorted and have somehow stable IDs for git diffability.


traceback.install(show_locals=True)

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
    jobs: int,
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


@cli.command(
    help="Open and display one or more reports. If multiple reports are provided, they will be compared."
)
@click.argument("reports", type=PathParamType, nargs=-1, required=True)
@pass_console
def open(console: Console, reports: tuple[Path, ...]) -> None:
    # Implementation would go here
    pass


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


if __name__ == "__main__":
    cli()
