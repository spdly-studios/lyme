"""State matrix exporter for UOC."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import IO, Any

import pyarrow as pa
import pyarrow.parquet as pq

from ..alignment import align, get_unique_timestamps
from ..config import ExportConfig
from ..missing import fill_missing_column
from ..registry import VariableRegistry
from ..store import ObservationStore
from .base import BaseExporter


class StateMatrixExporter(BaseExporter):
    """Exports time-aligned wide state matrix representation."""

    def export(
        self,
        store: ObservationStore,
        registry: VariableRegistry,
        output: Path | IO[str],
        config: ExportConfig | None = None,
    ) -> None:
        cfg = config if config is not None else ExportConfig()

        # Get all sorted unique timestamps or apply time range filter
        timestamps = get_unique_timestamps(store)
        if cfg.time_range:
            t_start, t_end = cfg.time_range
            timestamps = [t for t in timestamps if t_start <= t <= t_end]

        # Get target variable IDs
        if cfg.variables:
            var_ids = sorted(list(cfg.variables))
        else:
            var_ids = sorted([v.id for v in registry])

        if not timestamps or not var_ids:
            # Empty matrix
            self._export_empty(output, registry, var_ids, cfg)
            return

        # Perform alignment
        # This returns dict[timestamp, dict[variable_id, value]]
        aligned = align(
            store=store,
            registry=registry,
            strategy=cfg.alignment_strategy,
            timestamps=timestamps,
            variables=var_ids,
        )

        # Build column data for each variable
        columns: dict[int, list[Any]] = {vid: [] for vid in var_ids}
        for t in timestamps:
            for vid in var_ids:
                columns[vid].append(aligned[t][vid])

        # Apply missing data strategy per variable column
        for vid in var_ids:
            columns[vid] = fill_missing_column(
                timestamps=timestamps,
                values=columns[vid],
                strategy=cfg.missing_strategy,
                default_value=cfg.default_missing_value,
            )

        # Map variable IDs to names for header
        headers = ["timestamp"]
        var_names: dict[int, str] = {}
        for vid in var_ids:
            var = registry.get_by_id(vid)
            name = var.name if var else f"var_{vid}"
            # Ensure uniqueness of headers
            if name in headers:
                name = f"{name}_{vid}"
            headers.append(name)
            var_names[vid] = name

        # Export formatting
        is_parquet = False
        if isinstance(output, Path) and (
            output.suffix.lower() == ".parquet" or cfg.format.lower() == "parquet"
        ):
            is_parquet = True

        if is_parquet:
            if not isinstance(output, Path):
                raise ValueError("Parquet export requires a file Path, not an IO stream.")
            
            # Construct Arrow Table
            arrays = [pa.array(timestamps, type=pa.float64())]
            for vid in var_ids:
                # Infer array type from first non-None value or default to string
                col_vals = columns[vid]
                arrays.append(pa.array(col_vals))

            table = pa.Table.from_arrays(arrays, names=headers)
            pq.write_table(table, output)
        else:
            with self._open_output(output) as f:
                writer = csv.writer(f)
                writer.writerow(headers)

                for idx, t in enumerate(timestamps):
                    row = [t]
                    for vid in var_ids:
                        row.append(columns[vid][idx])
                    writer.writerow(row)

    def _export_empty(
        self,
        output: Path | IO[str],
        registry: VariableRegistry,
        var_ids: list[int],
        cfg: ExportConfig,
    ) -> None:
        headers = ["timestamp"]
        for vid in var_ids:
            var = registry.get_by_id(vid)
            headers.append(var.name if var else f"var_{vid}")

        is_parquet = False
        if isinstance(output, Path) and (
            output.suffix.lower() == ".parquet" or cfg.format.lower() == "parquet"
        ):
            is_parquet = True

        if is_parquet:
            if not isinstance(output, Path):
                raise ValueError("Parquet export requires a file Path, not an IO stream.")
            schema = pa.schema([("timestamp", pa.float64())] + [
                (h, pa.string()) for h in headers[1:]
            ])
            table = pa.Table.from_batches([], schema=schema)
            pq.write_table(table, output)
        else:
            with self._open_output(output) as f:
                writer = csv.writer(f)
                writer.writerow(headers)
