import shlex


def join_command(run: str | list[str]) -> str:
    return shlex.join(run) if isinstance(run, list) else run


def split_command(run: str | list[str]) -> list[str]:
    return shlex.split(run) if isinstance(run, str) else run
