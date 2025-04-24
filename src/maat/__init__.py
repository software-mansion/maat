import functools
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path

import cache_to_disk
import click
import rich.traceback
from python_on_whales import DockerClient
from rich.console import Console

from maat import sandbox, web
from maat.workflow import build_test_suite
from maat.installation import REPO
from maat.model import Report, Semver, ReportMeta
from maat.report.analysis import analyse_report
from maat.report.reporter import Reporter
from maat.runner.ephemeral_volume import ephemeral_volume
from maat.runner.local import docker_run_step, execute_test_suite_locally
from maat.utils.asdf import asdf_set
from maat.utils.notify import send_notification
from maat.workspace import Workspace

pass_console = click.make_pass_decorator(Console, ensure=True)
pass_docker = click.make_pass_decorator(DockerClient, ensure=True)


PathParamType = click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)


def workspace_options(f):
    f = click.option(
        "-w",
        "--workspace",
        envvar="MAAT_WORKSPACE",
        default="local",
        help="Workspace name.",
        metavar="WORKSPACE",
    )(f)
    return f


def tool_versions_options(f):
    f = click.option(
        "--scarb",
        envvar="MAAT_SCARB_VERSION",
        prompt="Scarb version",
        help="Version of Scarb to experiment on.",
    )(f)
    f = click.option(
        "--foundry",
        envvar="MAAT_FOUNDRY_VERSION",
        prompt="Starknet Foundry version",
        help="Version of Starknet Foundry to experiment on.",
    )(f)
    return f


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
@workspace_options
@tool_versions_options
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

    send_notification(
        title="Ma'at Experiment Finished",
        message=f"Experiment in workspace '{workspace.name}' on Scarb {scarb} and \
                  Starknet Foundry {foundry} has completed.",
    )


@cli.command(help="Build the sandbox image for the given environment.")
@click.option(
    "--scarb",
    envvar="MAAT_SCARB_VERSION",
    prompt="Scarb version",
    help="Version of Scarb to experiment on.",
)
@click.option(
    "--foundry",
    envvar="MAAT_FOUNDRY_VERSION",
    prompt="Starknet Foundry version",
    help="Version of Starknet Foundry to experiment on.",
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
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=True, file_okay=False, path_type=Path),
    help="Write output to directory instead of opening in browser.",
)
@pass_console
def open(
    console: Console,
    reports: tuple[Path, ...],
    output: Path | None = None,
) -> None:
    report_tuples = [
        (Report.model_validate_json(path.read_bytes()), ReportMeta.new(path))
        for path in reports
    ]

    with ExitStack() as stack:
        output_dir: Path
        if output is None:
            output_dir = Path(
                stack.enter_context(tempfile.TemporaryDirectory(delete=False))
            )
        else:
            output_dir = output

        web.build(reports=report_tuples, output=output_dir)

        if output is None:
            console.log("Report generated at:", output_dir.name)
            console.log("Opening report in browser...")
            click.launch(str(output_dir / "index.html"))


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
@workspace_options
@tool_versions_options
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

    steps = [step for step in test.steps if step.checkout]
    if not steps:
        raise RuntimeError(f"no checkout steps found for test: {test_name}")

    checkout_dir = REPO / "checkouts" / test_name

    with (
        console.status("Running checkout steps...") as status,
        ephemeral_volume(docker) as cache_volume,
        ephemeral_volume(docker) as workbench_volume,
    ):
        for step in steps:
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

        if checkout_dir.exists():
            shutil.rmtree(checkout_dir)
        checkout_dir.mkdir(parents=True, exist_ok=True)

        docker.volume.copy(
            source=(workbench_volume, "."),
            destination=checkout_dir,
        )

    asdf_set(checkout_dir, "scarb", scarb)
    asdf_set(checkout_dir, "starknet-foundry", foundry)

    console.log(f":file_folder: Checked out {checkout_dir}")


@cli.command(help="Delete all disk caches that Ma'at stores.")
@pass_console
def prune_cache(console: Console) -> None:
    cache_to_disk.delete_disk_caches_for_function("fetch_all_packages")
    cache_to_disk.delete_disk_caches_for_function("fetch_commit_hash")
    cache_to_disk.delete_disk_caches_for_function("fetch")


if __name__ == "__main__":
    rich.traceback.install(show_locals=True)
    cli()
