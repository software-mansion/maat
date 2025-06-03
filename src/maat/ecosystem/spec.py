import re
import typing
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

import maat.ecosystem.git as _git
import maat.ecosystem.registry as _registry
import maat.ecosystem.scarbs_xyz as _scarbs_xyz
from maat.model import Step

if typing.TYPE_CHECKING:
    from maat.workspace import WorkspaceSettings

type Ecosystem = EcosystemProject | list[Ecosystem] | Callable[[], Ecosystem]


class EcosystemProject(BaseModel, ABC):
    workdir: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def fetch_rev(self) -> str:
        pass

    @abstractmethod
    def setup(self) -> list[Step]:
        pass


class _Git(EcosystemProject):
    repo: str

    @property
    def name(self) -> str:
        if self.repo.startswith(_git.GITHUB_URL):
            return self.repo.removeprefix(_git.GITHUB_URL).removesuffix("/")
        else:
            return _human_url(self.repo)

    def fetch_rev(self) -> str:
        return _git.fetch_commit_hash(repo=self.repo)

    def setup(self) -> list[Step]:
        return _git.setup_git(repo=self.repo)


class _Registry(EcosystemProject):
    registry_url: str
    package: str

    @property
    def name(self) -> str:
        name = self.package

        if self.registry_url != _scarbs_xyz.BASE_URL:
            name += f"@{_human_url(self.registry_url)}"

        return name

    def fetch_rev(self) -> str:
        return _registry.fetch_version(
            registry_url=self.registry_url,
            package=self.package,
        )

    def setup(self) -> list[Step]:
        return _registry.setup_registry(
            registry_url=self.registry_url,
            package=self.package,
        )


def git(repo: str, /, workdir: str | None = None) -> Ecosystem:
    return _Git(repo=repo, workdir=workdir)


def github(repo: str, /, workdir: str | None = None) -> Ecosystem:
    return git(f"https://github.com/{repo}", workdir=workdir)


def registry(registry_url: str, package: str) -> Ecosystem:
    return _Registry(registry_url=registry_url, package=package)


def scarbs(package: str) -> Ecosystem:
    return registry(_scarbs_xyz.BASE_URL, package)


def entire_scarbs(*, blacklist: list[str | re.Pattern] = None) -> Ecosystem:
    if blacklist is None:
        blacklist = []

    def is_blacklisted(package: str) -> bool:
        for rule in blacklist:
            match rule:
                case re.Pattern() if re.search(rule, package):
                    return True
                case _ if rule == package:
                    return True
        return False

    def lazy() -> Ecosystem:
        return [
            registry(_scarbs_xyz.BASE_URL, package)
            for package in _scarbs_xyz.fetch_all_packages()
            if not is_blacklisted(package)
        ]

    return lazy


def _human_url(url: str) -> str:
    return url.removeprefix("http://").removeprefix("https://").removesuffix("/")


def import_workspace(name: str) -> "WorkspaceSettings":
    from maat.workspace import WorkspaceSettings

    return WorkspaceSettings.load(name)


class ReportNameGenerationContext(Protocol):
    workspace: str
    scarb: str
    foundry: str
