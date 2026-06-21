"""
KSE Knowledge Graph Builder.

Populates the KnowledgeGraph structure with nodes and edges representing the
discovered variables, relationships, operational modes, and transitions.
"""

from __future__ import annotations

from typing import Any

from ..models import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    ModeTransition,
    OperationalMode,
    Relationship,
    RelationType,
    Rule,
)


class GraphBuilder:
    """Assembles a unified KnowledgeGraph from nodes and edges."""

    def __init__(self) -> None:
        self.graph = KnowledgeGraph()

    def build(
        self,
        variable_names: list[str],
        relationships: list[Relationship],
        rules: list[Rule],
        modes: list[OperationalMode],
        transitions: list[ModeTransition],
        variable_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> KnowledgeGraph:
        """Construct a KnowledgeGraph.

        Parameters:
            variable_names: Names of all variables in the system.
            relationships: Discovered Level-2 relationships.
            rules: Discovered Level-3 rules (can be linked to target nodes).
            modes: Discovered Level-4 operational modes.
            transitions: Mode transition edges.
            variable_metadata: Optional UOC variable metadata.

        Returns:
            An populated KnowledgeGraph instance.
        """
        # 1. Add variable nodes
        var_meta = variable_metadata or {}
        for var in variable_names:
            self.graph.add_node(
                KnowledgeGraphNode(
                    name=var,
                    node_type="variable",
                    metadata=var_meta.get(var, {}),
                )
            )

        # 2. Add mode nodes
        for mode in modes:
            self.graph.add_node(
                KnowledgeGraphNode(
                    name=mode.label,
                    node_type="mode",
                    metadata={
                        "description": mode.description,
                        "centroid": mode.centroid,
                        "prevalence": mode.prevalence,
                        "distinguishing_features": mode.distinguishing_features,
                    },
                )
            )

        # 3. Add edges from relationships
        for rel in relationships:
            self.graph.add_edge(
                KnowledgeGraphEdge(
                    source=rel.source,
                    target=rel.target,
                    relation_type=rel.relation_type,
                    confidence=rel.confidence,
                    evidence_level=rel.evidence_level,
                    estimated_lag=rel.estimated_lag,
                    supporting_methods=rel.supporting_methods,
                    metadata=rel.metadata,
                )
            )

        # 4. Add edges from transitions
        for trans in transitions:
            self.graph.add_edge(
                KnowledgeGraphEdge(
                    source=trans.from_mode,
                    target=trans.to_mode,
                    relation_type=RelationType.TRANSITIONS_TO, # Mapping to the TransitionsTo relation type
                    confidence=trans.confidence,
                    evidence_level=EvidenceLevel_from_confidence(trans.confidence),
                    estimated_lag=0.0,
                    supporting_methods=["transition_analysis"],
                    metadata={
                        "count": trans.count,
                        "probability": trans.probability,
                    },
                )
            )

        return self.graph


def EvidenceLevel_from_confidence(confidence: float) -> Any:
    """Resolve EvidenceLevel enum from confidence score."""
    from ..models import EvidenceLevel

    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
