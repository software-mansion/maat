from maat.runner.model import TestStep


def setup_registry(registry_url: str, package: str) -> list[TestStep]:
    raise NotImplementedError


def fetch_all_packages(registry_url: str) -> list[str]:
    # TODO
    return []
