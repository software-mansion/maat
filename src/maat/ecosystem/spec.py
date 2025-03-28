from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel

from maat.ecosystem.git import setup_git
from maat.ecosystem.registry import fetch_all_packages, setup_registry
from maat.runner.model import Step

_GITHUB_URL = "https://github.com/"
_SCARBS_XYZ = "https://scarbs.xyz/"

type Ecosystem = EcosystemProject | list[Ecosystem] | Callable[[], Ecosystem]


class EcosystemProject(BaseModel, ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def setup(self) -> list[Step]:
        pass


class _Git(EcosystemProject):
    repo: str

    @property
    def name(self) -> str:
        if self.repo.startswith(_GITHUB_URL):
            return self.repo.removeprefix(_GITHUB_URL).removesuffix("/")
        else:
            return _human_url(self.repo)

    def setup(self) -> list[Step]:
        return setup_git(repo=self.repo)


class _Registry(EcosystemProject):
    registry_url: str
    package: str

    @property
    def name(self) -> str:
        name = self.package

        if self.registry_url != _SCARBS_XYZ:
            name += f"@{_human_url(self.registry_url)}"

        return name

    def setup(self) -> list[Step]:
        return setup_registry(
            registry_url=self.registry_url,
            package=self.package,
        )


def git(repo: str) -> Ecosystem:
    return _Git(repo=repo)


def github(repo: str) -> Ecosystem:
    return git(f"https://github.com/{repo}")


def registry(registry_url: str, package: str) -> Ecosystem:
    return _Registry(registry_url=registry_url, package=package)


def scarbs(package: str) -> Ecosystem:
    return registry(_SCARBS_XYZ, package)


def entire_registry(registry_url: str) -> Ecosystem:
    def lazy() -> Ecosystem:
        return [
            registry(registry_url, package)
            for package in fetch_all_packages(registry_url)
        ]

    return lazy


def entire_scarbs() -> Ecosystem:
    return entire_registry(_SCARBS_XYZ)


def _human_url(url: str) -> str:
    return url.removeprefix("http://").removeprefix("https://").removesuffix("/")
