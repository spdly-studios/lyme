"""
KSE Data Models.

Defines the universal knowledge representation used throughout the
Knowledge Synthesis Engine.  Every discovered fact, regardless of which
analyzer produced it, is ultimately encoded in one of these structures.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Enumerated types
# ---------------------------------------------------------------------------


class EvidenceLevel(enum.Enum):
    """Epistemic confidence level of a discovered relationship.

    Attributes:
        OBSERVED: Strongly supported by multiple statistical methods with
            high data coverage and low p-values.  The relationship is very
            likely real.
        PROBABLE: Supported by at least one method with moderate confidence.
            Treat as a working hypothesis.
        SPECULATIVE: Weak statistical support or low data coverage.  Should
            be presented as a hypothesis to investigate, not a conclusion.
    """

    OBSERVED = "observed"
    PROBABLE = "probable"
    SPECULATIVE = "speculative"


class RelationType(enum.Enum):
    """The category of relationship between two variables.

    Attributes:
        CORRELATES: Variables co-vary without establishing direction.
        INFLUENCES: Variable A causally influences variable B.
        TRIGGERS: A discrete event in A is followed by a change in B.
        THRESHOLD: A crosses a threshold value causing an effect in B.
        CO_OCCURS: States of A and B frequently appear together.
        TRANSITIONS_TO: Operational mode A transitions to mode B.
    """

    CORRELATES = "correlates"
    INFLUENCES = "influences"
    TRIGGERS = "triggers"
    THRESHOLD = "threshold"
    CO_OCCURS = "co_occurs"
    TRANSITIONS_TO = "transitions_to"


# ---------------------------------------------------------------------------
# Core finding structures
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """Level 1 — A statistical observation about one or two variables.

    Represents a raw signal found in the data: a correlation, a distribution
    characteristic, or a co-occurrence pattern.

    Attributes:
        variables: Names of variables involved.
        description: Human-readable description.
        confidence: Confidence score in [0, 1].
        evidence_level: Epistemic strength.
        metric_name: Statistical metric used (e.g., ``pearson_r``).
        metric_value: Numeric value of the metric.
        data_coverage: Fraction of timestamps used (non-null fraction).
        p_value: Statistical p-value if applicable.
        method: The analyzer method that produced this finding.
        metadata: Additional analyzer-specific metadata.
    """

    variables: list[str]
    description: str
    confidence: float
    evidence_level: EvidenceLevel
    metric_name: str
    metric_value: float
    data_coverage: float = 1.0
    p_value: float | None = None
    method: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """Level 2 — A directed relationship between two variables.

    Captures the direction, temporal lag, and causal character of an
    association discovered between two variables.

    Attributes:
        source: Name of the influencing variable.
        target: Name of the influenced variable.
        relation_type: Category of the relationship.
        confidence: Confidence score in [0, 1].
        evidence_level: Epistemic strength.
        estimated_lag: Estimated time lag in original timestamp units.
            Zero means the effect is immediate.
        lag_confidence: Confidence in the lag estimate.
        p_value: Statistical p-value if applicable.
        data_coverage: Fraction of data used.
        supporting_methods: List of analyzer method names that agree.
        metadata: Additional relationship metadata.
    """

    source: str
    target: str
    relation_type: RelationType
    confidence: float
    evidence_level: EvidenceLevel
    estimated_lag: float = 0.0
    lag_confidence: float = 0.0
    p_value: float | None = None
    data_coverage: float = 1.0
    supporting_methods: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Condition:
    """A single predicate in a rule condition.

    Attributes:
        variable: Variable name.
        operator: Comparison operator (``>``, ``<``, ``>=``, ``<=``, ``==``).
        threshold: Threshold value.
    """

    variable: str
    operator: str
    threshold: float


@dataclass
class Rule:
    """Level 3 — An interpretable IF/THEN operational rule.

    Rules are expressed as human-readable predicates.  They are produced
    by tree-based threshold analysis.

    Attributes:
        conditions: List of conditions that must all hold (AND logic).
        target_variable: The variable whose behaviour is explained.
        outcome_description: Human-readable outcome text.
        confidence: Confidence in [0, 1].
        evidence_level: Epistemic strength.
        support: Fraction of data that satisfies the conditions.
        precision: Fraction of condition-satisfying rows where outcome holds.
        p_value: Statistical significance if available.
        metadata: Additional metadata.
    """

    conditions: list[Condition]
    target_variable: str
    outcome_description: str
    confidence: float
    evidence_level: EvidenceLevel
    support: float = 0.0
    precision: float = 0.0
    p_value: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        """Render rule as a human-readable IF/THEN statement."""
        if not self.conditions:
            return f"(unconditional) → {self.outcome_description}"
        parts = []
        for c in self.conditions:
            parts.append(f"{c.variable} {c.operator} {c.threshold:.4g}")
        condition_str = " AND ".join(parts)
        return f"IF {condition_str} THEN {self.outcome_description}"


@dataclass
class OperationalMode:
    """Level 4 — A naturally occurring operational state of the system.

    Modes are discovered through unsupervised clustering of the state matrix.

    Attributes:
        label: Discovered label (e.g., ``Mode_2`` or a derived descriptive name).
        description: Human-readable description based on dominant variable ranges.
        centroid: Dict mapping variable name to centroid value.
        member_count: Number of timestamps assigned to this mode.
        total_count: Total number of timestamps in the dataset.
        distinguishing_features: Variables that most differentiate this mode.
        confidence: Clustering confidence / silhouette score.
        metadata: Additional metadata.
    """

    label: str
    description: str
    centroid: dict[str, float]
    member_count: int
    total_count: int
    distinguishing_features: list[str]
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prevalence(self) -> float:
        """Fraction of time the system spends in this mode."""
        if self.total_count == 0:
            return 0.0
        return self.member_count / self.total_count


@dataclass
class ModeTransition:
    """A directed transition between two operational modes.

    Attributes:
        from_mode: Source mode label.
        to_mode: Target mode label.
        count: Observed number of transitions.
        probability: Transition probability from source mode.
        confidence: Confidence in this transition.
    """

    from_mode: str
    to_mode: str
    count: int
    probability: float
    confidence: float


@dataclass
class KnowledgeGraphNode:
    """A node in the knowledge graph — represents a variable or mode.

    Attributes:
        name: Node name (variable name or mode label).
        node_type: ``"variable"`` or ``"mode"``.
        metadata: Variable dtype, unit, or mode centroid.
    """

    name: str
    node_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraphEdge:
    """A directed edge in the knowledge graph.

    Attributes:
        source: Source node name.
        target: Target node name.
        relation_type: The RelationType of this edge.
        confidence: Confidence score.
        evidence_level: Epistemic strength.
        estimated_lag: Time lag in original units.
        supporting_methods: Methods that agree on this edge.
        metadata: Additional edge metadata.
    """

    source: str
    target: str
    relation_type: RelationType
    confidence: float
    evidence_level: EvidenceLevel
    estimated_lag: float = 0.0
    supporting_methods: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    """The complete machine-readable knowledge graph.

    Attributes:
        nodes: Dict from node name to KnowledgeGraphNode.
        edges: List of directed KnowledgeGraphEdge objects.
    """

    nodes: dict[str, KnowledgeGraphNode] = field(default_factory=dict)
    edges: list[KnowledgeGraphEdge] = field(default_factory=list)

    def add_node(self, node: KnowledgeGraphNode) -> None:
        """Add or overwrite a node."""
        self.nodes[node.name] = node

    def add_edge(self, edge: KnowledgeGraphEdge) -> None:
        """Append a directed edge."""
        self.edges.append(edge)

    def get_edges_from(self, source: str) -> list[KnowledgeGraphEdge]:
        """Return all outgoing edges from *source*."""
        return [e for e in self.edges if e.source == source]

    def get_edges_to(self, target: str) -> list[KnowledgeGraphEdge]:
        """Return all incoming edges to *target*."""
        return [e for e in self.edges if e.target == target]


@dataclass
class Contradiction:
    """A detected conflict between two findings or relationships.

    Attributes:
        description: Human-readable description of the conflict.
        finding_a: First conflicting item (description or repr).
        finding_b: Second conflicting item.
        severity: ``"high"`` | ``"medium"`` | ``"low"``.
    """

    description: str
    finding_a: str
    finding_b: str
    severity: str = "medium"


@dataclass
class SystemModel:
    """Level 5 — The complete synthesised operational model of the system.

    Attributes:
        findings: All Level-1 observations.
        relationships: All Level-2 directed relationships.
        rules: All Level-3 IF/THEN rules.
        modes: All Level-4 operational modes.
        mode_transitions: All mode transition edges.
        graph: The assembled knowledge graph.
        contradictions: Detected conflicts.
        variable_names: All variable names observed.
        timestamp_count: Total number of timestamps in the input.
        metadata: Additional model metadata.
    """

    findings: list[Finding] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    modes: list[OperationalMode] = field(default_factory=list)
    mode_transitions: list[ModeTransition] = field(default_factory=list)
    graph: KnowledgeGraph = field(default_factory=KnowledgeGraph)
    contradictions: list[Contradiction] = field(default_factory=list)
    variable_names: list[str] = field(default_factory=list)
    timestamp_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
