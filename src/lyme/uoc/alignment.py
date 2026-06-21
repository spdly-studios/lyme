"""Time alignment strategies for UOC.

Aligns observations from multi-rate sources to a common time grid using
EXACT, NEAREST, FORWARD_FILL, or INTERPOLATE strategies.
"""

from __future__ import annotations

import bisect
from typing import Any

from .config import AlignmentStrategy
from .registry import VariableRegistry
from .store import ObservationStore


def get_unique_timestamps(store: ObservationStore) -> list[float]:
    """Extract a sorted list of unique timestamps from the store.

    Parameters:
        store: The ObservationStore to query.

    Returns:
        A sorted list of unique float timestamps.
    """
    table = store.to_table()
    if table.num_rows == 0:
        return []

    # Get the unique timestamps
    ts_array = table["timestamp"]
    # In Arrow, we can compute unique values or convert to set
    ts_set = set(ts_array.to_pylist())
    return sorted(list(ts_set))


def align(
    store: ObservationStore,
    registry: VariableRegistry,
    strategy: AlignmentStrategy,
    timestamps: list[float] | None = None,
    variables: list[int] | None = None,
) -> dict[float, dict[int, Any]]:
    """Align multi-rate observations to a target set of timestamps.

    Parameters:
        store: The ObservationStore containing the raw data.
        registry: The VariableRegistry.
        strategy: The AlignmentStrategy to apply.
        timestamps: The target list of timestamps. If None, uses all unique
            timestamps present in the store.
        variables: The list of variable IDs to include. If None, uses all
            registered variable IDs.

    Returns:
        A dictionary mapping timestamp -> {variable_id: aligned_value}.
    """
    if timestamps is None:
        timestamps = get_unique_timestamps(store)
    else:
        timestamps = sorted(list(timestamps))

    if variables is None:
        variables = [v.id for v in registry]

    if not timestamps or not variables:
        return {}

    # Read data from Arrow store
    table = store.to_table()
    var_obs: dict[int, list[tuple[float, Any]]] = {vid: [] for vid in variables}

    if table.num_rows > 0:
        ts_list = table["timestamp"].to_pylist()
        vid_list = table["variable_id"].to_pylist()
        v_floats = table["value_float"].to_pylist()
        v_ints = table["value_int"].to_pylist()
        v_strs = table["value_str"].to_pylist()
        v_bools = table["value_bool"].to_pylist()

        for i in range(len(ts_list)):
            vid = vid_list[i]
            if vid in var_obs:
                # Resolve active value
                val = None
                if v_bools[i] is not None:
                    val = v_bools[i]
                elif v_ints[i] is not None:
                    val = v_ints[i]
                elif v_floats[i] is not None:
                    val = v_floats[i]
                else:
                    val = v_strs[i]
                
                var_obs[vid].append((ts_list[i], val))

    # Sort observations per variable by timestamp
    for vid in var_obs:
        var_obs[vid].sort(key=lambda x: x[0])

    # Align each target timestamp
    aligned_grid: dict[float, dict[int, Any]] = {}

    for t_target in timestamps:
        aligned_grid[t_target] = {}

        for vid in variables:
            obs_list = var_obs[vid]
            if not obs_list:
                aligned_grid[t_target][vid] = None
                continue

            val = None
            if strategy == AlignmentStrategy.EXACT:
                # Find exact match
                keys = [x[0] for x in obs_list]
                idx = bisect.bisect_left(keys, t_target)
                if idx < len(keys) and keys[idx] == t_target:
                    val = obs_list[idx][1]

            elif strategy == AlignmentStrategy.NEAREST:
                keys = [x[0] for x in obs_list]
                idx = bisect.bisect_left(keys, t_target)
                if idx == 0:
                    val = obs_list[0][1]
                elif idx == len(keys):
                    val = obs_list[-1][1]
                else:
                    t_left = keys[idx - 1]
                    t_right = keys[idx]
                    if (t_target - t_left) <= (t_right - t_target):
                        val = obs_list[idx - 1][1]
                    else:
                        val = obs_list[idx][1]

            elif strategy == AlignmentStrategy.FORWARD_FILL:
                keys = [x[0] for x in obs_list]
                idx = bisect.bisect_right(keys, t_target)
                if idx > 0:
                    val = obs_list[idx - 1][1]

            elif strategy == AlignmentStrategy.INTERPOLATE:
                keys = [x[0] for x in obs_list]
                idx = bisect.bisect_left(keys, t_target)
                if idx == 0:
                    if keys[0] == t_target:
                        val = obs_list[0][1]
                elif idx == len(keys):
                    # Extrapolate forward-fill
                    val = obs_list[-1][1]
                else:
                    t_left, val_left = obs_list[idx - 1]
                    t_right, val_right = obs_list[idx]
                    if t_left == t_target:
                        val = val_left
                    elif t_right == t_target:
                        val = val_right
                    else:
                        # Try to interpolate float/int
                        try:
                            f_left = float(val_left)
                            f_right = float(val_right)
                            t_diff = t_right - t_left
                            if t_diff == 0:
                                val = val_left
                            else:
                                fraction = (t_target - t_left) / t_diff
                                val = f_left + fraction * (f_right - f_left)
                        except (ValueError, TypeError):
                            # Fallback to forward-fill
                            val = val_left

            aligned_grid[t_target][vid] = val

    return aligned_grid
