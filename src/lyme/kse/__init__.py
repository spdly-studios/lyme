"""
Lyme - Knowledge Synthesis Engine (KSE)

Component 2 of the Lyme pipeline.

Receives canonical observations from the Universal Observation Canonicalizer
(UOC, Component 1) and automatically discovers interpretable operational
knowledge about an unknown system.

The engine discovers:
- Variable relationships (correlation, influence, causality)
- State relationships (co-occurrence, clustering)
- Trigger relationships (event-driven causality with lag)
- Threshold effects (IF/THEN rules)
- Temporal relationships (delayed effects, lag estimation)
- Operational modes (unsupervised mode clustering)
- State transitions (mode-to-mode transition graph)

All discoveries are graded by confidence and evidence level.
"""

from .engine import KnowledgeSynthesisEngine
from .config import (
    CausalConfig,
    CorrelationConfig,
    KSEConfig,
    ModeConfig,
    TemporalConfig,
    ThresholdConfig,
)
from .ingestion import IngestionResult, load_csv, load_dataframe, load_from_uoc, load_parquet
from .models import (
    EvidenceLevel,
    Finding,
    KnowledgeGraph,
    OperationalMode,
    Relationship,
    RelationType,
    Rule,
    SystemModel,
)

__all__ = [
    "KnowledgeSynthesisEngine",
    "KSEConfig",
    "CorrelationConfig",
    "TemporalConfig",
    "CausalConfig",
    "ThresholdConfig",
    "ModeConfig",
    "IngestionResult",
    "load_csv",
    "load_parquet",
    "load_dataframe",
    "load_from_uoc",
    "EvidenceLevel",
    "Finding",
    "KnowledgeGraph",
    "OperationalMode",
    "Relationship",
    "RelationType",
    "Rule",
    "SystemModel",
]
