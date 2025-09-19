import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from python_on_whales import DockerClient, DockerException, Image, Volume

from maat.model import EXIT_RUNNER_SKIPPED, Plan, PlanPartitionView, Test
from maat.report.reporter import Reporter, StepReporter
from maat.runner.cancellation_token import CancellationToken, CancelledException
from maat.runner.ephemeral_volume import ephemeral_volume
from maat.sandbox import MAAT_CACHE, MAAT_WORKBENCH
from maat.utils.log import log, track
from maat.utils.shell import split_command
from maat.utils.slugify import slugify
from maat.utils.unique_id import snowflake_id


def execute_plan(
    plan: Plan,
    jobs: int | None,
    docker: DockerClient,
    reporter: Reporter,
):
    for partition in plan.partition_views():
        execute_plan_partition(
            partition=partition,
            jobs=jobs,
            docker=docker,
            reporter=reporter,
        )


def execute_plan_partition(
    partition: PlanPartitionView,
    jobs: int | None,
    docker: DockerClient,
    reporter: Reporter,
):
    jobs = determine_jobs_amount(jobs)
    ct = CancellationToken()

    with (
        ThreadPoolExecutor(max_workers=jobs) as pool,
    ):

        def worker_main(current_test: Test):
            try:
                _execute_test(
                    test=current_test,
                    sandbox=partition.plan.sandbox,
                    ct=ct,
                    docker=docker,
                    reporter=reporter,
                )
            except CancelledException:
                pass
            except Exception:
                traceback.print_exc()

        for test in partition.test_suite.tests:
            pool.submit(worker_main, test)

        try:
            pool.shutdown(wait=True)
        except KeyboardInterrupt:
            log("⚠️ Cancelling experiment, sending SIGKILL to all containers...")
            ct.cancel(docker)
            pool.shutdown(wait=True)
            log("🧪 Experiment cancelled")
            raise


def _execute_test(
    test: Test,
    sandbox: Image | str,
    ct: CancellationToken,
    docker: DockerClient,
    reporter: Reporter,
):
    ct.raise_if_cancelled()

    test_reporter = reporter.test(test)

    with (
        track(test.name),
        ephemeral_volume(docker) as cache_volume,
        ephemeral_volume(docker) as workbench_volume,
    ):
        ct.raise_if_cancelled()

        setup_failed = False

        for step in test.steps:
            ct.raise_if_cancelled()

            # Skip execution if a setup step has failed but still create a report.
            if setup_failed:
                # Mark as skipped due to a setup failure.
                with test_reporter.step(step) as step_reporter:
                    step_reporter.set_exit_code(EXIT_RUNNER_SKIPPED)
                continue

            with (
                track(f"{test.name}: `{step.name}`"),
                test_reporter.step(step) as step_reporter,
            ):
                exit_code = docker_run_step(
                    docker=docker,
                    image=sandbox,
                    command=split_command(step.run),
                    container_name=f"maat-{slugify(test.name)}-{slugify(step.name)}-{snowflake_id()}",
                    cache_volume=cache_volume,
                    workbench_volume=workbench_volume,
                    ct=ct,
                    step_reporter=step_reporter,
                    env=step.env,
                    workdir=step.workdir,
                )

                # If this was a setup step, and it failed, mark that we should skip the remaining steps.
                if step.setup and exit_code != 0:
                    setup_failed = True


def docker_run_step(
    docker: DockerClient,
    image: Image | str,
    command: list[str],
    cache_volume: Volume,
    workbench_volume: Volume,
    container_name: str | None = None,
    ct: CancellationToken | None = None,
    step_reporter: StepReporter | None = None,
    raise_on_nonzero_exit: bool = False,
    env: dict[str, str] | None = None,
    workdir: str | None = None,
) -> int:
    exit_code = 0

    if container_name is None:
        container_name = f"maat-{snowflake_id()}"

    labels = {}
    if ct is not None:
        labels.update(ct.container_labels)

    real_workdir: str
    if isinstance(workdir, str):
        if Path(workdir).is_absolute():
            real_workdir = workdir
        else:
            real_workdir = str(Path(MAAT_WORKBENCH) / workdir)
    else:
        real_workdir = MAAT_WORKBENCH

    try:
        stream = docker.container.run(
            image=image,
            command=command,
            envs=env or {},
            name=container_name,
            labels=labels,
            remove=True,
            volumes=[
                (cache_volume, MAAT_CACHE, "rw"),
                (workbench_volume, MAAT_WORKBENCH, "rw"),
            ],
            workdir=real_workdir,
            stream=True,
        )
        for source, line in stream:
            if step_reporter is not None:
                step_reporter.log(source, line)
    except DockerException as e:
        exit_code = e.return_code
        if raise_on_nonzero_exit:
            raise
        # Docker run uses exit codes 125, 126, 127 to signal Docker daemon errors.
        # Anything other than these values comes from the container process.
        # Ref: https://docs.docker.com/engine/containers/run/#exit-status
        elif exit_code in [125, 126, 127]:
            raise
    finally:
        if step_reporter is not None:
            step_reporter.set_exit_code(exit_code)

    return exit_code


def truncate_with_ellipsis(text, max_length):
    """Truncate text to `max_length` and add ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def determine_jobs_amount(jobs: int | None) -> int:
    if jobs is not None:
        return jobs

    if num := os.cpu_count():
        # Too much parallelism results in aggressive RAM consumption and severely degraded perf.
        return min(num, 4)

    return 1
