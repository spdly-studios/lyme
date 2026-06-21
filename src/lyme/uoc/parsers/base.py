"""Base parser interface for UOC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from ..config import ParserConfig
from ..models import RawObservation


class BaseParser(ABC):
    """Abstract base class for all input parsers."""

    @abstractmethod
    def parse(
        self,
        source: Path | IO[str],
        config: ParserConfig | None = None,
    ) -> Iterator[RawObservation]:
        """Yield raw observations lazily from the given source.

        Parameters:
            source: A Path to the file, or a file-like text stream.
            config: Optional parser configuration override.

        Yields:
            RawObservation instances.
        """
        pass

    def can_parse(self, source: Path) -> bool:
        """Heuristically return True if this parser can handle the given file.

        Parameters:
            source: Absolute path to the file.

        Returns:
            True if the file can likely be parsed by this parser, False otherwise.
        """
        return False
