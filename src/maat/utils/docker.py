import re


def sanitize_for_docker(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
