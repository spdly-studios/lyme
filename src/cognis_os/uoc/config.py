"""
Configuration for the Universal Observation Canonicalizer.

Provides configuration dataclasses and TOML loading for all UOC settings.
"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import DataType, Quality


class MissingStrategy(enum.Enum):
    """Strategy for handling missing data during export."""

    LEAVE = "leave"
    FORWARD_FILL = "forward_fill"
    INTERPOLATE = "interpolate"
    DEFAULT = "default"


class AlignmentStrategy(enum.Enum):
    """Strategy for time-aligning multi-rate observations."""

    EXACT = "exact"
    NEAREST = "nearest"
    FORWARD_FILL = "forward_fill"
    INTERPOLATE = "interpolate"


@dataclass
class ParserConfig:
    """Configuration for input parsers.

    Attributes:
        timestamp_column: Name of the timestamp column/key. Auto-detected
            if ``None``.
        timestamp_format: ``strftime`` format string. Auto-detected if ``None``.
        delimiter: Column delimiter for CSV files.
        kv_separator: Key-value separator (e.g. ``=``).
        kv_delimiter: Delimiter between key-value pairs (e.g. ``,``).
        text_patterns: Additional regex patterns for text log parsing.
            Each pattern should define named groups ``variable`` and ``value``,
            and optionally ``unit`` and ``timestamp``.
        encoding: File encoding.
    """

    timestamp_column: str | None = None
    timestamp_format: str | None = None
    delimiter: str = ","
    kv_separator: str = "="
    kv_delimiter: str = ","
    text_patterns: list[str] = field(default_factory=list)
    encoding: str = "utf-8"


@dataclass
class ExportConfig:
    """Configuration for export operations.

    Attributes:
        missing_strategy: How to handle missing data.
        alignment_strategy: How to align multi-rate observations.
        default_missing_value: Default value for ``MissingStrategy.DEFAULT``.
        variables: Optional subset of variable IDs to export.  ``None`` = all.
        time_range: Optional ``(start, end)`` tuple to filter timestamps.
        format: Output format (``csv``, ``parquet``, ``json``).
    """

    missing_strategy: MissingStrategy = MissingStrategy.LEAVE
    alignment_strategy: AlignmentStrategy = AlignmentStrategy.FORWARD_FILL
    default_missing_value: Any = None
    variables: list[int] | None = None
    time_range: tuple[float, float] | None = None
    format: str = "csv"


@dataclass
class UOCConfig:
    """Top-level configuration for the Universal Observation Canonicalizer.

    Attributes:
        timestamp_column: Default timestamp column name.  Auto-detected if
            ``None``.
        timestamp_format: Default timestamp format.  Auto-detected if ``None``.
        default_quality: Quality level assigned when not otherwise specified.
        batch_size: Number of observations per processing batch.
        missing_strategy: Default missing data strategy.
        alignment_strategy: Default time alignment strategy.
        type_overrides: Manual type declarations mapping variable name to
            ``DataType``.
        unit_overrides: Target units for normalization mapping variable name
            to a unit string.
        parser_config: Parser-specific settings.
        default_missing_value: Default fill value when using
            ``MissingStrategy.DEFAULT``.
    """

    timestamp_column: str | None = None
    timestamp_format: str | None = None
    default_quality: Quality = Quality.MEASURED
    batch_size: int = 10_000
    missing_strategy: MissingStrategy = MissingStrategy.LEAVE
    alignment_strategy: AlignmentStrategy = AlignmentStrategy.FORWARD_FILL
    type_overrides: dict[str, DataType] = field(default_factory=dict)
    unit_overrides: dict[str, str] = field(default_factory=dict)
    parser_config: ParserConfig = field(default_factory=ParserConfig)
    default_missing_value: Any = None

    @classmethod
    def from_toml(cls, path: Path) -> UOCConfig:
        """Load configuration from a TOML file.

        Parameters:
            path: Path to the TOML configuration file.

        Returns:
            A populated ``UOCConfig`` instance.
        """
        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                raise ImportError(
                    "tomli is required for Python < 3.11. "
                    "Install it with: pip install tomli"
                )
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UOCConfig:
        """Create configuration from a dictionary.

        The dictionary structure mirrors the TOML layout::

            {
                "general": {"batch_size": 50000, ...},
                "parser": {"delimiter": ",", ...},
                "type_overrides": {"status": "categorical"},
                "unit_overrides": {"temperature": "degC"},
            }

        Parameters:
            d: Configuration dictionary.

        Returns:
            A populated ``UOCConfig`` instance.
        """
        general = d.get("general", {})
        parser = d.get("parser", {})
        type_overrides_raw = d.get("type_overrides", {})
        unit_overrides = d.get("unit_overrides", {})

        # Parse enums from strings, with safe defaults
        missing_str = general.get("missing_strategy", "leave")
        alignment_str = general.get("alignment_strategy", "forward_fill")
        quality_str = general.get("default_quality", "measured")

        type_overrides = {
            k: DataType(v) for k, v in type_overrides_raw.items()
        }

        return cls(
            timestamp_column=general.get("timestamp_column"),
            timestamp_format=general.get("timestamp_format"),
            default_quality=Quality[quality_str.upper()],
            batch_size=general.get("batch_size", 10_000),
            missing_strategy=MissingStrategy(missing_str),
            alignment_strategy=AlignmentStrategy(alignment_str),
            type_overrides=type_overrides,
            unit_overrides=unit_overrides,
            parser_config=ParserConfig(
                timestamp_column=parser.get("timestamp_column"),
                timestamp_format=parser.get("timestamp_format"),
                delimiter=parser.get("delimiter", ","),
                kv_separator=parser.get("kv_separator", "="),
                kv_delimiter=parser.get("kv_delimiter", ","),
                text_patterns=parser.get("text_patterns", []),
                encoding=parser.get("encoding", "utf-8"),
            ),
            default_missing_value=general.get("default_missing_value"),
        )
