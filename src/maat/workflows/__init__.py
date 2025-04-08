from typing import Callable

from maat.model import Step
from maat.workflows import build_and_lint, patch, test

type Workflow = Callable[[], list[Step]]

ALL: list[Workflow] = [patch.workflow, build_and_lint.workflow, test.workflow]
