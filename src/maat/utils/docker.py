from python_on_whales import Image, DockerClient


def inspect_image(image: str, docker: DockerClient) -> Image:
    return docker.image.inspect(image)
