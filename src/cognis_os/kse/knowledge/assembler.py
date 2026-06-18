"""
KSE Knowledge Assembler.

Merges findings, relationships, rules, and modes from different analyzers,
deduplicates them, resolves conflicts, adjusts confidence scores, and constructs
the final system operational model.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import KSEConfig
from ..models import (
    Contradiction,
    EvidenceLevel,
    Finding,
    KnowledgeGraph,
    ModeTransition,
    OperationalMode,
    Relationship,
    RelationType,
    Rule,
    SystemModel,
)
from .contradiction import ContradictionDetector
from .graph import GraphBuilder

logger = logging.getLogger(__name__)


class KnowledgeAssembler:
    """Combines outputs from multiple analyzers into a unified system model."""

    def __init__(self, config: KSEConfig) -> None:
        self.config = config

    def assemble(
        self,
        variable_names: list[str],
        findings: list[Finding],
        relationships: list[Relationship],
        rules: list[Rule],
        modes: list[OperationalMode],
        transitions: list[ModeTransition],
        variable_metadata: dict[str, dict[str, Any]] | None = None,
        total_timestamps: int = 0,
    ) -> SystemModel:
        """Merge, deduplicate, score, and compile the final SystemModel.

        Parameters:
            variable_names: Names of all variables in the system.
            findings: Level-1 statistical observations.
            relationships: Level-2 directed relationships.
            rules: Level-3 IF/THEN rules.
            modes: Level-4 operational modes.
            transitions: Mode transitions.
            variable_metadata: Optional registry metadata.
            total_timestamps: Total timestamps in the telemetry.

        Returns:
            The compiled SystemModel.
        """
        # 1. Merge and deduplicate relationships
        merged_relationships = self._merge_relationships(relationships)

        # 2. Filter findings, relationships, and rules by minimum confidence
        min_conf = self.config.min_confidence_report
        filtered_findings = [f for f in findings if f.confidence >= min_conf]
        filtered_relationships = [r for r in merged_relationships if r.confidence >= min_conf]
        filtered_rules = [ru for ru in rules if ru.confidence >= min_conf]

        # 3. Detect contradictions
        detector = ContradictionDetector()
        contradictions = detector.detect(
            findings=filtered_findings,
            relationships=filtered_relationships,
            rules=filtered_rules,
            modes=modes,
        )

        # 4. Build the KnowledgeGraph representation
        builder = GraphBuilder()
        graph = builder.build(
            variable_names=variable_names,
            relationships=filtered_relationships,
            rules=filtered_rules,
            modes=modes,
            transitions=transitions,
            variable_metadata=variable_metadata,
        )

        # 5. Build final system model container
        return SystemModel(
            findings=filtered_findings,
            relationships=filtered_relationships,
            rules=filtered_rules,
            modes=modes,
            mode_transitions=transitions,
            graph=graph,
            contradictions=contradictions,
            variable_names=variable_names,
            timestamp_count=total_timestamps,
            metadata=self.config.metadata,
        )

    # ------------------------------------------------------------------

    def _merge_relationships(self, relationships: list[Relationship]) -> list[Relationship]:
        """Group relationships by (source, target, relation_type) and merge statistics."""
        grouped: dict[tuple[str, str, RelationType], list[Relationship]] = {}
        for r in relationships:
            key = (r.source, r.target, r.relation_type)
            grouped.setdefault(key, []).append(r)

        merged: list[Relationship] = []
        for (src, tgt, rtype), items in grouped.items():
            # Combine supporting methods
            methods = []
            for item in items:
                for m in item.supporting_methods:
                    if m not in methods:
                        methods.append(m)

            # Consensus confidence boosting formula:
            # take max confidence, and boost slightly for each additional unique supporting method
            max_conf = max(item.confidence for item in items)
            if len(methods) > 1:
                boost = 0.05 * (len(methods) - 1)
                confidence = min(max_conf + boost, 0.98)
            else:
                confidence = max_conf

            # Average other stats
            avg_lag = float(sum(item.estimated_lag for item in items) / len(items))
            avg_lag_conf = float(sum(item.lag_confidence for item in items) / len(items))
            avg_coverage = float(sum(item.data_coverage for item in items) / len(items))

            # Pick minimum p-value if available
            p_values = [item.p_value for item in items if item.p_value is not None]
            min_p = min(p_values) if p_values else None

            # Collect metadata
            meta: dict[str, Any] = {}
            for item in items:
                meta.update(item.metadata)

            # Re-evaluate evidence level based on boosted confidence
            evidence_level = _confidence_to_evidence(confidence)

            merged.append(
                Relationship(
                    source=src,
                    target=tgt,
                    relation_type=rtype,
                    confidence=confidence,
                    evidence_level=evidence_level,
                    estimated_lag=avg_lag,
                    lag_confidence=avg_lag_conf,
                    p_value=min_p,
                    data_coverage=avg_coverage,
                    supporting_methods=methods,
                    metadata=meta,
                )
            )

        return merged


def _confidence_to_evidence(confidence: float) -> EvidenceLevel:
    """Resolve EvidenceLevel from confidence score."""
    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
