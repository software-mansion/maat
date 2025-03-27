import importlib

from python_on_whales import DockerClient, Image
from rich.console import Console

from maat.semver import Semver

SANDBOX_REPOSITORY = "maat/sandbox"


def build(
    scarb: Semver,
    foundry: Semver,
    docker: DockerClient,
    console: Console,
) -> Image:
    with console.status("Building sandbox image..."):
        with importlib.resources.path("maat.agent") as path:
            image = docker.buildx.build(
                context_path=str(path),
                build_args={
                    "ASDF_SCARB_VERSION": scarb,
                    "ASDF_STARKNET_FOUNDRY_VERSION": foundry,
                },
                pull=True,
                tags=[
                    f"{SANDBOX_REPOSITORY}:scarb-{scarb}-foundry-{foundry}",
                    # Tag this image as "latest" for easier access (no need to remember precise versions used)
                    # via Docker CLI when debugging.
                    f"{SANDBOX_REPOSITORY}:latest",
                ],
            )
            assert isinstance(image, Image)

    console.log(
        f":rocket: Successfully built sandbox image: {' or '.join(image.repo_tags)}"
    )

    return image
