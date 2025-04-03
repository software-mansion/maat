from contextlib import contextmanager

from python_on_whales import DockerClient, Volume
from retry import retry

from maat.utils.unique_id import unique_id


@contextmanager
def ephemeral_volume(docker: DockerClient):
    volume_name = f"maat-{unique_id()}"

    # noinspection PyBroadException
    try:
        docker.volume.remove(volume_name=volume_name)
    except Exception:
        pass

    volume = docker.volume.create(volume_name=volume_name)
    try:
        yield volume
    finally:
        _remove_volume(volume)


@retry(tries=5, delay=0.1, backoff=2)
def _remove_volume(volume: Volume):
    volume.remove()
