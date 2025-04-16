import requests
from cache_to_disk import cache_to_disk

from maat.model import Step

GITHUB_URL = "https://github.com/"


@cache_to_disk(1)
def fetch_commit_hash(repo: str) -> str:
    if repo.startswith(GITHUB_URL):
        # Make a GET request to GitHub API, which is faster than calling Git.
        repo_path = repo.split("github.com/")[-1].rstrip("/")
        response = requests.get(
            f"https://api.github.com/repos/{repo_path}/branches/main"
        )
        response.raise_for_status()
        return response.json()["commit"]["sha"][:9]
    else:
        raise NotImplementedError


def setup_git(repo: str) -> list[Step]:
    return [
        Step.setup(["git", "clone", "--depth", "1", "--no-tags", repo, "."]),
    ]
