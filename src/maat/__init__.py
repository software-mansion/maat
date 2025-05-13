import functools
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path

import cache_to_disk
import click
import rich.traceback
from python_on_whales import DockerClient, Image
from rich.console import Console

from maat import sandbox, web
from maat.installation import REPO
from maat.model import Report, ReportMeta, Semver
from maat.report.analysis import analyse_report
from maat.report.io import ReportEditor, save_report
from maat.report.reporter import Reporter
from maat.runner.ephemeral_volume import ephemeral_volume
from maat.runner.executor import docker_run_step, execute_plan
from maat.runner.planner import prepare_plan
from maat.utils.asdf import asdf_latest, asdf_set
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


def sandbox_options(f=None, /, pull: bool = True):
    def decorator(f):
        f = click.option(
            "--scarb",
            envvar="MAAT_SCARB_VERSION",
            help="Version of Scarb to experiment on.",
        )(f)
        f = click.option(
            "--foundry",
            envvar="MAAT_FOUNDRY_VERSION",
            help="Version of Starknet Foundry to experiment on.",
        )(f)
        if pull:
            f = click.option(
                "--pull",
                help="Pull the sandbox image instead of building it. Format: NAME[:TAG|@DIGEST]",
            )(f)
        return f

    # This allows the decorator to be used with or without arguments.
    if f is None:
        return decorator
    return decorator(f)


def load_workspace(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        workspace_name: str | None = kwargs.pop("workspace", None)
        if not workspace_name:
            raise click.UsageError("--workspace is required")
        workspace = Workspace.load(workspace_name)
        return ctx.invoke(f, *args, **kwargs, workspace=workspace)

    return functools.update_wrapper(new_func, f)


def tool_versions(f=None, /, optional: bool = False):
    def decorator(f):
        @pass_docker
        @click.pass_context
        def new_func(ctx, docker: DockerClient, *args, **kwargs):
            workspace: Workspace | None = kwargs.get("workspace")

            if kwargs.get("scarb") is None:
                if optional:
                    scarb = None
                elif (
                    workspace is not None
                    and (default_scarb := workspace.settings.default_scarb) is not None
                ):
                    scarb = default_scarb
                else:
                    scarb = click.prompt("Scarb version", type=str)

                if scarb is not None and scarb.startswith("latest"):
                    version = scarb.split(":", 1)[-1]
                    scarb = asdf_latest(docker, "scarb", version)

                kwargs["scarb"] = scarb

            if kwargs.get("foundry") is None:
                if optional:
                    foundry = None
                elif (
                    workspace is not None
                    and (default_foundry := workspace.settings.default_foundry)
                    is not None
                ):
                    foundry = default_foundry
                else:
                    foundry = click.prompt("Starknet Foundry version", type=str)

                if foundry is not None and foundry.startswith("latest"):
                    version = foundry.split(":", 1)[-1]
                    foundry = asdf_latest(docker, "starknet-foundry", version)

                kwargs["foundry"] = foundry

            return ctx.invoke(f, *args, **kwargs)

        return functools.update_wrapper(new_func, f)

    # This allows the decorator to be used with or without arguments.
    if f is None:
        return decorator
    return decorator(f)


def load_sandbox_image(f):
    @pass_docker
    @pass_console
    @click.pass_context
    def new_func(
        ctx,
        console: Console,
        docker: DockerClient,
        *args,
        pull: str | None,
        scarb: Semver | None,
        foundry: Semver | None,
        **kwargs,
    ):
        # Validate that either --pull is specified or both --scarb and --foundry are specified.
        if pull is None and (scarb is None or foundry is None):
            raise click.UsageError(
                "either --pull or both --scarb and --foundry must be specified"
            )

        if pull:
            with console.status(f"Pulling sandbox image: {pull}..."):
                sandbox_image = docker.image.pull(pull)
                console.log(f":rocket: Successfully pulled sandbox image: {pull}")
        else:
            sandbox_image = sandbox.build(
                scarb=scarb, foundry=foundry, docker=docker, console=console
            )

        kwargs["sandbox_image"] = sandbox_image
        return ctx.invoke(f, *args, **kwargs)

    return functools.update_wrapper(new_func, f)


@click.group(help="Run experimental software builds across Cairo language ecosystem.")
def cli() -> None:
    pass


@cli.command(help="Run an experiment locally.")
@workspace_options
@sandbox_options
@click.option(
    "-j",
    "--jobs",
    metavar="N",
    help="Allow N jobs at once; defaults to number of CPUs.",
    type=int,
    default=None,
)
@load_workspace
@tool_versions(optional=True)
@load_sandbox_image
@pass_docker
@pass_console
def run_local(
    console: Console,
    docker: DockerClient,
    workspace: Workspace,
    sandbox_image: Image,
    jobs: int | None,
) -> None:
    console.log(f":test_tube: Running experiment within workspace: [bold]{workspace}")

    plan = prepare_plan(
        workspace=workspace,
        sandbox=sandbox_image,
        partitions=1,
        docker=docker,
        console=console,
    )

    reporter = Reporter(plan)

    execute_plan(
        plan=plan,
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

    save_report(report, plan.report_path)

    send_notification(
        title="Ma'at Experiment Finished",
        message=f"Experiment in workspace '{workspace.name}' on Scarb {plan.scarb} and \
                  Starknet Foundry {plan.foundry} has completed.",
    )


@cli.command(help="Build the sandbox image for the given environment.")
@sandbox_options(pull=False)
@click.option(
    "--cache-from",
    help="External cache sources (e.g., 'user/app:cache', 'type=local,src=path/to/dir')",
)
@click.option(
    "--cache-to",
    help="Cache export destinations (e.g., 'user/app:cache', 'type=local,dest=path/to/dir')",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Use build cache",
)
@click.option(
    "--output",
    help="Output destination (e.g., 'type=local,dest=path/to/dir')",
)
@click.option(
    "--push",
    is_flag=True,
    help="Push the image to registry",
)
@tool_versions
@pass_docker
@pass_console
def build_sandbox(
    console: Console,
    docker: DockerClient,
    scarb: Semver,
    foundry: Semver,
    cache_from: str = None,
    cache_to: str = None,
    cache: bool = True,
    output: str = None,
    push: bool = False,
) -> None:
    sandbox.build(
        scarb=scarb,
        foundry=foundry,
        docker=docker,
        console=console,
        cache_from=cache_from,
        cache_to=cache_to,
        cache=cache,
        output=output,
        push=push,
    )


@cli.command(help="Build web frontend and optionally open it in browser.")
@click.argument("reports", type=PathParamType, nargs=-1, required=True)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=True, file_okay=False, path_type=Path),
    help="Write output to directory instead of opening in browser.",
)
@pass_console
def build_web(
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
        editor = ReportEditor.read(report_file)
        analyse_report(report=editor.report, console=console)
        editor.save()

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
@sandbox_options
@load_workspace
@tool_versions
@load_sandbox_image
@pass_docker
@pass_console
def checkout(
    console: Console,
    docker: DockerClient,
    workspace: Workspace,
    sandbox_image: Image,
    test_name: str,
) -> None:
    plan = prepare_plan(
        workspace=workspace,
        sandbox=sandbox_image,
        partitions=1,
        docker=docker,
        console=console,
    )

    test = plan.partitions[0].test_by_name(test_name)
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
                env=step.env,
            )

        status.update("Copying workbench contents...")

        if checkout_dir.exists():
            shutil.rmtree(checkout_dir)
        checkout_dir.mkdir(parents=True, exist_ok=True)

        docker.volume.copy(
            source=(workbench_volume, "."),
            destination=checkout_dir,
        )

    asdf_set(checkout_dir, "scarb", plan.scarb)
    asdf_set(checkout_dir, "starknet-foundry", plan.foundry)

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
