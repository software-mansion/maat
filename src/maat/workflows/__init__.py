from typing import Callable

from maat.model import Step
from maat.workflows import build_and_lint, test

type Workflow = Callable[[], list[Step]]

ALL: list[Workflow] = [build_and_lint.workflow, test.workflow]
