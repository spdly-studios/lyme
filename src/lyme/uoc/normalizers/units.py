"""Unit parsing and normalization for UOC using pint.

Parses unit strings from values and normalizes them to canonical base units.
"""

from __future__ import annotations

import logging
import re

import pint

logger = logging.getLogger(__name__)

# Initialize a single shared UnitRegistry
ureg = pint.UnitRegistry()
# Add RPM as a recognized unit alias if not already present
try:
    ureg.define("RPM = revolution / minute = rpm")
except pint.RedefinitionError:
    pass

# Mapping of raw unit strings to pint-recognized unit strings.
# 'C' is ambiguous (coulomb vs Celsius) — in telemetry/sensor context we default to Celsius.
UNIT_MAPPING: dict[str, str] = {
    # Temperature
    "C": "degC",
    "celsius": "degC",
    "Celsius": "degC",
    "F": "degF",
    "fahrenheit": "degF",
    "Fahrenheit": "degF",
    "K": "kelvin",
    # Voltage
    "V": "volt",
    "v": "volt",
    "volt": "volt",
    "volts": "volt",
    "mV": "millivolt",
    "mv": "millivolt",
    "millivolts": "millivolt",
    "kV": "kilovolt",
    "kv": "kilovolt",
    "kilovolts": "kilovolt",
    # Current
    "A": "ampere",
    "ampere": "ampere",
    "amperes": "ampere",
    "amps": "ampere",
    "mA": "milliampere",
    "ma": "milliampere",
    "milliamperes": "milliampere",
    # Power
    "W": "watt",
    "w": "watt",
    "watt": "watt",
    "watts": "watt",
    "kW": "kilowatt",
    "kw": "kilowatt",
    "kilowatts": "kilowatt",
    # Frequency
    "Hz": "hertz",
    "hz": "hertz",
    "hertz": "hertz",
    "kHz": "kilohertz",
    "MHz": "megahertz",
    # Rotation speed — map to RPM which we define above
    "rpm": "RPM",
    # Pressure
    "Pa": "pascal",
    "kPa": "kilopascal",
    "MPa": "megapascal",
    "bar": "bar",
    "atm": "atmosphere",
    "psi": "pound_force_per_square_inch",
    # Mass
    "kg": "kilogram",
    "g": "gram",
    "mg": "milligram",
    "lb": "pound",
    # Length
    "m": "meter",
    "km": "kilometer",
    "cm": "centimeter",
    "mm": "millimeter",
    "in": "inch",
    "ft": "foot",
    # Speed
    "m/s": "meter / second",
    "km/h": "kilometer / hour",
    "mph": "mile / hour",
    # Angle
    "deg": "degree",
    "rad": "radian",
}

# When to_base_units() would decompose into SI primitives, prefer these named units.
# Keyed by the pint dimensionality string.
_PREFERRED_UNITS: dict[str, str] = {
    # Voltage: kg·m²·A⁻¹·s⁻³
    "[mass] * [length] ** 2 / [time] ** 3 / [current]": "volt",
    # Power: kg·m²·s⁻³
    "[mass] * [length] ** 2 / [time] ** 3": "watt",
    # Pressure: kg·m⁻¹·s⁻²
    "[mass] / [length] / [time] ** 2": "pascal",
    # Force: kg·m·s⁻²
    "[mass] * [length] / [time] ** 2": "newton",
    # Frequency: s⁻¹
    "1 / [time]": "hertz",
    # Energy: kg·m²·s⁻²
    "[mass] * [length] ** 2 / [time] ** 2": "joule",
}


# Regex to split numeric value from trailing unit suffix.
# Handles: "4.1V", "28.5 C", "100 RPM", "4100mV", "1.3e-2 kPa"
_VALUE_UNIT_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*"
    r"([a-zA-Z°%°][a-zA-Z°%0-9_./*\-^]*)$"
)


class UnitNormalizer:
    """Parses and normalizes physical units using Pint."""

    @classmethod
    def parse_value_unit(cls, raw_value: str) -> tuple[str, str | None]:
        """Separate a value string from its trailing unit suffix.

        Examples::

            "4.1V"    → ("4.1", "V")
            "28.5 C"  → ("28.5", "C")
            "500"     → ("500", None)
            "100 RPM" → ("100", "RPM")

        Parameters:
            raw_value: The raw string value.

        Returns:
            A tuple of ``(value_string, unit_string_or_None)``.
        """
        val_strip = raw_value.strip()
        if not val_strip:
            return "", None

        match = _VALUE_UNIT_RE.match(val_strip)
        if not match:
            return val_strip, None

        return match.group(1), match.group(2)

    @classmethod
    def get_canonical_unit(cls, unit_str: str) -> str:
        """Resolve a raw unit string to its canonical pint form.

        Parameters:
            unit_str: Raw unit string, e.g. ``"mV"``, ``"RPM"``, ``"C"``.

        Returns:
            The canonical unit string recognized by pint (e.g. ``"millivolt"``).
        """
        unit_str = unit_str.strip()
        mapped = UNIT_MAPPING.get(unit_str, unit_str)
        try:
            u = ureg.Unit(mapped)
            return str(u)
        except pint.UndefinedUnitError:
            logger.warning("Undefined unit in pint registry: %s", unit_str)
            return unit_str

    @classmethod
    def normalize_unit(
        cls,
        value: float,
        from_unit: str,
        to_unit: str | None = None,
    ) -> tuple[float, str]:
        """Convert a value from one unit to another or to a preferred base unit.

        Parameters:
            value: The numeric value to convert.
            from_unit: The source unit string.
            to_unit: Target unit string. If ``None``, converts to the most
                readable named unit for the same dimension (e.g. ``"volt"``
                instead of ``"kg·m²/A/s³"``).

        Returns:
            A tuple of ``(converted_float, canonical_unit_string)``.
        """
        from_unit_clean = UNIT_MAPPING.get(from_unit.strip(), from_unit.strip())

        try:
            q = ureg.Quantity(value, from_unit_clean)

            if to_unit:
                to_unit_clean = UNIT_MAPPING.get(to_unit.strip(), to_unit.strip())
                q_converted = q.to(to_unit_clean)
                return float(q_converted.magnitude), str(q_converted.units)

            # No target: pick a human-friendly named unit over raw SI decomposition.
            dim_str = str(q.dimensionality)
            if dim_str in _PREFERRED_UNITS:
                preferred = _PREFERRED_UNITS[dim_str]
                q_converted = q.to(preferred)
                return float(q_converted.magnitude), str(q_converted.units)

            q_converted = q.to_base_units()
            return float(q_converted.magnitude), str(q_converted.units)

        except (pint.UndefinedUnitError, pint.DimensionalityError) as exc:
            logger.warning(
                "Unit conversion failed from '%s' to '%s': %s",
                from_unit, to_unit, exc,
            )
            return value, from_unit
