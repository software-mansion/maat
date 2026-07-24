import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from python_on_whales import DockerClient, DockerException, Image, Volume

from maat.model import (
    EXIT_RUNNER_SKIPPED,
    EXIT_STEP_TIMEOUT,
    Plan,
    PlanPartitionView,
    Test,
)
from maat.report.reporter import Reporter, StepReporter
from maat.runner.bake_volume import bake_volume
from maat.runner.cancellation_token import CancellationToken, CancelledException
from maat.runner.ephemeral_volume import ephemeral_volume
from maat.sandbox import MAAT_CACHE, MAAT_WORKBENCH
from maat.utils.log import log, track, uptime
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

    with track(test.name), ExitStack() as volumes:
        # Create cache and workbench volumes which contents will be mutated during the setup phase.
        # We will bake these volumes' contents into the sandbox image and delete them afterwards.
        cache_volume = volumes.enter_context(ephemeral_volume(docker))
        ct.raise_if_cancelled()

        workbench_volume = volumes.enter_context(ephemeral_volume(docker))
        ct.raise_if_cancelled()

        # We will run setup on the sandbox image, and then this will become the image with baked-in
        # cache and workbench volumes.
        image = sandbox

        is_setup_phase = True
        setup_failed = False

        for step in test.steps:
            ct.raise_if_cancelled()

            # Raise if a sudden setup step exists after a non-setup one.
            if not is_setup_phase and step.setup:
                raise RuntimeError(
                    f"Setup step `{step.name}` found after non-setup step in test: {test.name}"
                )

            # Skip execution if a setup step has failed but still create a report.
            if setup_failed:
                # Mark as skipped due to a setup failure.
                with test_reporter.step(step) as step_reporter:
                    step_reporter.set_exit_code(EXIT_RUNNER_SKIPPED)
                continue

            # Check if we've just exited the setup phase and have to prepare the test image.
            if is_setup_phase and not step.setup:
                is_setup_phase = False

                with track(f"{test.name}: baking test image"):
                    image = bake_volume(
                        docker=docker,
                        image=image,
                        volume=cache_volume,
                        mount=MAAT_CACHE,
                        ct=ct,
                    )
                    ct.raise_if_cancelled()

                    image = bake_volume(
                        docker=docker,
                        image=image,
                        volume=workbench_volume,
                        mount=MAAT_WORKBENCH,
                        ct=ct,
                    )
                    ct.raise_if_cancelled()

                    # We don't need volumes any more, so we can delete them and stop mounting.
                    cache_volume, workbench_volume = None, None
                    volumes.close()

            assert is_setup_phase == step.setup, "setup phase transition messed up"

            ct.raise_if_cancelled()

            with (
                track(f"{test.name}: `{step.name}`"),
                test_reporter.step(step) as step_reporter,
            ):
                exit_code = docker_run_step(
                    docker=docker,
                    image=image,
                    command=split_command(step.run),
                    container_name=f"maat-{slugify(test.name)}-{slugify(step.name)}-{snowflake_id()}",
                    cache_volume=cache_volume,
                    workbench_volume=workbench_volume,
                    ct=ct,
                    step_reporter=step_reporter,
                    env=step.env,
                    workdir=step.workdir,
                    extra_binds=step.binds or None,
                    timeout=step.timeout,
                    stream_logs=step.timeout is not None
                    or bool(os.environ.get("MAAT_STREAM_LOGS")),
                )

                if exit_code != 0:
                    log(f"⚠️ {test.name}: `{step.name}` exited with code {exit_code}")

                # If this was a setup step, and it failed, mark that we should skip the remaining steps.
                if step.setup and exit_code != 0:
                    setup_failed = True


def docker_run_step(
    docker: DockerClient,
    image: Image | str,
    command: list[str],
    cache_volume: Volume | None = None,
    workbench_volume: Volume | None = None,
    container_name: str | None = None,
    ct: CancellationToken | None = None,
    step_reporter: StepReporter | None = None,
    raise_on_nonzero_exit: bool = False,
    env: dict[str, str] | None = None,
    workdir: str | None = None,
    extra_binds: list[list[str]] | None = None,
    timeout: float | None = None,
    stream_logs: bool = False,
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

    volumes = []
    if cache_volume is not None:
        volumes.append((cache_volume, MAAT_CACHE, "rw"))
    if workbench_volume is not None:
        volumes.append((workbench_volume, MAAT_WORKBENCH, "rw"))
    if extra_binds:
        volumes.extend(extra_binds)

    try:
        stream = docker.container.run(
            image=image,
            command=command,
            envs=env or {},
            name=container_name,
            labels=labels,
            remove=True,
            volumes=volumes,
            workdir=real_workdir,
            stream=True,
        )

        # Consume the container's output on a helper thread so we can enforce a wall-clock
        # timeout on it. A plain `for ... in stream` is an unbounded blocking read: a hung
        # container (e.g. a wedged CairoLS during the `ls` step) would otherwise block this
        # worker thread — and therefore `pool.shutdown(wait=True)` and the whole partition —
        # until the CI job's 6h ceiling, with no output flushed.
        events: Queue = Queue()

        def _pump():
            try:
                for source, line in stream:
                    events.put(("line", source, line))
                events.put(("done", None, None))
            except DockerException as exc:
                events.put(("docker_error", exc, None))
            except Exception as exc:  # forward any other error to the main thread
                events.put(("error", exc, None))

        pump_thread = threading.Thread(
            target=_pump, name=f"maat-pump-{container_name}", daemon=True
        )
        pump_thread.start()

        deadline = None if timeout is None else time.monotonic() + timeout
        timed_out = False
        pending_error: Exception | None = None

        while True:
            if ct is not None and ct.is_cancelled:
                # Cancellation kills containers by label elsewhere; stop consuming output.
                break

            if deadline is None:
                wait = 1.0
            else:
                wait = deadline - time.monotonic()
                if wait <= 0:
                    timed_out = True
                    break
                wait = min(wait, 1.0)

            try:
                kind, a, b = events.get(timeout=wait)
            except Empty:
                continue

            if kind == "line":
                source, line = a, b
                if step_reporter is not None:
                    step_reporter.log(source, line)
                if stream_logs:
                    _tee_line(source, line)
            elif kind == "done":
                break
            else:  # "docker_error" or "error"
                pending_error = a
                break

        if timed_out:
            log(
                f"⏱️ step exceeded timeout of {timeout:.0f}s, "
                f"killing container {container_name}"
            )
            try:
                docker.container.kill(container_name)
            except DockerException:
                pass  # already gone / not running
            exit_code = EXIT_STEP_TIMEOUT
            # Give the pump a moment to drain the tail so the report captures it.
            pump_thread.join(timeout=30)
        elif pending_error is not None:
            raise pending_error
    except DockerException as e:
        exit_code = e.return_code
        # If the docker CLI failed without streaming any output (e.g. the
        # image reference could not be resolved), surface its stderr in the
        # step log — otherwise the report records a bare exit code with an
        # empty log and nothing to debug from.
        if step_reporter is not None and not step_reporter.has_output and e.stderr:
            stderr = e.stderr if isinstance(e.stderr, bytes) else str(e.stderr).encode()
            for line in stderr.splitlines(keepends=True):
                step_reporter.log("stderr", line)
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


def _tee_line(source: str, line: bytes) -> None:
    """Echo a streamed container output line to stdout as it arrives.

    Container output is otherwise only buffered in the report and flushed when the step ends,
    so a hanging step yields no live trail. Teeing turns silent hangs into a timestamped stream.
    """
    tag = "err" if source == "stderr" else "out"
    text = line.decode("utf-8", errors="replace").rstrip("\n")
    print(f"[{uptime()}] │ {tag}: {text}", flush=True)


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
