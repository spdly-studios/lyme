"""Base exporter interface for UOC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from ..config import ExportConfig
from ..registry import VariableRegistry
from ..store import ObservationStore


class BaseExporter(ABC):
    """Abstract base class for all exporters."""

    @abstractmethod
    def export(
        self,
        store: ObservationStore,
        registry: VariableRegistry,
        output: Path | IO[str],
        config: ExportConfig | None = None,
    ) -> None:
        """Export observations to the given output.

        Parameters:
            store: The ObservationStore containing the data.
            registry: The VariableRegistry containing metadata.
            output: Path to write to, or open text IO stream.
            config: Optional ExportConfig.
        """
        pass

    @contextmanager
    def _open_output(
        self,
        output: Path | IO[str],
    ) -> Iterator[IO[str]]:
        """Helper to open a Path or yield an existing IO stream."""
        if isinstance(output, Path):
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8", newline="") as f:
                yield f
        else:
            yield output
