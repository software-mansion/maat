import re

from docker import DockerClient
from docker.errors import BuildError
from docker.models.images import Image
from docker.utils.json_stream import json_stream


class MaatDockerClient(DockerClient):
    """
    A wrapper around the `DockerClient` class that has default constructor (useful for integrating with `click`)
    which also contains some extra utilities.
    """

    def __init__(self, **kwargs):
        """
        Initialize the MaatDockerClient by wrapping `DockerClient`.

        :param kwargs: Keyword arguments passed to `DockerClient.from_env`.
        """
        real_client = DockerClient.from_env(**kwargs)
        self.api = real_client.api

    def build_image_with_streaming_output(self, **kwargs) -> Image:
        """
        Like `self.images.build`, but streams output to the console.
        """

        # Call the low-level API directly to get the response stream
        resp = self.api.build(**kwargs)
        if isinstance(resp, str):
            image = self.images.get(resp)
            return image

        # Process the stream
        last_event = None
        image_id = None

        # Stream the build output
        for chunk in json_stream(resp):
            if "error" in chunk:
                raise BuildError(chunk["error"], None)
            if "stream" in chunk:
                # Print the stream output
                print(chunk["stream"], end="")

                # Check if this is the success message
                match = re.search(
                    r"(^Successfully built |sha256:)([0-9a-f]+)$", chunk["stream"]
                )
                if match:
                    image_id = match.group(2)
            last_event = chunk

        if image_id:
            image = self.images.get(image_id)
            return image

        raise BuildError(last_event or "Unknown", None)
