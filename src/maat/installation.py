import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.absolute()


def this_maat_commit() -> str:
    # CI ships the sources with `git archive`, which does not include a .git
    # directory, so there is no repo to query on the runner. The workflow passes
    # the archived commit through MAAT_COMMIT; prefer it when set.
    env = os.environ.get("MAAT_COMMIT")
    if env:
        return env.strip()

    return (
        subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO
        )
        .decode("utf-8")
        .strip()
    )
