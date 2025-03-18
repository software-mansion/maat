import functools
import pathlib

import click
from rich import traceback
from rich.console import Console

from maat import sandbox
from maat.ecosystem import build_test_suite
from maat.report.builder import ReportBuilder
from maat.runner.docker import MaatDockerClient
from maat.runner.local import execute_test_suite_locally
from maat.semver import Semver, SemverParamType
from maat.workspace import Workspace

# TODO: Make CTRL+C working when running locally. Maybe run containers in python async code instead of thread pool?
# TODO: Reports need to be sorted and have somehow stable IDs for git diffability.


traceback.install(show_locals=True)

pass_console = click.make_pass_decorator(Console, ensure=True)
pass_docker = click.make_pass_decorator(MaatDockerClient, ensure=True)


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
    type=SemverParamType(),
)
@click.option(
    "--foundry",
    envvar="MAAT_FOUNDRY_VERSION",
    prompt="Starknet Foundry version",
    help="Version of Starknet Foundry to experiment on.",
    type=SemverParamType(),
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
    docker: MaatDockerClient,
    workspace: Workspace,
    scarb: Semver,
    foundry: Semver,
    jobs: int,
) -> None:
    console.log(f":test_tube: Running experiment within workspace: [bold]{workspace}")

    report_builder = ReportBuilder(
        workspace_name=workspace.name, scarb=scarb, foundry=foundry
    )

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
        report_builder=report_builder,
        console=console,
    )

    report_builder.finish().save()


@cli.command(help="Compare two reports.")
@click.argument(
    "old_report", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path)
)
@click.argument(
    "new_report", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path)
)
def diff(old_report: str, new_report: str) -> None:
    print(f"Comparing reports: {old_report} vs {new_report}")
    # Implementation would go here


if __name__ == "__main__":
    cli()
