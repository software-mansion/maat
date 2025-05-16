import re

from python_on_whales import Image, DockerClient


def sanitize_for_docker(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def inspect_image(image: Image | str, docker: DockerClient) -> Image:
    if isinstance(image, str):
        return docker.image.inspect(image)
    else:
        return image


def image_id(image: Image | str) -> str:
    if isinstance(image, Image):
        return image.id
    else:
        return image
