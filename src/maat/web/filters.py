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


def timedeltaformat(value: timedelta) -> str:
    total_seconds = value.total_seconds()

    # If less than 1 second, show milliseconds with 2 digits precision
    if total_seconds < 1:
        return f"{total_seconds:.2f}s"

    # Round to the nearest second for durations >= 1 second.
    total_seconds = round(total_seconds)

    # Recalculate days, hours, minutes, seconds.
    days, remainder = divmod(total_seconds, 86400)  # 86400 seconds in a day
    hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
    minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

    # Build the string with only non-zero parts.
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:  # Always include seconds if no other parts.
        parts.append(f"{seconds}s")

    return " ".join(parts)
