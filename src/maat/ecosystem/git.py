import subprocess

from maat.model import Step


def fetch_commit_hash(repo: str) -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", repo, "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            commit_hash = result.stdout.split()[0]
            return commit_hash[:9]
        else:
            raise ValueError(f"failed to get commit hash via git: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise ValueError("git command timed out")


def setup_git(repo: str) -> list[Step]:
    return [
        Step(run=["git", "clone", "--depth", "1", "--no-tags", repo, "."], setup=True),
    ]
