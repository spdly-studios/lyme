"""Canonicalizer orchestrator for UOC.

Wires together parsers, normalizers, the variable registry, the observation store,
and exporters into a single unified data ingestion and transformation pipeline.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from .config import ExportConfig, UOCConfig
from .exporters.observation import ObservationExporter
from .exporters.sparse import SparseExporter
from .exporters.state_matrix import StateMatrixExporter
from .models import DataType, Observation, Quality, RawObservation
from .normalizers.timestamp import TimestampNormalizer
from .normalizers.types import TypeInferrer
from .normalizers.units import UnitNormalizer
from .parsers.csv_parser import CSVParser
from .parsers.json_parser import JSONParser
from .parsers.kv_parser import KVParser
from .parsers.text_parser import TextParser
from .registry import VariableRegistry
from .store import ObservationStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    """Statistics about the completed ingestion process."""

    total_records: int
    variable_count: int
    duration_seconds: float = 0.0


class Canonicalizer:
    """The core orchestrator of the Universal Observation Canonicalizer."""

    def __init__(self, config: UOCConfig | None = None) -> None:
        """Initialize the Canonicalizer.

        Parameters:
            config: Configuration settings. If None, uses default configuration.
        """
        self.config = config if config is not None else UOCConfig()
        self.registry = VariableRegistry()
        self.store = ObservationStore(batch_size=self.config.batch_size)

        # Register standard parsers
        self._parsers = [
            CSVParser(),
            JSONParser(),
            KVParser(),
            TextParser(),
        ]

    def ingest(
        self,
        source: Path | IO[str],
        format_name: str | None = None,
    ) -> IngestionResult:
        """Ingest observational data from a file or text stream.

        Parameters:
            source: Path to the file, or an open text stream.
            format_name: Optional format override ("csv", "json", "kv", "text").

        Returns:
            An IngestionResult object containing ingestion metrics.
        """
        import time

        start_time = time.perf_counter()

        # Resolve parser
        parser = None
        if format_name:
            fmt_lower = format_name.lower()
            if fmt_lower in ("csv", "tsv"):
                parser = CSVParser()
            elif fmt_lower in ("json", "jsonl"):
                parser = JSONParser()
            elif fmt_lower == "kv":
                parser = KVParser()
            elif fmt_lower in ("text", "log", "txt"):
                parser = TextParser()
            else:
                raise ValueError(f"Unknown format specified: {format_name}")
        else:
            # Auto-detect parser based on file path extension
            if isinstance(source, Path):
                for p in self._parsers:
                    if p.can_parse(source):
                        parser = p
                        break
            
            # Sniff if still unresolved
            if not parser:
                parser = self._sniff_parser(source)

        if not parser:
            # Fallback to TextParser which can handle any unstructured text
            parser = TextParser()

        logger.info(f"Ingesting source using parser: {parser.__class__.__name__}")

        records_count = 0
        raw_iterator = parser.parse(source, self.config.parser_config)

        for raw in raw_iterator:
            self._process_raw_observation(raw)
            records_count += 1

        self.store.flush()
        end_time = time.perf_counter()

        return IngestionResult(
            total_records=records_count,
            variable_count=len(self.registry),
            duration_seconds=end_time - start_time,
        )

    def export(
        self,
        mode: str,
        output: Path | IO[str],
        config: ExportConfig | None = None,
    ) -> None:
        """Export observations from the store.

        Parameters:
            mode: Export mode ("observation", "state_matrix", "sparse").
            output: Path or open text stream to write the output to.
            config: Optional export configuration.
        """
        mode_lower = mode.lower()
        if mode_lower == "observation":
            exporter = ObservationExporter()
        elif mode_lower == "state_matrix":
            exporter = StateMatrixExporter()
        elif mode_lower == "sparse":
            exporter = SparseExporter()
        else:
            raise ValueError(f"Unknown export mode: {mode}")

        exporter.export(self.store, self.registry, output, config)

    def _process_raw_observation(self, raw: RawObservation) -> None:
        """Canonicalize and store a RawObservation."""
        # 1. Normalize timestamp
        ts_hint = self.config.timestamp_format
        try:
            timestamp, orig_ts = TimestampNormalizer.normalize(
                raw.timestamp_raw, format_hint=ts_hint
            )
        except ValueError as e:
            logger.warning(f"Skipping observation due to timestamp error: {e}")
            return

        # 2. Parse units from value
        val_str = raw.value_raw.strip()
        parsed_val_str, parsed_unit = UnitNormalizer.parse_value_unit(val_str)

        # 3. Handle Variable Registration and Type inference
        var_name = raw.variable_name
        source = raw.source

        # Check type overrides first
        override_type = self.config.type_overrides.get(var_name)
        override_unit = self.config.unit_overrides.get(var_name)

        # Determine unit
        canonical_unit = None
        if override_unit:
            canonical_unit = UnitNormalizer.get_canonical_unit(override_unit)
        elif parsed_unit:
            canonical_unit = UnitNormalizer.get_canonical_unit(parsed_unit)

        # Look up variable in registry
        variable = self.registry.get_by_name(var_name)
        if not variable:
            # First time seeing this variable. Determine initial type
            if override_type:
                dtype = override_type
            else:
                # Infer type
                if parsed_unit:
                    # If it has a unit, it is almost certainly a float or int
                    dtype = DataType.FLOAT
                else:
                    dtype = TypeInferrer.infer_type(parsed_val_str)
            
            variable = self.registry.register(
                name=var_name,
                dtype=dtype,
                unit=canonical_unit,
                source=source,
            )
        else:
            # Variable already exists. Manage type and unit upgrades/conversions
            if not override_type:
                new_type = TypeInferrer.infer_type(parsed_val_str)
                # Check for dynamic type upgrading
                if variable.dtype == DataType.INTEGER and new_type == DataType.FLOAT:
                    variable.dtype = DataType.FLOAT
                elif (
                    variable.dtype in (DataType.INTEGER, DataType.FLOAT)
                    and new_type == DataType.STRING
                ):
                    variable.dtype = DataType.STRING

            if canonical_unit and not variable.unit:
                variable.unit = canonical_unit

        # 4. Normalize unit if variable has a registered unit and raw has a different unit
        final_val_str = parsed_val_str
        if canonical_unit and variable.unit and canonical_unit != variable.unit:
            # Perform unit conversion
            try:
                numeric_val = float(parsed_val_str)
                conv_val, _ = UnitNormalizer.normalize_unit(
                    numeric_val, canonical_unit, variable.unit
                )
                final_val_str = str(conv_val)
            except (ValueError, TypeError):
                # If numeric conversion fails, fallback to raw string
                pass
        elif not canonical_unit and variable.unit:
            # The observation doesn't specify a unit, but the registry does.
            # We assume it is already in canonical units.
            pass

        # 5. Coerce data value to variable's DataType
        coerced_value = TypeInferrer.coerce(final_val_str, variable.dtype)

        # 6. Construct and store canonical Observation
        observation = Observation(
            timestamp=timestamp,
            variable_id=variable.id,
            value=coerced_value,
            quality=self.config.default_quality,
            original_timestamp=orig_ts,
            source=source,
        )
        self.store.append(observation)

    def _sniff_parser(self, source: Path | IO[str]) -> BaseParser | None:
        """Read a small portion of the stream to sniff the input format."""
        if isinstance(source, Path):
            try:
                with open(source, "r", encoding=self.config.parser_config.encoding) as f:
                    chunk = f.read(1024)
            except Exception:
                return None
        else:
            # For stream, read if seekable, or just read a tiny bit
            # (Warning: reading from a non-seekable stream will consume characters.
            # For simple CLI inputs, we check seekable).
            try:
                if source.seekable():
                    pos = source.tell()
                    chunk = source.read(1024)
                    source.seek(pos)
                else:
                    return None
            except Exception:
                return None

        chunk_strip = chunk.strip()
        if not chunk_strip:
            return None

        # 1. JSON Sniff
        if chunk_strip.startswith(("{", "[")):
            return JSONParser()

        # 2. KV Sniff (contains key=value format like time=123,temp=30)
        # Check if there are key-value assignments
        if "=" in chunk_strip and ("," in chunk_strip or ";" in chunk_strip):
            # Check if it looks more like a key value pair than CSV header
            lines = chunk_strip.splitlines()
            if lines and "=" in lines[0]:
                return KVParser()

        # 3. CSV Sniff
        # If it has commas/tabs and a header-like line
        if "," in chunk_strip or "\t" in chunk_strip:
            # Basic validation: check if first line has commas and subsequent lines have the same count
            lines = chunk_strip.splitlines()
            if len(lines) > 1:
                delim = "," if "," in lines[0] else "\t"
                cnt = lines[0].count(delim)
                if cnt > 0 and lines[1].count(delim) == cnt:
                    return CSVParser()

        return None
