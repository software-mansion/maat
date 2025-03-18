from pathlib import Path

REPO = Path(__file__).parent.parent.parent.absolute()


def this_maat_commit() -> str:
    import subprocess

    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .decode("utf-8")
        .strip()
    )
