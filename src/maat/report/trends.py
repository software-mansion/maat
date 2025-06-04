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

    # Find reference, min, and max values.
    reference_value = row[reference_idx]
    ref_secs = reference_value.total_seconds()
    min_value = min(row)
    max_value = max(row)

    # Compute trend for each value.
    for value in row:
        value_secs = value.total_seconds()

        trend = Trend(
            ratio=(value_secs - ref_secs) / ref_secs,
            is_extreme=value == min_value or value == max_value,
        )

        trends.append(trend)

    return trends
