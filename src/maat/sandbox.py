import importlib.resources
from pathlib import Path
from typing import NamedTuple

from python_on_whales import DockerClient, Image
from rich.console import Console

from maat.model import Semver
from maat.utils.docker import sanitize_for_docker, inspect_image

SANDBOX_REPOSITORY = "ghcr.io/software-mansion/maat/sandbox"
MAAT_CACHE = "/mnt/maat-cache"
MAAT_WORKBENCH = "/mnt/maat-workbench"


def build(
    scarb: Semver,
    foundry: Semver,
    docker: DockerClient,
    console: Console,
    cache_from: str | dict[str, str] | list[dict[str, str]] | None = None,
    cache_to: str | dict[str, str] | None = None,
    cache: bool = True,
    output: str | dict[str, str] = None,
    iidfile: Path | None = None,
) -> Image:
    output_dict: dict[str, str] = {}
    match output:
        case str():
            # Parse output string into a dictionary
            for part in output.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    output_dict[key] = value
                else:
                    output_dict["type"] = part
        case dict():
            output_dict = output

    with console.status("Building sandbox image..."):
        with importlib.resources.path("maat.agent") as path:
            image = docker.buildx.build(
                context_path=str(path),
                build_args={
                    "ASDF_SCARB_VERSION": scarb,
                    "ASDF_STARKNET_FOUNDRY_VERSION": foundry,
                    "MAAT_CACHE": MAAT_CACHE,
                    "MAAT_WORKBENCH": MAAT_WORKBENCH,
                },
                pull=True,
                tags=[
                    f"{SANDBOX_REPOSITORY}:scarb-{sanitize_for_docker(scarb)}-foundry-{sanitize_for_docker(foundry)}",
                    # Tag this image as "latest" for easier access (no need to remember precise versions used)
                    # via Docker CLI when debugging.
                    f"{SANDBOX_REPOSITORY}:latest",
                ],
                cache_from=cache_from,
                cache_to=cache_to,
                cache=cache,
                output=output_dict,
            )
            assert isinstance(image, Image)

    if iidfile:
        iidfile.write_text(image.id)

    console.log(
        f":rocket: Successfully built sandbox image: {' or '.join(image.repo_tags)}"
    )

    return image


class ToolVersions(NamedTuple):
    scarb: Semver
    foundry: Semver


def tool_versions(image: Image | str, docker: DockerClient) -> ToolVersions:
    image = inspect_image(image, docker)
    return ToolVersions(
        scarb=image.config.labels["maat.scarb.version"],
        foundry=image.config.labels["maat.foundry.version"],
    )
