import importlib.resources
from pathlib import Path
from typing import Literal

from python_on_whales import DockerClient, Image


def asdf_set(context: Path, tool: str, version: str):
    tool_versions = context / ".tool-versions"
    tool_versions.touch(exist_ok=True)

    spec = tool_versions.read_text().splitlines()

    updated_spec = []
    tool_line_found = False

    for line in spec:
        if line.startswith(f"{tool} "):
            updated_spec.append(f"{tool} {version}")
            tool_line_found = True
        else:
            updated_spec.append(line)

    if not tool_line_found:
        updated_spec.append(f"{tool} {version}")

    spec = "\n".join(updated_spec)

    tool_versions.write_text(spec)


def asdf_latest(
    docker: DockerClient,
    name: Literal["scarb", "starknet-foundry"],
    version: str | None = None,
) -> str:
    with importlib.resources.path("maat.utils.asdf") as path:
        image = docker.buildx.build(context_path=str(path), pull=True)
        assert isinstance(image, Image)

    command = ["latest", name]
    if version is not None:
        command.append(version)

    return docker.container.run(image, command, remove=True)
