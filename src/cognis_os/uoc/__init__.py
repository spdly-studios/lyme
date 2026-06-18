"""Universal Observation Canonicalizer (UOC).

Transforms heterogeneous observational data into a single,
domain-independent canonical representation.
"""

from .canonicalizer import Canonicalizer, IngestionResult
from .config import AlignmentStrategy, ExportConfig, MissingStrategy, ParserConfig, UOCConfig
from .models import DataType, Observation, Quality, Variable

__version__ = "0.1.0"
__all__ = [
    "Canonicalizer",
    "IngestionResult",
    "UOCConfig",
    "ParserConfig",
    "ExportConfig",
    "MissingStrategy",
    "AlignmentStrategy",
    "DataType",
    "Observation",
    "Quality",
    "Variable",
]

