"""
KSE Configuration.

Defines all tunable parameters for the Knowledge Synthesis Engine.
Users can instantiate ``KSEConfig`` and override any defaults before
passing it to ``KnowledgeSynthesisEngine``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CorrelationConfig:
    """Configuration for the CorrelationAnalyzer.

    Attributes:
        pearson_threshold: Minimum |r| to emit a Pearson finding.
        spearman_threshold: Minimum |rho| to emit a Spearman finding.
        mi_threshold: Minimum mutual information score to emit a finding.
        p_value_threshold: Maximum p-value to accept a finding.
        min_data_coverage: Minimum fraction of non-null pairs required.
    """

    pearson_threshold: float = 0.5
    spearman_threshold: float = 0.5
    mi_threshold: float = 0.2
    p_value_threshold: float = 0.05
    min_data_coverage: float = 0.5


@dataclass
class TemporalConfig:
    """Configuration for the TemporalAnalyzer.

    Attributes:
        max_lag_steps: Maximum lag window in time steps (±).
        min_xcorr_threshold: Minimum cross-correlation peak to report.
        trigger_jump_z: Z-score threshold to identify a discrete jump/trigger event.
        min_trigger_samples: Minimum number of trigger events to report.
    """

    max_lag_steps: int = 50
    min_xcorr_threshold: float = 0.4
    trigger_jump_z: float = 2.5
    min_trigger_samples: int = 3


@dataclass
class CausalConfig:
    """Configuration for the CausalAnalyzer (Granger).

    Attributes:
        max_lag_steps: Maximum lag order for Granger causality tests.
        p_value_threshold: Maximum p-value to accept a causal finding.
        max_pairs: Maximum number of variable pairs to test (avoids O(n²) blowup).
            Pairs are selected by highest correlation rank.
    """

    max_lag_steps: int = 10
    p_value_threshold: float = 0.05
    max_pairs: int = 100


@dataclass
class ThresholdConfig:
    """Configuration for the ThresholdAnalyzer (decision tree rules).

    Attributes:
        max_depth: Maximum decision tree depth (keeps rules interpretable).
        min_samples_leaf: Minimum samples per leaf.
        min_support: Minimum fraction of data that must satisfy a rule condition.
        min_precision: Minimum precision (outcome hold rate) for a rule.
        max_conditions: Maximum number of conditions per rule (tree depth cap).
    """

    max_depth: int = 4
    min_samples_leaf: int = 10
    min_support: float = 0.05
    min_precision: float = 0.6
    max_conditions: int = 3


@dataclass
class ModeConfig:
    """Configuration for the ModeAnalyzer (clustering).

    Attributes:
        min_cluster_size: HDBSCAN minimum cluster size.
        min_samples: HDBSCAN min_samples parameter.
        kmeans_max_k: Maximum k to try when falling back to KMeans.
        min_mode_prevalence: Minimum fraction of timestamps a mode must cover
            to be reported (filters noise clusters).
        n_distinguishing_features: Number of top distinguishing features to
            include in mode descriptions.
    """

    min_cluster_size: int = 5
    min_samples: int = 3
    kmeans_max_k: int = 8
    min_mode_prevalence: float = 0.02
    n_distinguishing_features: int = 4


@dataclass
class KSEConfig:
    """Top-level configuration for the Knowledge Synthesis Engine.

    Attributes:
        correlation: CorrelationAnalyzer settings.
        temporal: TemporalAnalyzer settings.
        causal: CausalAnalyzer settings.
        threshold: ThresholdAnalyzer settings.
        mode: ModeAnalyzer settings.
        min_confidence_report: Minimum confidence to include in outputs.
        numeric_only: If True, skip non-numeric variables in all analyses.
        verbose: Emit progress messages during analysis.
        metadata: Free-form metadata attached to the output SystemModel.
    """

    correlation: CorrelationConfig = field(default_factory=CorrelationConfig)
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    causal: CausalConfig = field(default_factory=CausalConfig)
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    mode: ModeConfig = field(default_factory=ModeConfig)
    min_confidence_report: float = 0.3
    numeric_only: bool = False
    verbose: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
