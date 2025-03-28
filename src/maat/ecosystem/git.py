from maat.model import Step


def setup_git(repo: str) -> list[Step]:
    return [
        Step.setup(["git", "clone", "--depth", "1", "--no-tags", repo, "."]),
    ]
