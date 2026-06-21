"""Arrow-backed observation store for UOC.

Provides columnar storage for canonical observations with chunked processing
and Parquet serialization support.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .models import Observation, Quality

# Canonical Schema for Observations
SCHEMA = pa.schema([
    ("timestamp", pa.float64()),
    ("variable_id", pa.int32()),
    ("value_float", pa.float64()),
    ("value_int", pa.int64()),
    ("value_str", pa.string()),
    ("value_bool", pa.bool_()),
    ("quality", pa.int8()),
    ("original_timestamp", pa.string()),
    ("source", pa.string()),
])


class ObservationStore:
    """columnar observation store backed by Apache Arrow."""

    def __init__(self, batch_size: int = 10_000) -> None:
        """Initialize the store.

        Parameters:
            batch_size: Number of observations to accumulate in memory before
                flushing to Arrow record batches.
        """
        self._batch_size = batch_size
        self._buffer: list[dict[str, Any]] = []
        self._batches: list[pa.RecordBatch] = []
        self._total_count = 0

    def append(self, observation: Observation) -> None:
        """Append a single canonical observation.

        Flushes to Arrow record batch if batch_size is reached.

        Parameters:
            observation: The Observation instance.
        """
        self._buffer.append(self._obs_to_dict(observation))
        self._total_count += 1
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def append_batch(self, observations: list[Observation]) -> None:
        """Append a batch of canonical observations.

        Parameters:
            observations: List of Observation instances.
        """
        for obs in observations:
            self.append(obs)

    def flush(self) -> None:
        """Flush any buffered observations into an Arrow RecordBatch."""
        if not self._buffer:
            return

        # Prepare column lists
        cols: dict[str, list[Any]] = {name: [] for name in SCHEMA.names}
        for item in self._buffer:
            for name in SCHEMA.names:
                cols[name].append(item[name])

        # Convert to arrow arrays
        arrays = []
        for name in SCHEMA.names:
            arrays.append(pa.array(cols[name], type=SCHEMA.field(name).type))

        batch = pa.RecordBatch.from_arrays(arrays, schema=SCHEMA)
        self._batches.append(batch)
        self._buffer.clear()

    def to_table(self) -> pa.Table:
        """Concatenate all record batches and return a single Arrow Table."""
        self.flush()
        if not self._batches:
            # Return empty table with schema
            return pa.Table.from_batches([], schema=SCHEMA)
        return pa.Table.from_batches(self._batches, schema=SCHEMA)

    def __len__(self) -> int:
        return self._total_count

    def iter_batches(self) -> Iterator[pa.RecordBatch]:
        """Iterate over all stored Arrow RecordBatches.

        Yields:
            pyarrow.RecordBatch
        """
        self.flush()
        yield from self._batches

    def save_parquet(self, path: Path) -> None:
        """Save all observations to a Parquet file.

        Parameters:
            path: Target file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        table = self.to_table()
        pq.write_table(table, path)

    @classmethod
    def load_parquet(cls, path: Path, batch_size: int = 10_000) -> ObservationStore:
        """Load observations from a Parquet file.

        Parameters:
            path: Source Parquet file path.
            batch_size: Batch size of the new store.

        Returns:
            A new ObservationStore populated with Parquet data.
        """
        store = cls(batch_size=batch_size)
        table = pq.read_table(path)
        # Convert table batches to RecordBatches
        store._batches = table.to_batches()
        store._total_count = table.num_rows
        return store

    def clear(self) -> None:
        """Clear all stored data and buffers."""
        self._buffer.clear()
        self._batches.clear()
        self._total_count = 0

    def _obs_to_dict(self, obs: Observation) -> dict[str, Any]:
        """Route value to type-specific columns and return dictionary."""
        val = obs.value
        val_float: float | None = None
        val_int: int | None = None
        val_str: str | None = None
        val_bool: bool | None = None

        if val is not None:
            if isinstance(val, bool):
                val_bool = val
            elif isinstance(val, int):
                val_int = val
            elif isinstance(val, float):
                val_float = val
            else:
                val_str = str(val)

        return {
            "timestamp": obs.timestamp,
            "variable_id": obs.variable_id,
            "value_float": val_float,
            "value_int": val_int,
            "value_str": val_str,
            "value_bool": val_bool,
            "quality": int(obs.quality),
            "original_timestamp": obs.original_timestamp,
            "source": obs.source,
        }

    def get_value_at(self, idx: int) -> Any:
        """Utility to retrieve a python value from the table representation."""
        # Note: mainly for testing/debugging
        table = self.to_table()
        row = table.slice(idx, 1).to_pydict()
        
        # Read the value based on active columns
        if row["value_bool"][0] is not None:
            return row["value_bool"][0]
        if row["value_int"][0] is not None:
            return row["value_int"][0]
        if row["value_float"][0] is not None:
            return row["value_float"][0]
        return row["value_str"][0]
