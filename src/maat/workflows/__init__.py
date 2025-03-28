from typing import Callable

from maat.model import Step
from maat.workflows import build, lint, test

type Workflow = Callable[[], list[Step]]

ALL: list[Workflow] = [build.workflow, lint.workflow, test.workflow]
