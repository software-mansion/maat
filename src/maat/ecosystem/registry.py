from typing import Self
from urllib.parse import urljoin

import requests
from pydantic import BaseModel, RootModel

from maat.ecosystem import scarbs_xyz
from maat.model import Step
from maat.utils.smart_sort import smart_sort_key
from maat.utils.unique_id import snowflake_id


def fetch_version(registry_url: str, package: str) -> str:
    registry_config = RegistryConfig.fetch(registry_url)
    records = IndexRecords.fetch(registry_config, package)
    return records.latest_version()


def setup_registry(registry_url: str, package: str) -> list[Step]:
    registry_config = RegistryConfig.fetch(registry_url)
    records = IndexRecords.fetch(registry_config, package)

    latest = records.latest_version()
    dl_url = registry_config.expand_dl(package, latest)

    # Using unique IDs to reduce risks of potential conflicts with archive contents.
    dl_path = f"archive-{snowflake_id()}.tar.zstd"

    return [
        Step(run=["curl", "-sSLf", dl_url, "-o", dl_path], setup=True),
        Step(
            run=["tar", "--zstd", "-xf", dl_path, "--strip-components", "1"],
            setup=True,
        ),
    ]


class RegistryConfig(BaseModel):
    dl: str
    index: str

    @classmethod
    def fetch(cls, registry_url: str) -> Self:
        url = cls.config_json_url(registry_url)
        return cls.model_validate_json(requests.get(url).content)

    @classmethod
    def config_json_url(cls, registry_url: str) -> str:
        if registry_url == scarbs_xyz.BASE_URL:
            # Workaround for https://github.com/software-mansion/scarbs.xyz/issues/262
            return urljoin(registry_url, "/api/v1/index/config.json")
        else:
            return urljoin(registry_url, "/config.json")

    def expand_dl(self, package: str, version: str) -> str:
        return self.dl.replace("{package}", package).replace("{version}", version)

    def expand_index(self, package: str) -> str:
        return self.index.replace("{prefix}", _package_prefix(package)).replace(
            "{package}", package
        )


class IndexRecord(BaseModel):
    v: str


class IndexRecords(RootModel):
    root: list[IndexRecord]

    @classmethod
    def fetch(cls, registry: RegistryConfig, package: str) -> Self:
        url = registry.expand_index(package)
        return cls.model_validate_json(requests.get(url).content)

    def latest_version(self) -> str:
        latest_record = max(self.root, key=lambda record: smart_sort_key(record.v))
        return latest_record.v


def _package_prefix(name: str) -> str:
    """Make a path to a package directory, which aligns to the index directory layout."""
    match len(name):
        case 1:
            return "1"
        case 2:
            return "2"
        case 3:
            return f"3/{name[:1]}"
        case _:
            return f"{name[:2]}/{name[2:4]}"
