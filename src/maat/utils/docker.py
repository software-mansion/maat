from python_on_whales import Image, DockerClient


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
