import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from docker.models.containers import Container
from docker.models.images import Image
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
from maat.runner.docker import MaatDockerClient
from maat.runner.model import Test, TestSuite


def execute_test_locally(
    test: Test,
    sandbox: Image | str,
    docker: MaatDockerClient,
    report_builder: ReportBuilder,
    progress: Progress,
):
    status_icon = ":question_mark:"
    task = progress.add_task(
        test.name,
        start=False,
        total=sum(not s.setup for s in test.steps),
    )

    # noinspection PyBroadException
    try:
        container: Container = docker.containers.run(
            sandbox,
            detach=True,
            name=f"maat-{sanitize_name(test.name)}",
            auto_remove=True,
            remove=True,
            working_dir="/root/maat-workbench",
        )

        try:
            with report_builder.test(test) as trb:
                for step in test.steps:
                    progress.update(task, description=f"{test.name}: {step.name}")

                    if not step.setup and progress.tasks[task].start_time is None:
                        progress.start_task(task)

                    exit_code, (stdout, stderr) = container.exec_run(
                        step.run, demux=True
                    )

                    trb.report(
                        step=step,
                        exit_code=exit_code,
                        stdout=stdout,
                        stderr=stderr,
                    )

                    if not step.setup:
                        progress.advance(task)

            status_icon = ":white_check_mark:"
        finally:
            container.remove(force=True)
    except Exception:
        status_icon = ":x:"
        progress.console.print_exception()
    finally:
        progress.update(task, visible=False)
        progress.console.log(
            f"{status_icon} [progress.elapsed]{timedelta(seconds=progress.tasks[task].finished_time or 0)}[/progress.elapsed] [progress.description]{test.name}[/progress.description]"
        )


def execute_test_suite_locally(
    test_suite: TestSuite,
    jobs: int | None,
    docker: MaatDockerClient,
    report_builder: ReportBuilder,
    console: Console,
):
    jobs = jobs or os.process_cpu_count() or 1

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("RT"),
        TimeRemainingColumn(),
        TextColumn("ET"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
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


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
