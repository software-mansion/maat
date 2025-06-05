from datetime import timedelta

from pydantic import BaseModel


class Trend(BaseModel):
    """Represents the trend of a metric compared to a reference value."""

    ratio: float
    """`(value - reference) / reference`. Negative ratios indicate a decrease."""

    is_extreme: bool
    """States whether this value was the lowest/highest in the input set."""

    @property
    def symbol(self) -> str:
        if self.ratio < 0.0:
            if self.is_extreme:
                return "⤓"
            else:
                return "↓"
        elif self.ratio > 0.0:
            if self.is_extreme:
                return "⤒"
            else:
                return "↑"
        else:
            return "∗"

    @property
    def color_class(self) -> str:
        if self.ratio < 0.0:
            return "text-positive"
        elif self.ratio > 0.0:
            return "text-negative"
        else:
            return "text-neutral"


def trends_row(row: list[timedelta], reference_idx: int) -> list[Trend]:
    trends = []
    reference_value = row[reference_idx]
    min_value, max_value = _find_extremes(row)

    for value in row:
        trend = _calculate_trend(value, reference_value, min_value, max_value)
        trends.append(trend)
    return trends


def trends_row_with_optionals(
    row: list[timedelta | None],
    reference_idx: int,
) -> list[Trend | None]:
    if row[reference_idx] is None:
        return [None] * len(row)

    trends = []
    reference_value = row[reference_idx]
    min_value, max_value = _find_extremes(row)

    for value in row:
        if value is None:
            trends.append(None)
        else:
            trend = _calculate_trend(value, reference_value, min_value, max_value)
            trends.append(trend)
    return trends


def _find_extremes(
    values: list[timedelta | None],
) -> tuple[timedelta | None, timedelta | None]:
    """Find min and max values, filtering out None values."""
    non_none_values = [v for v in values if v is not None]
    if not non_none_values:
        return None, None
    return min(non_none_values), max(non_none_values)


def _calculate_trend(
    value: timedelta,
    reference_value: timedelta,
    min_value: timedelta | None,
    max_value: timedelta | None,
) -> Trend:
    """Calculate trend for a single value."""
    ref_secs = reference_value.total_seconds()
    value_secs = value.total_seconds()
    return Trend(
        ratio=(value_secs - ref_secs) / ref_secs,
        is_extreme=value == min_value or value == max_value,
    )
