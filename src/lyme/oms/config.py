"""
OMS Config definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OMSConfig:
    """Configuration options for the Operational Model Synthesizer.

    Attributes:
        min_influence_confidence: Min confidence to include relationships in causal chains.
        equation_significance_pval: Max p-value to keep mathematical regression coefficients.
        max_poly_degree: Max polynomial degree to attempt during equation fitting.
        min_r2_score: Minimum R-squared to keep a derived mathematical model.
        subsystem_clustering_threshold: Distance threshold (1 - |corr|) for grouping variables.
        subsystem_max_clusters: Limit on the auto-discovered subsystems.
        verbose: Print progress messages.
        metadata: Custom metadata dictionary.
    """

    min_influence_confidence: float = 0.4
    equation_significance_pval: float = 0.05
    max_poly_degree: int = 2
    min_r2_score: float = 0.30
    subsystem_clustering_threshold: float = 0.75
    subsystem_max_clusters: int = 5
    verbose: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
