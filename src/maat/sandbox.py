import importlib

from docker.models.images import Image
from rich.console import Console

from maat.runner.docker import MaatDockerClient
from maat.semver import Semver

SANDBOX_REPOSITORY = "maat/sandbox"


def build(
    scarb: Semver, foundry: Semver, docker: MaatDockerClient, console: Console
) -> Image:
    with console.status("Building sandbox image..."):
        with importlib.resources.path("maat.agent") as path:
            image = docker.build_image_with_streaming_output(
                path=str(path),
                rm=True,
                pull=True,
                tag=f"{SANDBOX_REPOSITORY}:scarb-{scarb}-foundry-{foundry}",
                buildargs={
                    "ASDF_SCARB_VERSION": scarb,
                    "ASDF_STARKNET_FOUNDRY_VERSION": foundry,
                },
            )

            # Tag this image as "latest" for easier access (no need to remember precise versions used)
            # via Docker CLI when debugging.
            image.tag(SANDBOX_REPOSITORY, "latest", force=True)

    console.log(f":rocket: Successfully built sandbox image: {' or '.join(image.tags)}")

    return image
