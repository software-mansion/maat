"""All functions exported from this module are available as filters in templates."""

from datetime import datetime, timedelta


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


def datetimeformat(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def timedeltaformat(value: timedelta, /, precision=2) -> str:
    mm, ss = divmod(value.seconds, 60)
    hh, mm = divmod(mm, 60)
    s = f"{hh:d}:{mm:02d}:{ss:02d}"

    if value.days:

        def plural(n):
            return n, abs(n) != 1 and "s" or ""

        s = ("%d day%s, " % plural(value.days)) + s

    if value.microseconds:
        # Round to the nearest 1/(10**precision)th of a second.
        # For example, 0:07:12.211526 -> 0:07:12.21 (when precision = 2).
        ms = round(value.microseconds / 10**6, precision)
        # Add fractional seconds, omit leading `0` with that `[1:]`.
        s += f"{ms:.{precision}f}"[1:]

    return s
