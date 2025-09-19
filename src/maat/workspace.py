import importlib.util
from typing import Self, Callable

from pydantic import BaseModel, ConfigDict

from maat.ecosystem.spec import Ecosystem, ReportNameGenerationContext
from maat.installation import REPO


def _default_report_name_generator(ctx: ReportNameGenerationContext) -> str:
    return f"{ctx.workspace}-{ctx.scarb}-{ctx.foundry}"


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True)

    ecosystem: Ecosystem
    default_scarb: str | None = None
    default_foundry: str | None = None
    generate_report_name: Callable[[ReportNameGenerationContext], str] = (
        _default_report_name_generator
    )

    @classmethod
    def load(cls, workspace_name: str) -> Self:
        # Construct the path to the workspace Python script
        settings_script = REPO / "workspaces" / f"{workspace_name}.py"
        if not settings_script.exists():
            print(
                f"⚠️ Workspace '{workspace_name}' settings script not found, copying from local_example.py..."
            )
            settings_script.write_text(
                (REPO / "workspaces" / "local_example.py").read_text(), encoding="utf-8"
            )

        # Load the Python script as a module.
        spec = importlib.util.spec_from_file_location(workspace_name, settings_script)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load module from: {settings_script}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Use the module attributes to construct a WorkspaceSettings instance.
        kwargs = {
            key: value for key, value in vars(module).items() if not key.startswith("_")
        }
        return cls.model_validate(kwargs, context=dict(workspace_name=workspace_name))


class Workspace(BaseModel):
    name: str
    settings: WorkspaceSettings

    def __str__(self) -> str:
        return self.name

    @classmethod
    def load(cls, name: str) -> Self:
        return cls(name=name, settings=WorkspaceSettings.load(name))
