import base64
import struct
import threading
import time

from python_on_whales import DockerClient, DockerException
from python_on_whales.exceptions import NoSuchContainer


class CancellationToken:
    def __init__(self):
        self._run_event = threading.Event()
        self._run_event.set()

        current_time = time.time_ns()
        packed_time = struct.pack(">Q", current_time)
        self._label_token = (
            base64.b32encode(packed_time).decode("utf-8").rstrip("=").lower()
        )

    @property
    def is_cancelled(self) -> bool:
        return not self._run_event.is_set()

    def raise_if_cancelled(self):
        if self.is_cancelled:
            raise CancelledException

    @property
    def container_labels(self) -> dict[str, str]:
        return {"maat-ct": self._label_token}

    def cancel(self, docker: DockerClient):
        self._run_event.clear()
        self._kill_containers(docker)

    def _kill_containers(self, docker: DockerClient):
        containers = docker.container.list(
            filters={"label": f"maat-ct={self._label_token}"}
        )
        for container in containers:
            try:
                container.kill()
            except NoSuchContainer:
                continue
            except DockerException as e:
                if "is not running" in str(e):
                    continue
                else:
                    raise


class CancelledException(Exception):
    """Raised when an operation is cancelled."""

    pass
