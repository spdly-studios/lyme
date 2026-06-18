"""CSV and TSV parser for UOC."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from ..config import ParserConfig
from ..models import RawObservation
from .base import BaseParser

_COMMON_TS_NAMES = {"timestamp", "time", "datetime", "date", "t", "ts"}


class CSVParser(BaseParser):
    """Parses CSV/TSV files and streams RawObservations."""

    @contextmanager
    def _open_source(self, source: Path | IO[str], encoding: str) -> Iterator[IO[str]]:
        if isinstance(source, Path):
            with open(source, "r", encoding=encoding, newline="") as f:
                yield f
        else:
            yield source

    def can_parse(self, source: Path) -> bool:
        return source.suffix.lower() in (".csv", ".tsv")

    def parse(
        self,
        source: Path | IO[str],
        config: ParserConfig | None = None,
    ) -> Iterator[RawObservation]:
        cfg = config if config is not None else ParserConfig()
        source_name = str(source) if isinstance(source, Path) else None

        # Determine delimiter
        delim = cfg.delimiter
        if isinstance(source, Path) and source.suffix.lower() == ".tsv" and delim == ",":
            delim = "\t"

        with self._open_source(source, cfg.encoding) as f:
            reader = csv.reader(f, delimiter=delim)
            try:
                headers = next(reader)
            except StopIteration:
                return

            # Clean headers
            headers = [h.strip() for h in headers]

            # Find timestamp column
            ts_idx = -1
            if cfg.timestamp_column:
                if cfg.timestamp_column in headers:
                    ts_idx = headers.index(cfg.timestamp_column)
            else:
                for idx, h in enumerate(headers):
                    if h.lower() in _COMMON_TS_NAMES:
                        ts_idx = idx
                        break
                if ts_idx == -1 and headers:
                    # Fallback to the first column
                    ts_idx = 0

            # If no columns, we can't parse
            if not headers:
                return

            for row_idx, row in enumerate(reader):
                if not row:
                    continue

                # Pad row if it is shorter than headers
                if len(row) < len(headers):
                    row = row + [""] * (len(headers) - len(row))

                # Extract timestamp
                raw_ts = row[ts_idx] if ts_idx < len(row) else None

                # Yield observations for all other columns
                for col_idx, value in enumerate(row):
                    if col_idx == ts_idx:
                        continue
                    if col_idx >= len(headers):
                        break

                    var_name = headers[col_idx]
                    val_strip = value.strip()

                    # Skip empty cells for compact storage
                    if val_strip == "":
                        continue

                    yield RawObservation(
                        timestamp_raw=raw_ts,
                        variable_name=var_name,
                        value_raw=val_strip,
                        source=source_name,
                    )
