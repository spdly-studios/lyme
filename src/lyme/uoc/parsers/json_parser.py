"""JSON and JSONL parser for UOC."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from ..config import ParserConfig
from ..models import RawObservation
from .base import BaseParser

_COMMON_TS_NAMES = {"timestamp", "time", "datetime", "date", "t", "ts"}


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    for k, v in d.items():
        new_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key))
        else:
            items[new_key] = v
    return items


class JSONParser(BaseParser):
    """Parses JSON / JSONL files and streams RawObservations."""

    @contextmanager
    def _open_source(self, source: Path | IO[str], encoding: str) -> Iterator[IO[str]]:
        if isinstance(source, Path):
            with open(source, "r", encoding=encoding) as f:
                yield f
        else:
            yield source

    def can_parse(self, source: Path) -> bool:
        return source.suffix.lower() in (".json", ".jsonl")

    def parse(
        self,
        source: Path | IO[str],
        config: ParserConfig | None = None,
    ) -> Iterator[RawObservation]:
        cfg = config if config is not None else ParserConfig()
        source_name = str(source) if isinstance(source, Path) else None

        # Check if source is a file path with .jsonl extension or if we stream it
        is_jsonl = False
        if isinstance(source, Path) and source.suffix.lower() == ".jsonl":
            is_jsonl = True

        if is_jsonl:
            with self._open_source(source, cfg.encoding) as f:
                for line in f:
                    line_strip = line.strip()
                    if not line_strip:
                        continue
                    try:
                        obj = json.loads(line_strip)
                        yield from self._parse_object(obj, cfg, source_name)
                    except json.JSONDecodeError:
                        continue
            return

        # For standard JSON, try reading the entire stream first.
        # If it fails, fallback to line-by-line JSONL (some files have .json extension but are JSONL).
        content = None
        with self._open_source(source, cfg.encoding) as f:
            try:
                content = f.read()
            except Exception:
                pass

        if content is not None:
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield from self._parse_object(item, cfg, source_name)
                elif isinstance(data, dict):
                    yield from self._parse_object(data, cfg, source_name)
                return
            except json.JSONDecodeError:
                # Fallback to JSONL line-by-line parsing of content
                lines = content.splitlines()
                for line in lines:
                    line_strip = line.strip()
                    if not line_strip:
                        continue
                    try:
                        obj = json.loads(line_strip)
                        yield from self._parse_object(obj, cfg, source_name)
                    except json.JSONDecodeError:
                        continue

    def _parse_object(
        self,
        obj: dict[str, Any],
        cfg: ParserConfig,
        source_name: str | None,
    ) -> Iterator[RawObservation]:
        flat = _flatten_dict(obj)

        # Find timestamp field
        ts_field = None
        if cfg.timestamp_column:
            if cfg.timestamp_column in flat:
                ts_field = cfg.timestamp_column
        else:
            for k in flat:
                # Check top-level keys or flat keys
                # E.g. 'timestamp' or 'sensor.timestamp'
                # If key has dots, get the last part
                part = k.split(".")[-1]
                if part.lower() in _COMMON_TS_NAMES:
                    ts_field = k
                    break

        raw_ts = flat.get(ts_field) if ts_field else None

        for k, v in flat.items():
            if k == ts_field:
                continue

            val_str = str(v).strip() if v is not None else ""
            if val_str == "":
                continue

            yield RawObservation(
                timestamp_raw=raw_ts,
                variable_name=k,
                value_raw=val_str,
                source=source_name,
            )
