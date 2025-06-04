import enum
from datetime import timedelta


class Trend(enum.Enum):
    """Represents the trend of a metric compared to a reference value."""

    LOWEST = enum.auto()
    """The value is the lowest among all values."""

    HIGHEST = enum.auto()
    """The value is the highest among all values."""

    REFERENCE = enum.auto()
    """The value is the reference value (and not the lowest or highest)."""

    LOWER = enum.auto()
    """The value is lower than the reference value."""

    HIGHER = enum.auto()
    """The value is higher than the reference value."""

    NONE = enum.auto()
    """No trend information is available."""

    @enum.property
    def symbol(self) -> str:
        match self:
            case self.LOWEST:
                return "⤓"
            case self.HIGHEST:
                return "⤒"
            case self.REFERENCE:
                return "∗"
            case self.LOWER:
                return "↓"
            case self.HIGHER:
                return "↑"
            case self.NONE:
                return ""
            case _:
                raise ValueError(f"invalid trend: {self}")


def trends_row(row: list[timedelta], reference_idx: int) -> list[Trend]:
    trends = []

    # Find reference, min, and max values
    reference_value = row[reference_idx]
    min_value = min(row)
    max_value = max(row)

    # Compute trend for each value
    for value in row:
        if value == min_value:
            trend = Trend.LOWEST
        elif value == max_value:
            trend = Trend.HIGHEST
        elif value == reference_value:
            if value != min_value and value != max_value:
                trend = Trend.REFERENCE
            else:
                trend = Trend.NONE
        elif value < reference_value:
            trend = Trend.LOWER
        else:  # value > reference_value
            trend = Trend.HIGHER

        trends.append(trend)

    return trends
