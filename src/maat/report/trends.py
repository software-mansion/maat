from datetime import timedelta
from typing import Self

from pydantic import BaseModel


class Trend(BaseModel):
    """Represents the trend of a metric compared to a reference value."""

    ratio: float
    """`(value - reference) / reference`. Negative ratios indicate a decrease."""

    is_extreme: bool
    """States whether this value was the lowest/highest in the input set."""

    @classmethod
    def new(
        cls,
        value: timedelta,
        reference_value: timedelta | None,
        min_value: timedelta | None,
        max_value: timedelta | None,
    ) -> Self:
        """Calculate trend for a single value."""
        value_secs = value.total_seconds()

        if reference_value is None:
            # If reference represents a failure, then any value is an infinite improvement.
            ratio = float("-inf")
        else:
            ref_secs = reference_value.total_seconds()
            if ref_secs == 0.0:
                if value_secs == 0.0:
                    ratio = 0.0  # No change: 0 → 0.
                elif value_secs > 0.0:
                    ratio = float("inf")  # Infinite increase: 0 → positive.
                else:
                    ratio = float("-inf")  # Infinite decrease: 0 → negative.
            else:
                ratio = (value_secs - ref_secs) / ref_secs

        return cls(
            ratio=ratio,
            is_extreme=value == min_value or value == max_value,
        )

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
            return "="

    @property
    def percentage(self) -> str:
        if self.ratio == float("inf"):
            return "∞"
        elif self.ratio == float("-inf"):
            return "-∞"
        else:
            return f"{round(self.ratio * 100)}%"

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
        trend = Trend.new(value, reference_value, min_value, max_value)
        trends.append(trend)
    return trends


def trends_row_with_optionals(
    row: list[timedelta | None],
    reference_idx: int,
) -> list[Trend | None]:
    trends = []
    reference_value = row[reference_idx]
    min_value, max_value = _find_extremes(row)

    for value in row:
        if value is None:
            trends.append(None)
        else:
            trend = Trend.new(value, reference_value, min_value, max_value)
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
