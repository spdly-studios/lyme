"""Raw canonical observation exporter for UOC."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import IO

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ..config import ExportConfig
from ..models import Quality
from ..registry import VariableRegistry
from ..store import ObservationStore
from .base import BaseExporter


class ObservationExporter(BaseExporter):
    """Exports raw canonical observations to CSV or Parquet format."""

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
            
            # Construct a unified table for Parquet export
            p_table = self._build_export_table(table, registry)
            pq.write_table(p_table, output)
        else:
            with self._open_output(output) as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "variable_id",
                    "variable_name",
                    "value",
                    "quality",
                    "original_timestamp",
                    "source",
                ])

                if table.num_rows > 0:
                    timestamps = table["timestamp"].to_pylist()
                    vids = table["variable_id"].to_pylist()
                    v_floats = table["value_float"].to_pylist()
                    v_ints = table["value_int"].to_pylist()
                    v_strs = table["value_str"].to_pylist()
                    v_bools = table["value_bool"].to_pylist()
                    qualities = table["quality"].to_pylist()
                    orig_ts = table["original_timestamp"].to_pylist()
                    sources = table["source"].to_pylist()

                    for i in range(len(timestamps)):
                        vid = vids[i]
                        var = registry.get_by_id(vid)
                        var_name = var.name if var else f"var_{vid}"

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

                        q_name = Quality(qualities[i]).name

                        writer.writerow([
                            timestamps[i],
                            vid,
                            var_name,
                            val,
                            q_name,
                            orig_ts[i] if orig_ts[i] is not None else "",
                            sources[i] if sources[i] is not None else "",
                        ])

    def _build_export_table(self, table: pa.Table, registry: VariableRegistry) -> pa.Table:
        """Build a clean unified table for Parquet export."""
        if table.num_rows == 0:
            # Return empty schema
            schema = pa.schema([
                ("timestamp", pa.float64()),
                ("variable_id", pa.int32()),
                ("variable_name", pa.string()),
                ("value", pa.string()),
                ("quality", pa.string()),
                ("original_timestamp", pa.string()),
                ("source", pa.string()),
            ])
            return pa.Table.from_batches([], schema=schema)

        vids = table["variable_id"].to_pylist()
        v_floats = table["value_float"].to_pylist()
        v_ints = table["value_int"].to_pylist()
        v_strs = table["value_str"].to_pylist()
        v_bools = table["value_bool"].to_pylist()
        qualities = table["quality"].to_pylist()

        names = []
        vals = []
        q_names = []

        for i in range(len(vids)):
            vid = vids[i]
            var = registry.get_by_id(vid)
            names.append(var.name if var else f"var_{vid}")

            val = None
            if v_bools[i] is not None:
                val = str(v_bools[i])
            elif v_ints[i] is not None:
                val = str(v_ints[i])
            elif v_floats[i] is not None:
                val = str(v_floats[i])
            else:
                val = v_strs[i]
            vals.append(val)

            q_names.append(Quality(qualities[i]).name)

        # Construct new table columns
        export_table = pa.Table.from_arrays([
            table["timestamp"],
            table["variable_id"],
            pa.array(names, type=pa.string()),
            pa.array(vals, type=pa.string()),
            pa.array(q_names, type=pa.string()),
            table["original_timestamp"],
            table["source"],
        ], names=[
            "timestamp",
            "variable_id",
            "variable_name",
            "value",
            "quality",
            "original_timestamp",
            "source",
        ])
        return export_table
