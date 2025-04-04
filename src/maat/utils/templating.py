type ClassNames = (
    str | None | list[str | None] | tuple[str | None] | dict[str, bool | None]
)


def clsx(*args: ClassNames, **kwargs: bool) -> str:
    """Port of JS `clsx` helper."""
    classes: list[str] = []
    for arg in args:
        if arg:
            if isinstance(arg, str):
                classes.append(arg)
            elif isinstance(arg, (list, tuple)):
                classes.extend([c for c in arg if c])
            elif isinstance(arg, dict):
                classes.extend([k for k, v in arg.items() if v])
    for k, v in kwargs.items():
        if v:
            classes.append(k)
    return " ".join(classes)
