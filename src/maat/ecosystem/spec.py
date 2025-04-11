import re
from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel

from maat.ecosystem import scarbs_xyz
from maat.ecosystem.git import setup_git
from maat.ecosystem.registry import setup_registry
from maat.ecosystem.scarbs_xyz import BASE_URL
from maat.model import Step

_GITHUB_URL = "https://github.com/"

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

        if self.registry_url != BASE_URL:
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
    return registry(BASE_URL, package)


def entire_scarbs(*, blacklist: list[str | re.Pattern] = None) -> Ecosystem:
    if blacklist is None:
        blacklist = []

    def is_blacklisted(package: str) -> bool:
        for rule in blacklist:
            match rule:
                case re.Pattern() if re.fullmatch(rule, package):
                    return True
                case _ if rule == package:
                    return True
        return False

    def lazy() -> Ecosystem:
        return [
            registry(BASE_URL, package)
            for package in scarbs_xyz.fetch_all_packages()
            if not is_blacklisted(package)
        ]

    return lazy


def _human_url(url: str) -> str:
    return url.removeprefix("http://").removeprefix("https://").removesuffix("/")
