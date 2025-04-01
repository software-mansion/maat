from contextlib import contextmanager

from python_on_whales import DockerClient, Volume

from maat.runner.retry import retry


@contextmanager
def ephemeral_volume(docker: DockerClient, **kwargs):
    volume = docker.volume.create(**kwargs)
    try:
        yield volume
    finally:
        _remove_volume(volume)


@retry
def _remove_volume(volume: Volume):
    volume.remove()
