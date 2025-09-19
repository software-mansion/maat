from python_on_whales import DockerClient, Image, Volume

from maat.runner.cancellation_token import CancellationToken
from maat.utils.docker import inspect_image


def bake_volume(
    docker: DockerClient,
    image: Image | str,
    volume: Volume,
    mount: str,
    ct: CancellationToken,
) -> Image:
    """
    Creates a new image derived from the provided one, with the provided volume baked as an extra
    layer as if it was mounted at the specified path.
    """

    image = inspect_image(image, docker)

    with docker.container.run(
        image=image,
        command=[
            "bash",
            "-c",
            f"mkdir -p '{mount}' && cp -a /bake-volume-mnt/. '{mount}'",
        ],
        detach=True,
        labels=ct.container_labels,
        volumes=[(volume, "/bake-volume-mnt")],
    ) as container:
        if (code := docker.container.wait(container)) != 0 and not ct.is_cancelled:
            raise RuntimeError(f"baking volume failed with exit code: {code}")

        return container.commit()
