from maat.model import Semver


def is_unstable_semver(version: Semver) -> bool:
    return "+" in version or "-" in version
