"""
KSE JSON Knowledge Graph Exporter.

Serializes the KnowledgeGraph to a standard machine-readable JSON format.
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


class GraphJSONExporter:
    """Exports the compiled KnowledgeGraph as a structured JSON object."""

    def export(self, model: SystemModel, output: Path | str | IO[str]) -> None:
        """Export the graph as JSON.

        Parameters:
            model: The synthesised SystemModel.
            output: Target file path or stream.
        """
        graph = model.graph
        nodes_list = []
        for name, node in graph.nodes.items():
            nodes_list.append({
                "id": node.name,
                "type": node.node_type,
                "metadata": node.metadata
            })

        edges_list = []
        for edge in graph.edges:
            edges_list.append({
                "source": edge.source,
                "target": edge.target,
                "relation_type": edge.relation_type.value,
                "confidence": edge.confidence,
                "evidence_level": edge.evidence_level.value,
                "estimated_lag": edge.estimated_lag,
                "supporting_methods": edge.supporting_methods,
                "metadata": edge.metadata
            })

        data = {
            "nodes": nodes_list,
            "edges": edges_list,
            "metadata": {
                "variables_count": len(model.variable_names),
                "timestamps_analyzed": model.timestamp_count,
            }
        }

        if isinstance(output, (str, Path)):
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, cls=KSEJSONEncoder, indent=2)
        else:
            json.dump(data, output, cls=KSEJSONEncoder, indent=2)
