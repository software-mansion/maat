import importlib.util

from pydantic import BaseModel, ConfigDict
from rich.console import Console

from maat.ecosystem.spec import Ecosystem
from maat.installation import REPO


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(strict=True)

    ecosystem: Ecosystem

    @classmethod
    def load(cls, workspace_name: str) -> "WorkspaceSettings":
        # Construct the path to the workspace Python script
        settings_script = REPO / "workspaces" / f"{workspace_name}.py"
        if not settings_script.exists():
            console = Console()
            console.log(
                f"[yellow] Workspace [bold]{workspace_name}`[/bold] settings script not found, copying from [bold]release.py[/bold]..."
            )
            settings_script.write_text(
                (REPO / "workspaces" / "release.py").read_text(), encoding="utf-8"
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
    def load(cls, name: str) -> "Workspace":
        return cls(name=name, settings=WorkspaceSettings.load(name))
