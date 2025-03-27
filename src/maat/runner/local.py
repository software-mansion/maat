import os
import re
import shlex
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta

from python_on_whales import DockerClient, Image
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

from maat import ReportBuilder
from maat.runner.model import Test, TestStep, TestSuite


# noinspection PyBroadException
def execute_test_locally(
    test: Test,
    sandbox: Image | str,
    docker: DockerClient,
    report_builder: ReportBuilder,
    progress: Progress,
):
    workdir = "/root/maat-workbench"

    with (
        TestRunMonitor(test, progress) as monitor,
        report_builder.test(test) as trb,
        ephemeral_volume(
            docker, volume_name=f"maat-{sanitize_name(test.name)}"
        ) as volume,
    ):
        for step in test.steps:
            with monitor.will_run_step(step):
                if isinstance(step.run, str):
                    command = shlex.split(step.run)
                else:
                    command = step.run

                try:
                    stdout = docker.container.run(
                        image=sandbox,
                        command=command,
                        name=f"maat-{sanitize_name(test.name)}-{sanitize_name(step.name)}",
                        remove=True,
                        volumes=[(volume, workdir, "rw")],
                        workdir=workdir,
                    )

                    trb.report(
                        step=step,
                        exit_code=0,
                        stdout=stdout,
                        stderr="",
                    )
                except Exception:
                    progress.console.print_exception()


def execute_test_suite_locally(
    test_suite: TestSuite,
    jobs: int | None,
    docker: DockerClient,
    report_builder: ReportBuilder,
    console: Console,
):
    jobs = jobs or os.process_cpu_count() or 1

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

        def worker_main(current_test: Test):
            execute_test_locally(
                current_test,
                sandbox=test_suite.sandbox,
                docker=docker,
                report_builder=report_builder,
                progress=progress,
            )
            progress.advance(task)

        for test in test_suite.tests:
            pool.submit(worker_main, test)

        pool.shutdown(wait=True)

        progress.update(task, visible=False)
        progress.console.log(
            f":test_tube: [progress.elapsed]{timedelta(seconds=progress.tasks[task].finished_time or 0)}[/progress.elapsed] [progress.description bold]Experiment[/progress.description bold]"
        )


class TestRunMonitor:
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


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
