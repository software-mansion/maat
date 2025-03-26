from abc import ABC, abstractmethod

from maat.runner.model import TestStep


class TestWorkflow(ABC):
    @abstractmethod
    def steps(self) -> list[TestStep]:
        pass


class _Build(TestWorkflow):
    def steps(self) -> list[TestStep]:
        return [
            TestStep(name="build", run="scarb --json build --test"),
        ]


Build = _Build()


class _Lint(TestWorkflow):
    def steps(self) -> list[TestStep]:
        return [
            TestStep(name="test", run="scarb --json lint"),
        ]


Lint = _Lint()


class _Test(TestWorkflow):
    def steps(self) -> list[TestStep]:
        return [
            TestStep(name="test", run="scarb --json test"),
        ]


Test = _Test()

# TODO: LS workflow

All: list[TestWorkflow] = [Build, Lint, Test]
