import base64
import os
import re
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta

from python_on_whales import DockerClient, DockerException, Image, Volume
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from maat.report.reporter import Reporter, StepReporter
from maat.runner.model import Test, TestStep, TestSuite
from maat.utils.shell import split_command

RUN_LABEL = "maat-run"


def execute_test_suite_locally(
    test_suite: TestSuite,
    jobs: int | None,
    docker: DockerClient,
    reporter: Reporter,
    console: Console,
):
    jobs = jobs or os.cpu_count() or 1
    run_token = token()
    run_event = threading.Event()
    run_event.set()

    with (
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("RT"),
            TimeRemainingColumn(),
            TextColumn("ET"),
            TimeElapsedColumn(),
            console=console,
        ) as progress,
        ThreadPoolExecutor(max_workers=jobs) as pool,
    ):
        task = progress.add_task("Experimenting", total=len(test_suite.tests))

        def elapsed() -> timedelta:
            return timedelta(seconds=progress.tasks[task].finished_time or 0)

        def worker_main(current_test: Test):
            # noinspection PyBroadException
            try:
                execute_test_locally(
                    test=current_test,
                    sandbox=test_suite.sandbox,
                    run_event=run_event,
                    run_token=run_token,
                    docker=docker,
                    reporter=reporter,
                    progress=progress,
                )
                progress.advance(task)
            except Exception:
                progress.console.print_exception()

        for test in test_suite.tests:
            pool.submit(worker_main, test)

        try:
            pool.shutdown(wait=True)
        except KeyboardInterrupt:
            run_event.clear()

            progress.console.log(
                f":warning: [progress.elapsed]{elapsed()}[/progress.elapsed] [progress.description]Cancelling experiment, sending SIGKILL to all containers...[/progress.description]"
            )
            progress.update(task, description="Cancelling")

            kill_containers_with_run_token(docker, run_token)
            pool.shutdown(wait=True)

            progress.update(task, visible=False)
            progress.console.log(
                f":test_tube: [progress.elapsed]{elapsed()}[/progress.elapsed] [progress.description bold]Experiment cancelled[/progress.description bold]"
            )
            raise

        progress.update(task, visible=False)
        progress.console.log(
            f":test_tube: [progress.elapsed]{elapsed()}[/progress.elapsed] [progress.description bold]Experiment[/progress.description bold]"
        )


def execute_test_locally(
    test: Test,
    sandbox: Image | str,
    run_event: threading.Event,
    run_token: str,
    docker: DockerClient,
    reporter: Reporter,
    progress: Progress,
):
    if not run_event.is_set():
        return

    test_reporter = reporter.test(test)

    with (
        TestProgress(test, progress) as test_progress,
        ephemeral_volume(
            docker, volume_name=f"maat-{sanitize_name(test.name)}"
        ) as volume,
    ):
        for step in test.steps:
            if not run_event.is_set():
                return

            with (
                test_progress.will_run_step(step),
                test_reporter.step(step) as step_reporter,
            ):
                run_step_command(
                    docker=docker,
                    image=sandbox,
                    command=split_command(step.run),
                    container_name=f"maat-{sanitize_name(test.name)}-{sanitize_name(step.name)}",
                    workbench_volume=volume,
                    labels={RUN_LABEL: run_token},
                    step_reporter=step_reporter,
                )


class TestProgress:
    """
    A context manager to handle test execution monitoring and progress reporting.
    Manages status icons, task creation, progress updates, and final reporting.
    """

    def __init__(self, test: Test, progress: Progress):
        self._test = test
        self._progress = progress
        self._task = self._progress.add_task(
            description=self._test.name,
            start=False,
            total=sum(not s.setup for s in self._test.steps),
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            status_icon = ":x:"
        else:
            status_icon = ":white_check_mark:"

        # Hide task and log final status.
        self._progress.update(self._task, visible=False)
        self._progress.console.log(
            "%s [progress.elapsed]%s[/progress.elapsed] [progress.description]%s[/progress.description]"
            % (
                status_icon,
                timedelta(seconds=self._progress.tasks[self._task].finished_time or 0),
                self._test.name,
            )
        )

        return False  # Don't suppress exceptions.

    @contextmanager
    def will_run_step(self, step: TestStep):
        self._progress.update(self._task, description=f"{self._test.name}: {step.name}")

        if not step.setup and self._progress.tasks[self._task].start_time is None:
            self._progress.start_task(self._task)

        try:
            yield
        finally:
            if not step.setup:
                self._progress.advance(self._task)


@contextmanager
def ephemeral_volume(docker: DockerClient, **kwargs):
    volume = docker.volume.create(**kwargs)
    try:
        yield volume
    finally:
        volume.remove()


def run_step_command(
    docker: DockerClient,
    image: Image | str,
    command: list[str],
    container_name: str,
    workbench_volume: Volume,
    labels: dict[str, str],
    step_reporter: StepReporter,
):
    workdir = "/root/maat-workbench"

    try:
        stream = docker.container.run(
            image=image,
            command=command,
            name=container_name,
            labels=labels,
            remove=True,
            volumes=[(workbench_volume, workdir, "rw")],
            workdir=workdir,
            stream=True,
        )
        for source, line in stream:
            match source:
                case "stdout":
                    step_reporter.append_stdout_line(line)
                case "stderr":
                    step_reporter.append_stderr_line(line)
        step_reporter.set_exit_code(0)
    except DockerException as e:
        # Docker run uses exit codes 125, 126, 127 to signal Docker daemon errors.
        # Anything other than these values comes from the container process.
        # Ref: https://docs.docker.com/engine/containers/run/#exit-status
        exit_code = e.return_code
        step_reporter.set_exit_code(exit_code)
        if exit_code in [125, 126, 127]:
            raise


def kill_containers_with_run_token(docker: DockerClient, run_token: str):
    containers = docker.container.list(filters={"label": f"{RUN_LABEL}={run_token}"})
    for container in containers:
        container.kill()


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def token() -> str:
    """
    Generate a short base32-encoded token based on high-precision current time.
    """
    current_time = time.time_ns()
    packed_time = struct.pack(">Q", current_time)
    return base64.b32encode(packed_time).decode("utf-8").rstrip("=").lower()
