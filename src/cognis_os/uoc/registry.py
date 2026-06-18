"""Variable registry for UOC.

Provides a thread-safe registry to map variable names and sources to unique
integer IDs, and store metadata like data types and units.
"""

from __future__ import annotations

import threading
from typing import Any

from .models import DataType, Variable


class VariableRegistry:
    """Thread-safe registry mapping variable names to unique IDs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_id: dict[int, Variable] = {}
        self._by_name: dict[str, Variable] = {}
        self._next_id = 1

    def register(
        self,
        name: str,
        dtype: DataType,
        unit: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Variable:
        """Register a new variable and assign it a unique integer ID.

        If a variable with the same name is already registered,
        an exception is raised.

        Parameters:
            name: The variable name.
            dtype: The data type of the variable.
            unit: Optional unit of measurement.
            source: Optional data source identifier.
            metadata: Optional additional metadata dict.

        Returns:
            The registered Variable object.
        """
        with self._lock:
            if name in self._by_name:
                raise ValueError(
                    f"Variable '{name}' is already registered."
                )

            var_id = self._next_id
            self._next_id += 1

            meta = dict(metadata) if metadata else {}
            variable = Variable(
                id=var_id,
                name=name,
                dtype=dtype,
                unit=unit,
                source=source,
                metadata=meta,
            )

            self._by_id[var_id] = variable
            self._by_name[name] = variable
            return variable

    def get_or_create(
        self,
        name: str,
        dtype: DataType | None = None,
        unit: str | None = None,
        source: str | None = None,
    ) -> Variable:
        """Get an existing variable, or create it if it doesn't exist.

        Parameters:
            name: The variable name.
            dtype: The data type if creating. Defaults to DataType.FLOAT if None.
            unit: The unit if creating.
            source: Optional data source identifier.

        Returns:
            The retrieved or newly created Variable object.
        """
        with self._lock:
            if name in self._by_name:
                return self._by_name[name]

            var_id = self._next_id
            self._next_id += 1

            resolved_dtype = dtype if dtype is not None else DataType.FLOAT
            variable = Variable(
                id=var_id,
                name=name,
                dtype=resolved_dtype,
                unit=unit,
                source=source,
                metadata={},
            )

            self._by_id[var_id] = variable
            self._by_name[name] = variable
            return variable

    def get_by_id(self, variable_id: int) -> Variable | None:
        """Look up a variable by its unique ID.

        Returns:
            The Variable if found, else None.
        """
        with self._lock:
            return self._by_id.get(variable_id)

    def get_by_name(self, name: str) -> Variable | None:
        """Look up a variable by its name.

        Returns:
            The Variable if found, else None.
        """
        with self._lock:
            return self._by_name.get(name)

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_id)

    def __contains__(self, item: Any) -> bool:
        with self._lock:
            if isinstance(item, int):
                return item in self._by_id
            if isinstance(item, str):
                return item in self._by_name
            return False

    def __iter__(self):
        with self._lock:
            # Return an iterator over a copy to maintain thread safety
            return iter(list(self._by_id.values()))

    def to_dict(self) -> list[dict[str, Any]]:
        """Serialize the registry to a list of dictionaries.

        Returns:
            A JSON-serializable list of dictionary representations.
        """
        with self._lock:
            result = []
            for var in self._by_id.values():
                result.append({
                    "id": var.id,
                    "name": var.name,
                    "dtype": var.dtype.value,
                    "unit": var.unit,
                    "source": var.source,
                    "metadata": var.metadata,
                })
            return result

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> VariableRegistry:
        """Deserialize a registry from a list of dictionaries.

        Parameters:
            data: List of dictionary representations.

        Returns:
            A new VariableRegistry populated with the data.
        """
        registry = cls()
        max_id = 0
        for item in data:
            dtype = DataType(item["dtype"])
            var = Variable(
                id=item["id"],
                name=item["name"],
                dtype=dtype,
                unit=item.get("unit"),
                source=item.get("source"),
                metadata=item.get("metadata", {}),
            )
            registry._by_id[var.id] = var
            registry._by_name[var.name] = var
            max_id = max(max_id, var.id)

        registry._next_id = max_id + 1
        return registry
