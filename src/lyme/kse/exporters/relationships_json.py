"""
KSE JSON Relationship Exporter.

Serializes the discovered Level-1 and Level-2 variable relationships to a
machine-readable JSON database format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO

from ..models import SystemModel


class KSEJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, (np.int64, np.int32, np.integer)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32, np.floating)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class RelationshipsJSONExporter:
    """Exports relationships and findings as a structured JSON object."""

    def export(self, model: SystemModel, output: Path | str | IO[str]) -> None:
        """Export relationships as JSON.

        Parameters:
            model: The synthesised SystemModel.
            output: Target file path or stream.
        """
        rels_list = []
        for r in model.relationships:
            rels_list.append({
                "source": r.source,
                "target": r.target,
                "relation_type": r.relation_type.value,
                "confidence": r.confidence,
                "evidence_level": r.evidence_level.value,
                "estimated_lag": r.estimated_lag,
                "lag_confidence": r.lag_confidence,
                "p_value": r.p_value,
                "data_coverage": r.data_coverage,
                "supporting_methods": r.supporting_methods,
                "metadata": r.metadata
            })

        findings_list = []
        for f in model.findings:
            findings_list.append({
                "variables": f.variables,
                "description": f.description,
                "confidence": f.confidence,
                "evidence_level": f.evidence_level.value,
                "metric_name": f.metric_name,
                "metric_value": f.metric_value,
                "data_coverage": f.data_coverage,
                "p_value": f.p_value,
                "method": f.method,
                "metadata": f.metadata
            })

        data = {
            "relationships": rels_list,
            "findings": findings_list,
            "metadata": {
                "relationships_count": len(rels_list),
                "findings_count": len(findings_list),
                "timestamps_analyzed": model.timestamp_count
            }
        }

        if isinstance(output, (str, Path)):
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, cls=KSEJSONEncoder, indent=2)
        else:
            json.dump(data, output, cls=KSEJSONEncoder, indent=2)
