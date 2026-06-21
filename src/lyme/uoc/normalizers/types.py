"""Data type inference and coercion for UOC.

Automatically detects data types of observed values and coercing strings
to canonical representations.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import DataType
from .timestamp import TimestampNormalizer

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$")

_BOOL_TRUE = {"true", "yes", "on", "1"}
_BOOL_FALSE = {"false", "no", "off", "0"}


class TypeInferrer:
    """Infers DataType from string values and handles type coercion."""

    @classmethod
    def infer_type(cls, value: str) -> DataType:
        """Heuristically infer the DataType of a single string value.

        Parameters:
            value: The raw string value.

        Returns:
            The inferred DataType.
        """
        val_strip = value.strip()
        if not val_strip:
            return DataType.STRING

        # Boolean check
        val_lower = val_strip.lower()
        if val_lower in _BOOL_TRUE or val_lower in _BOOL_FALSE:
            return DataType.BOOLEAN

        # Integer check
        if _INT_RE.match(val_strip):
            return DataType.INTEGER

        # Float check
        if _FLOAT_RE.match(val_strip):
            return DataType.FLOAT

        # Timestamp check
        if TimestampNormalizer.is_timestamp(val_strip):
            return DataType.TIMESTAMP

        return DataType.STRING

    @classmethod
    def infer_type_for_series(cls, values: list[str]) -> DataType:
        """Infer the DataType for a sequence of string values.

        Parameters:
            values: A list of string representations.

        Returns:
            The inferred DataType for the series.
        """
        non_empty = [v.strip() for v in values if v is not None and str(v).strip() != ""]
        if not non_empty:
            return DataType.STRING

        inferred_types = [cls.infer_type(v) for v in non_empty]

        # Count frequencies
        unique_types = set(inferred_types)

        if unique_types == {DataType.INTEGER}:
            return DataType.INTEGER

        if unique_types.issubset({DataType.INTEGER, DataType.FLOAT}):
            return DataType.FLOAT

        if unique_types == {DataType.BOOLEAN}:
            return DataType.BOOLEAN

        if unique_types == {DataType.TIMESTAMP}:
            return DataType.TIMESTAMP

        # Check for categorical (low cardinality strings)
        unique_vals = set(non_empty)
        # If the number of unique values is very low relative to length
        # (e.g. < 10% of values, or absolute number of unique values < 20)
        # and it's a string, infer CATEGORICAL
        if len(unique_vals) < 20 or (len(unique_vals) / len(non_empty) < 0.10):
            return DataType.CATEGORICAL

        return DataType.STRING

    @classmethod
    def coerce(cls, value: Any, dtype: DataType) -> Any:
        """Coerce a value to a specific DataType.

        Parameters:
            value: The raw value (often string, but can be other types).
            dtype: The target DataType.

        Returns:
            The coerced value, or None if empty or invalid.
        """
        if value is None:
            return None

        val_str = str(value).strip()
        if val_str == "" or val_str.lower() in ("nan", "null", "none", "na"):
            return None

        try:
            if dtype == DataType.INTEGER:
                # If float string, convert to float first, then int
                if _FLOAT_RE.match(val_str):
                    return int(float(val_str))
                return int(val_str)

            if dtype == DataType.FLOAT:
                return float(val_str)

            if dtype == DataType.BOOLEAN:
                val_lower = val_str.lower()
                if val_lower in _BOOL_TRUE:
                    return True
                if val_lower in _BOOL_FALSE:
                    return False
                # Fallback to python bool truthiness
                return bool(value)

            if dtype == DataType.TIMESTAMP:
                epoch_sec, _ = TimestampNormalizer.normalize(val_str)
                return epoch_sec

            if dtype in (DataType.STRING, DataType.CATEGORICAL, DataType.ENUM):
                return val_str

        except (ValueError, TypeError, OverflowError):
            # Return None if coercion fails
            return None

        return value
