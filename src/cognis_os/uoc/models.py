"""
Canonical data models for the Universal Observation Canonicalizer.

Defines the universal observation representation used throughout UOC.
Every piece of observational data, regardless of source domain, is
ultimately represented using these structures.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Quality(enum.IntEnum):
    """Quality indicator for an observation value.

    Tracks the provenance of a value to inform downstream consumers
    about how much to trust each data point.
    """

    MEASURED = 0
    ESTIMATED = 1
    INTERPOLATED = 2
    DERIVED = 3
    UNKNOWN = 4


class DataType(enum.Enum):
    """Supported data types for observed variables."""

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CATEGORICAL = "categorical"
    ENUM = "enum"
    TIMESTAMP = "timestamp"


@dataclass(slots=True)
class Variable:
    """A registered variable in the observation system.

    Variables represent the identity of what is being observed (e.g.,
    ``temperature``, ``motor_speed``).  Each variable is assigned a unique
    integer ID for compact storage in observations.

    Attributes:
        id: Unique integer identifier.
        name: Human-readable variable name.
        dtype: The data type of values for this variable.
        unit: Canonical unit string (e.g. ``degC``, ``RPM``), or ``None``.
        source: Origin identifier (e.g. filename, sensor ID).
        metadata: Extensible metadata bag for domain-specific info.
    """

    id: int
    name: str
    dtype: DataType
    unit: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RawObservation:
    """Intermediate representation produced by parsers before canonicalization.

    Parsers yield ``RawObservation`` instances which are then processed by
    normalizers to produce canonical ``Observation`` instances.

    Attributes:
        timestamp_raw: Original timestamp in whatever form the parser found it.
        variable_name: Name of the observed variable.
        value_raw: Raw value as a string.
        source: Origin identifier.
        unit_raw: Raw unit string extracted from the value (e.g. ``mV``).
        metadata: Optional additional metadata from the parser.
    """

    timestamp_raw: str | float | int | None
    variable_name: str
    value_raw: str
    source: str | None = None
    unit_raw: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class Observation:
    """Canonical observation — the universal representation.

    This is the core data unit of UOC.  Every piece of observational data,
    regardless of its original format or domain, is converted into this
    representation.

    Attributes:
        timestamp: Normalized Unix epoch seconds (``float`` for sub-second
            precision).
        variable_id: Integer ID referencing a ``Variable`` in the registry.
        value: The observed value, coerced to the variable's declared type.
        quality: Quality indicator for this observation.
        original_timestamp: The original timestamp string, preserved for
            lossless round-tripping.
        source: Origin identifier.
    """

    timestamp: float
    variable_id: int
    value: Any
    quality: Quality = Quality.MEASURED
    original_timestamp: str | None = None
    source: str | None = None
