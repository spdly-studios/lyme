"""Key-Value parser for UOC."""

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


class KVParser(BaseParser):
    """Parses Key-Value formatted files and streams RawObservations."""

    @contextmanager
    def _open_source(self, source: Path | IO[str], encoding: str) -> Iterator[IO[str]]:
        if isinstance(source, Path):
            with open(source, "r", encoding=encoding) as f:
                yield f
        else:
            yield source

    def can_parse(self, source: Path) -> bool:
        return source.suffix.lower() in (".kv", ".kvlog")

    def parse(
        self,
        source: Path | IO[str],
        config: ParserConfig | None = None,
    ) -> Iterator[RawObservation]:
        cfg = config if config is not None else ParserConfig()
        source_name = str(source) if isinstance(source, Path) else None

        sep = cfg.kv_separator
        delim = cfg.kv_delimiter

        with self._open_source(source, cfg.encoding) as f:
            for line_idx, line in enumerate(f):
                line_strip = line.strip()
                if not line_strip:
                    continue

                # Use csv reader to split by delimiter while respecting quotes
                reader = csv.reader([line_strip], delimiter=delim)
                try:
                    parts = next(reader)
                except StopIteration:
                    continue

                # Extract key-value pairs
                pairs: dict[str, str] = {}
                for part in parts:
                    part_strip = part.strip()
                    if not part_strip:
                        continue
                    if sep in part_strip:
                        k, v = part_strip.split(sep, 1)
                        # Strip spaces and optional quotes from keys/values
                        k_clean = k.strip().strip("'\"")
                        v_clean = v.strip().strip("'\"")
                        pairs[k_clean] = v_clean

                if not pairs:
                    continue

                # Find timestamp key
                ts_key = None
                if cfg.timestamp_column:
                    if cfg.timestamp_column in pairs:
                        ts_key = cfg.timestamp_column
                else:
                    for k in pairs:
                        if k.lower() in _COMMON_TS_NAMES:
                            ts_key = k
                            break

                raw_ts = pairs.get(ts_key) if ts_key else None

                # Yield observations for all other keys
                for k, v in pairs.items():
                    if k == ts_key:
                        continue
                    if v == "":
                        continue

                    yield RawObservation(
                        timestamp_raw=raw_ts,
                        variable_name=k,
                        value_raw=v,
                        source=source_name,
                    )
