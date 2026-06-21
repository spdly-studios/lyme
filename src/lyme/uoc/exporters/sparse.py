"""Sparse representation exporter for UOC."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import IO

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ..config import ExportConfig
from ..registry import VariableRegistry
from ..store import ObservationStore
from .base import BaseExporter


class SparseExporter(BaseExporter):
    """Exports raw canonical observations in a sparse COO (timestamp, variable_id, value) format."""

    def export(
        self,
        store: ObservationStore,
        registry: VariableRegistry,
        output: Path | IO[str],
        config: ExportConfig | None = None,
    ) -> None:
        cfg = config if config is not None else ExportConfig()

        # Get and filter Table
        table = store.to_table()
        if table.num_rows > 0:
            mask = None
            if cfg.variables:
                mask = pc.field("variable_id").isin(cfg.variables)
            if cfg.time_range:
                t_start, t_end = cfg.time_range
                t_mask = (pc.field("timestamp") >= t_start) & (pc.field("timestamp") <= t_end)
                mask = t_mask if mask is None else (mask & t_mask)
            
            if mask is not None:
                table = table.filter(mask)

        # Check export format
        is_parquet = False
        if isinstance(output, Path) and (
            output.suffix.lower() == ".parquet" or cfg.format.lower() == "parquet"
        ):
            is_parquet = True

        if is_parquet:
            if not isinstance(output, Path):
                raise ValueError("Parquet export requires a file Path, not an IO stream.")
            
            p_table = self._build_sparse_table(table)
            pq.write_table(p_table, output)
        else:
            with self._open_output(output) as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "variable_id", "value"])

                if table.num_rows > 0:
                    timestamps = table["timestamp"].to_pylist()
                    vids = table["variable_id"].to_pylist()
                    v_floats = table["value_float"].to_pylist()
                    v_ints = table["value_int"].to_pylist()
                    v_strs = table["value_str"].to_pylist()
                    v_bools = table["value_bool"].to_pylist()

                    for i in range(len(timestamps)):
                        # Extract active value
                        val = None
                        if v_bools[i] is not None:
                            val = v_bools[i]
                        elif v_ints[i] is not None:
                            val = v_ints[i]
                        elif v_floats[i] is not None:
                            val = v_floats[i]
                        else:
                            val = v_strs[i]

                        # Skip actual null values
                        if val is None:
                            continue

                        writer.writerow([timestamps[i], vids[i], val])

    def _build_sparse_table(self, table: pa.Table) -> pa.Table:
        """Build a clean unified table for sparse Parquet export."""
        if table.num_rows == 0:
            schema = pa.schema([
                ("timestamp", pa.float64()),
                ("variable_id", pa.int32()),
                ("value", pa.string()),
            ])
            return pa.Table.from_batches([], schema=schema)

        timestamps = table["timestamp"].to_pylist()
        vids = table["variable_id"].to_pylist()
        v_floats = table["value_float"].to_pylist()
        v_ints = table["value_int"].to_pylist()
        v_strs = table["value_str"].to_pylist()
        v_bools = table["value_bool"].to_pylist()

        clean_ts = []
        clean_vids = []
        vals = []

        for i in range(len(timestamps)):
            val = None
            if v_bools[i] is not None:
                val = str(v_bools[i])
            elif v_ints[i] is not None:
                val = str(v_ints[i])
            elif v_floats[i] is not None:
                val = str(v_floats[i])
            else:
                val = v_strs[i]

            if val is None:
                continue

            clean_ts.append(timestamps[i])
            clean_vids.append(vids[i])
            vals.append(val)

        export_table = pa.Table.from_arrays([
            pa.array(clean_ts, type=pa.float64()),
            pa.array(clean_vids, type=pa.int32()),
            pa.array(vals, type=pa.string()),
        ], names=[
            "timestamp",
            "variable_id",
            "value",
        ])
        return export_table
