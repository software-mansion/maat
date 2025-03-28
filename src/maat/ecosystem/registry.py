from maat.runner.model import Step


def setup_registry(registry_url: str, package: str) -> list[Step]:
    raise NotImplementedError


def fetch_all_packages(registry_url: str) -> list[str]:
    # TODO
    return []
