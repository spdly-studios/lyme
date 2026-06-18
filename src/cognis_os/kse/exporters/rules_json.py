"""
KSE JSON Rules Exporter.

Serializes the discovered Level-3 rules to a machine-readable JSON format.
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


class RulesJSONExporter:
    """Exports discovered IF/THEN rules as a structured JSON object."""

    def export(self, model: SystemModel, output: Path | str | IO[str]) -> None:
        """Export rules as JSON.

        Parameters:
            model: The synthesised SystemModel.
            output: Target file path or stream.
        """
        rules_list = []
        for r in model.rules:
            conds = []
            for c in r.conditions:
                conds.append({
                    "variable": c.variable,
                    "operator": c.operator,
                    "threshold": c.threshold
                })

            rules_list.append({
                "conditions": conds,
                "target_variable": r.target_variable,
                "outcome_description": r.outcome_description,
                "rule_text": r.to_text(),
                "confidence": r.confidence,
                "evidence_level": r.evidence_level.value,
                "support": r.support,
                "precision": r.precision,
                "metadata": r.metadata
            })

        data = {
            "rules": rules_list,
            "metadata": {
                "rules_count": len(rules_list),
                "timestamps_analyzed": model.timestamp_count
            }
        }

        if isinstance(output, (str, Path)):
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, cls=KSEJSONEncoder, indent=2)
        else:
            json.dump(data, output, cls=KSEJSONEncoder, indent=2)
