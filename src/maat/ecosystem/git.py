from maat.runner.model import TestStep


def setup_git(repo: str) -> list[TestStep]:
    return [
        TestStep(
            name="git clone",
            run=["git", "clone", "--depth", "1", "--no-tags", repo, "."],
            setup=True,
        ),
    ]
