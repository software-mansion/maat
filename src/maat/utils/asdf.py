from pathlib import Path


def asdf_set(context: Path, tool: str, version: str):
    tool_versions = context / ".tool-versions"
    tool_versions.touch(exist_ok=True)

    spec = tool_versions.read_text().splitlines()

    updated_spec = []
    tool_line_found = False

    for line in spec:
        if line.startswith(f"{tool} "):
            updated_spec.append(f"{tool} {version}")
            tool_line_found = True
        else:
            updated_spec.append(line)

    if not tool_line_found:
        updated_spec.append(f"{tool} {version}")

    spec = "\n".join(updated_spec)

    tool_versions.write_text(spec)
