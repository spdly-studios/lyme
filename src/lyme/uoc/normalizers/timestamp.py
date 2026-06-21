"""Timestamp normalization for UOC.

Parses various timestamp formats (Unix epoch, ISO 8601, human-readable)
and normalizes them to float Unix epoch seconds.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
import dateutil.parser


# Regexes for heuristics
_UNIX_EPOCH_RE = re.compile(r"^\d+(\.\d+)?$")
# Matches typical ISO formats like 2026-06-18, 2026/06/18, etc.
_DATE_LIKE_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}"  # YYYY-MM-DD or YYYY/MM/DD
    r"|\d{2}[-/]\d{2}[-/]\d{4}"  # DD-MM-YYYY or MM-DD-YYYY
    r"|[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"  # Syslog (e.g. Jun 18 08:01:22)
    r"|[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"  # Ctime (e.g. Thu Jun 18 08:01:22 2026)
)


class TimestampNormalizer:
    """Normalizes various timestamp formats to Unix epoch seconds (float)."""

    @staticmethod
    def is_timestamp(value: str) -> bool:
        """Heuristically check if a string representation looks like a timestamp.

        Parameters:
            value: The string to test.

        Returns:
            True if the string is likely a timestamp, False otherwise.
        """
        val_strip = value.strip()
        if not val_strip:
            return False

        # If it looks like a Unix timestamp (numeric, length > 8, or small numbers if relative)
        if _UNIX_EPOCH_RE.match(val_strip):
            # If it's a number, it could be a relative timestamp or a Unix timestamp.
            # Usually, raw numbers in logs can be values (like 42). So we require
            # it to be a float/int but we also check other clues.
            # In UOC, we assume if we check a candidate column for timestamp-ness,
            # we check if it parses. If it's a Unix timestamp, it's a number.
            # Let's say any numeric value can be a timestamp. But to avoid false positives,
            # if it's a large integer (e.g., > 10^9), it's definitely a Unix timestamp.
            # Let's check if it parses.
            try:
                float(val_strip)
                return True
            except ValueError:
                return False

        # If it matches date-like regex patterns
        if _DATE_LIKE_RE.search(val_strip):
            return True

        # Try to parse it as dateutil parser
        try:
            dateutil.parser.parse(val_strip)
            return True
        except (ValueError, OverflowError, TypeError):
            return False

    @classmethod
    def normalize(
        cls,
        raw: str | int | float | None,
        format_hint: str | None = None,
    ) -> tuple[float, str | None]:
        """Normalize any supported timestamp representation to Unix epoch seconds (float).

        Parameters:
            raw: The raw timestamp value.
            format_hint: Optional strftime format hint.

        Returns:
            A tuple of (normalized_epoch_seconds, original_string_representation).
        """
        if raw is None:
            return 0.0, None

        if isinstance(raw, (int, float)):
            return float(raw), str(raw)

        # Parse string
        raw_str = str(raw).strip()
        if not raw_str:
            return 0.0, None

        # Check if it is a pure numeric epoch timestamp
        if _UNIX_EPOCH_RE.match(raw_str):
            try:
                return float(raw_str), raw_str
            except ValueError:
                pass

        # Try using format_hint if provided
        if format_hint:
            try:
                dt = datetime.strptime(raw_str, format_hint)
                # If naive, assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp(), raw_str
            except ValueError:
                pass

        # Try standard ISO parser
        try:
            dt = datetime.fromisoformat(raw_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp(), raw_str
        except ValueError:
            pass

        # Try dateutil parser
        try:
            # fuzzy=True can be helpful, but let's try direct parse first
            dt = dateutil.parser.parse(raw_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp(), raw_str
        except (ValueError, OverflowError, TypeError):
            pass

        # If it doesn't parse, but is numeric-ish, try fallback float conversion
        try:
            return float(raw_str), raw_str
        except ValueError:
            raise ValueError(f"Could not parse timestamp: {raw_str}")
