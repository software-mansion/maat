import functools
from pathlib import Path

import click
from python_on_whales import DockerClient
from rich import traceback
from rich.console import Console

from maat import sandbox
from maat.ecosystem import build_test_suite
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


@cli.command(help="Compare two reports.")
@click.argument("old_report", type=PathParamType)
@click.argument("new_report", type=PathParamType)
def diff(old_report: str, new_report: str) -> None:
    print(f"Comparing reports: {old_report} vs {new_report}")
    # Implementation would go here


@cli.command(help="Reanalyse an existing report and update it.")
@click.argument("report", type=PathParamType)
@pass_console
def reanalyse(console: Console, report: Path) -> None:
    report: Report = Report.model_validate_json(report.read_bytes())

    analyse_report(
        report=report,
        console=console,
    )

    report.save()


if __name__ == "__main__":
    cli()
