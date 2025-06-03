import requests
from cache_to_disk import cache_to_disk

from maat.model import Step

GITHUB_URL = "https://github.com/"


@cache_to_disk(1)
def fetch_commit_hash(repo: str) -> str:
    if repo.startswith(GITHUB_URL):
        # Make a GET request to GitHub API, which is faster than calling Git.
        repo_path = repo.split("github.com/")[-1].rstrip("/")

        # Get the latest commit from the default branch (no branch specified = default branch).
        response = requests.get(
            f"https://api.github.com/repos/{repo_path}/commits",
            params={"per_page": 1},  # Only get the latest commit.
        )
        response.raise_for_status()
        commits = response.json()
        if not commits:
            raise ValueError(f"no commits found for repo: {repo}")
        return commits[0]["sha"][:9]
    else:
        raise NotImplementedError


def setup_git(repo: str) -> list[Step]:
    return [
        Step(run=["git", "clone", "--depth", "1", "--no-tags", repo, "."], setup=True),
    ]
