"""Missing data handling strategies for UOC.

Provides utility functions to fill or handle missing values in list or column formats.
"""

from __future__ import annotations

from typing import Any

from .config import MissingStrategy


def fill_missing(
    values: list[Any],
    strategy: MissingStrategy,
    default_value: Any = None,
) -> list[Any]:
    """Fill missing (None) values in a list using the specified strategy.

    Parameters:
        values: The list of values containing potential None values.
        strategy: The MissingStrategy to use.
        default_value: The value to use when strategy is MissingStrategy.DEFAULT.

    Returns:
        A new list with missing values handled.
    """
    if not values:
        return []

    if strategy == MissingStrategy.LEAVE:
        return list(values)

    if strategy == MissingStrategy.DEFAULT:
        return [v if v is not None else default_value for v in values]

    if strategy == MissingStrategy.FORWARD_FILL:
        result = []
        last_val = None
        for v in values:
            if v is not None:
                last_val = v
            result.append(last_val if v is None else v)
        return result

    if strategy == MissingStrategy.INTERPOLATE:
        # For non-timestamp-aware interpolation, treat indices as timestamps
        timestamps = [float(i) for i in range(len(values))]
        return fill_missing_column(timestamps, values, strategy, default_value)

    return list(values)


def fill_missing_column(
    timestamps: list[float],
    values: list[Any],
    strategy: MissingStrategy,
    default_value: Any = None,
) -> list[Any]:
    """Fill missing (None) values in a column with timestamp awareness.

    Useful for linear interpolation where timestamp spacing determines the interpolated value.

    Parameters:
        timestamps: A list of floats representing the timestamps.
        values: The list of values, corresponding 1-to-1 with timestamps.
        strategy: The MissingStrategy to use.
        default_value: The value to use when strategy is MissingStrategy.DEFAULT.

    Returns:
        A new list with missing values handled.
    """
    if not values:
        return []
    if len(values) != len(timestamps):
        raise ValueError("timestamps and values must have the same length.")

    if strategy != MissingStrategy.INTERPOLATE:
        return fill_missing(values, strategy, default_value)

    # Perform linear interpolation
    result = list(values)
    n = len(values)

    # Find segments to interpolate
    # We find all ranges [left, right] where values[left] is not None,
    # values[right] is not None, and all elements in between are None.
    # Elements before the first non-None and after the last non-None are filled
    # using forward fill or remain None (depending on typical interpolation guidelines.
    # Here, we leave elements outside the first/last non-None as None or forward fill?
    # Usually, extrapolation is not interpolation, so we leave them as None or forward fill.
    # Let's leave them as None since they cannot be interpolated.

    # First, let's check if all elements are None
    if all(v is None for v in values):
        return result

    # Find the first and last non-None indices
    first_non_none = -1
    for i in range(n):
        if values[i] is not None:
            first_non_none = i
            break

    last_non_none = -1
    for i in range(n - 1, -1, -1):
        if values[i] is not None:
            last_non_none = i
            break

    # Now interpolate between first_non_none and last_non_none
    left = first_non_none
    while left < last_non_none:
        # Find next non-None
        right = left + 1
        while right <= last_non_none and values[right] is None:
            right += 1

        # Check if they are numeric
        try:
            val_left = float(values[left])
            val_right = float(values[right])
            is_numeric = True
        except (TypeError, ValueError):
            is_numeric = False

        if is_numeric and right - left > 1:
            t_left = timestamps[left]
            t_right = timestamps[right]
            t_diff = t_right - t_left

            for i in range(left + 1, right):
                t_curr = timestamps[i]
                if t_diff == 0:
                    # Avoid division by zero if timestamps are identical
                    result[i] = val_left
                else:
                    fraction = (t_curr - t_left) / t_diff
                    result[i] = val_left + fraction * (val_right - val_left)
        elif not is_numeric and right - left > 1:
            # Fallback to forward-fill for non-numeric values
            for i in range(left + 1, right):
                result[i] = values[left]

        left = right

    return result
