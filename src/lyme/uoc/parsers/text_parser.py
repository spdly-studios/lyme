"""Free-text log parser for UOC."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from ..config import ParserConfig
from ..models import RawObservation
from .base import BaseParser

# Regex to detect timestamp prefixes
# 1. ISO format: 2026-06-18 08:01:22 or 2026-06-18T08:01:22.123Z
_ISO_TS_RE = re.compile(
    r"^(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|[+-]\d{4}|Z)?)\s+(.*)$"
)
# 2. Syslog format: Jun 18 08:01:22
_SYSLOG_TS_RE = re.compile(
    r"^([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(.*)$"
)
# 3. Epoch/Simple relative prefix: e.g. "123.45 Temp = 30"
_NUMERIC_PREFIX_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s+(.*)$"
)

# Variable name clean-up: replace spaces/hyphens with underscores, remove other special chars
_VAR_CLEAN_RE = re.compile(r"[^a-zA-Z0-9_]")


def _normalize_var_name(name: str) -> str:
    cleaned = name.strip().replace(" ", "_").replace("-", "_")
    cleaned = _VAR_CLEAN_RE.sub("", cleaned)
    # Deduplicate underscores
    return re.sub(r"_+", "_", cleaned).strip("_")


class TextParser(BaseParser):
    """Parses free-text logs and extracts canonical observations using regex rules."""

    @contextmanager
    def _open_source(self, source: Path | IO[str], encoding: str) -> Iterator[IO[str]]:
        if isinstance(source, Path):
            with open(source, "r", encoding=encoding) as f:
                yield f
        else:
            yield source

    def can_parse(self, source: Path) -> bool:
        return source.suffix.lower() in (".txt", ".log")

    def parse(
        self,
        source: Path | IO[str],
        config: ParserConfig | None = None,
    ) -> Iterator[RawObservation]:
        cfg = config if config is not None else ParserConfig()
        source_name = str(source) if isinstance(source, Path) else None

        # Build patterns list
        patterns = []
        for p_str in cfg.text_patterns:
            try:
                patterns.append(re.compile(p_str))
            except re.error:
                pass

        # Add built-in patterns
        # 1. Key-Value patterns: Temperature = 28.5 C, Battery Voltage: 4.18V, Speed is 100
        patterns.append(
            re.compile(
                r"^([a-zA-Z_][a-zA-Z0-9_\s-]*?)\s*(?:=|:|\bis\b)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z°%_/]+)?$"
            )
        )
        # 2. Verb transition: Motor speed changed to 500 RPM, temp set to 30
        # Non-greedy match on variable name stops at the verb keyword.
        patterns.append(
            re.compile(
                r"^([a-zA-Z_][a-zA-Z0-9_\s-]*?)\s+(?:changed\s+to|set\s+to|updated\s+to)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z°%_/]+)?$"
            )
        )

        with self._open_source(source, cfg.encoding) as f:
            for line_idx, line in enumerate(f):
                line_strip = line.strip()
                if not line_strip:
                    continue

                # Try to extract timestamp prefix
                raw_ts = None
                content = line_strip

                # 1. ISO
                match = _ISO_TS_RE.match(content)
                if match:
                    raw_ts = match.group(1)
                    content = match.group(2)
                else:
                    # 2. Syslog
                    match = _SYSLOG_TS_RE.match(content)
                    if match:
                        raw_ts = match.group(1)
                        content = match.group(2)
                    else:
                        # 3. Numeric prefix
                        match = _NUMERIC_PREFIX_RE.match(content)
                        if match:
                            raw_ts = match.group(1)
                            content = match.group(2)

                content = content.strip()
                matched = False

                # Try to match patterns against content
                for pat in patterns:
                    m = pat.match(content)
                    if not m:
                        continue

                    # Determine groups by index or name
                    groupdict = m.groupdict()
                    if "variable" in groupdict and "value" in groupdict:
                        var_name = groupdict["variable"]
                        val_str = groupdict["value"]
                        unit_str = groupdict.get("unit")
                        ts_val = groupdict.get("timestamp")
                        if ts_val:
                            raw_ts = ts_val
                    elif len(m.groups()) >= 2:
                        var_name = m.group(1)
                        val_str = m.group(2)
                        unit_str = m.group(3) if len(m.groups()) >= 3 else None
                    else:
                        continue

                    if var_name and val_str:
                        var_clean = _normalize_var_name(var_name)
                        if var_clean:
                            yield RawObservation(
                                timestamp_raw=raw_ts,
                                variable_name=var_clean,
                                value_raw=val_str.strip(),
                                source=source_name,
                                unit_raw=unit_str.strip() if unit_str else None,
                            )
                            matched = True
                            break

                # Fallback: if no pattern matches, treat the entire line content as a log message
                if not matched:
                    # If there's content left
                    if content:
                        yield RawObservation(
                            timestamp_raw=raw_ts,
                            variable_name="log_line",
                            value_raw=content,
                            source=source_name,
                        )
                    elif raw_ts:
                        # If only timestamp is left
                        yield RawObservation(
                            timestamp_raw=raw_ts,
                            variable_name="event",
                            value_raw="ping",
                            source=source_name,
                        )
