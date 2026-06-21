"""
OMS Subsystem Discovery.

Identifies major system components using hierarchical clustering of variables
based on correlation distance, and names them using keyword heuristics.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from .config import OMSConfig
from .models import Subsystem

logger = logging.getLogger(__name__)


class SubsystemDiscoverer:
    """Discovers logical subsystem components from variables and relationships."""

    def __init__(self, config: OMSConfig) -> None:
        self.config = config

    def discover(
        self,
        variable_names: list[str],
        relationships: list[Any],
        findings: list[Any],
        df: pd.DataFrame | None = None,
    ) -> list[Subsystem]:
        """Group variables into subsystems.

        Parameters:
            variable_names: List of all variables.
            relationships: List of Level-2 relationships.
            findings: List of Level-1 findings.
            df: Optional aligned state matrix.

        Returns:
            A list of discovered Subsystem dataclasses.
        """
        n_vars = len(variable_names)
        if n_vars == 0:
            return []
        if n_vars == 1:
            return [
                Subsystem(
                    name=f"{variable_names[0].capitalize()} Subsystem",
                    variables=variable_names,
                    description=f"Single-variable subsystem containing {variable_names[0]}.",
                )
            ]

        # 1. Build distance matrix
        dist_matrix = self._build_distance_matrix(variable_names, relationships, findings, df)

        # 2. Perform hierarchical clustering
        try:
            # Condensed distance matrix
            condensed = squareform(dist_matrix, checks=False)
            Z = linkage(condensed, method="complete")
            
            # Cut tree at threshold
            max_d = self.config.subsystem_clustering_threshold
            labels = fcluster(Z, t=max_d, criterion="distance")
            
            # Limit the number of clusters if needed
            max_c = self.config.subsystem_max_clusters
            unique_labels = np.unique(labels)
            if len(unique_labels) > max_c:
                labels = fcluster(Z, t=max_c, criterion="maxclust")
                unique_labels = np.unique(labels)
        except Exception as e:
            logger.warning(f"Hierarchical clustering failed: {e}. Falling back to single cluster.")
            labels = np.ones(n_vars, dtype=int)
            unique_labels = [1]

        # Group variables by cluster label
        clusters: dict[int, list[str]] = {}
        for idx, label in enumerate(labels):
            var_name = variable_names[idx]
            clusters.setdefault(label, []).append(var_name)

        # 3. Name and describe each cluster/subsystem
        subsystems: list[Subsystem] = []
        name_counts: dict[str, int] = {}

        for label, vars_in_cluster in clusters.items():
            base_name = self._name_cluster(vars_in_cluster)
            name_counts[base_name] = name_counts.get(base_name, 0) + 1
            
            # De-duplicate names if multiple subsystems get the same keyword name
            if name_counts[base_name] > 1:
                name = f"{base_name} {name_counts[base_name]}"
            else:
                name = base_name

            desc = self._generate_description(name, vars_in_cluster, dist_matrix, variable_names)
            subsystems.append(Subsystem(name=name, variables=vars_in_cluster, description=desc))

        # Sort subsystems by name to keep order deterministic
        subsystems.sort(key=lambda s: s.name)
        return subsystems

    # ------------------------------------------------------------------

    def _build_distance_matrix(
        self,
        variable_names: list[str],
        relationships: list[Any],
        findings: list[Any],
        df: pd.DataFrame | None = None,
    ) -> np.ndarray:
        """Construct a symmetric distance matrix between all variables."""
        n_vars = len(variable_names)
        dist_matrix = np.ones((n_vars, n_vars))
        np.fill_diagonal(dist_matrix, 0.0)
        
        var_to_idx = {name: i for i, name in enumerate(variable_names)}

        # Option A: Compute correlation from raw DataFrame
        if df is not None:
            # Subset only requested variables that exist in df
            existing_vars = [v for v in variable_names if v in df.columns]
            if len(existing_vars) > 1:
                corr = df[existing_vars].corr().abs().fillna(0.0).values
                # Map back to dist_matrix
                for i, v_i in enumerate(existing_vars):
                    for j, v_j in enumerate(existing_vars):
                        idx_i = var_to_idx[v_i]
                        idx_j = var_to_idx[v_j]
                        dist_matrix[idx_i, idx_j] = np.clip(1.0 - corr[i, j], 0.0, 1.0)
                return dist_matrix

        # Option B: Use pearson correlation findings
        for f in findings:
            if getattr(f, "method", "") in ("pearson", "spearman") and len(f.variables) == 2:
                v1, v2 = f.variables[0], f.variables[1]
                if v1 in var_to_idx and v2 in var_to_idx:
                    idx1, idx2 = var_to_idx[v1], var_to_idx[v2]
                    # Map correlation to [0, 1] distance
                    val = np.clip(1.0 - abs(f.metric_value), 0.0, 1.0)
                    dist_matrix[idx1, idx2] = val
                    dist_matrix[idx2, idx1] = val

        # Option C: Use general relationship confidences as fallback
        for r in relationships:
            v1, v2 = r.source, r.target
            if v1 in var_to_idx and v2 in var_to_idx:
                idx1, idx2 = var_to_idx[v1], var_to_idx[v2]
                val = np.clip(1.0 - r.confidence, 0.0, 1.0)
                # Keep the minimum distance if multiple relationships exist
                dist_matrix[idx1, idx2] = min(dist_matrix[idx1, idx2], val)
                dist_matrix[idx2, idx1] = min(dist_matrix[idx2, idx1], val)

        return dist_matrix

    def _name_cluster(self, vars_in_cluster: list[str]) -> str:
        """Categorize a list of variables using keywords and return a subsystem name."""
        keywords = {
            "Thermal Subsystem": ["temp", "temperature", "thermal", "heat", "cool", "degc", "degf", "celsius", "kelvin"],
            "Power Subsystem": ["volt", "voltage", "curr", "current", "batt", "battery", "power", "amp", "energy", "draw"],
            "Actuation Subsystem": ["speed", "rpm", "velocity", "mot", "motor", "rot", "rotor", "thrust", "spin"],
            "Attitude & Control Subsystem": ["pitch", "roll", "yaw", "att", "attitude", "gyro", "acc", "accel", "angle"],
            "Navigation Subsystem": ["pos", "position", "alt", "altitude", "lat", "lon", "gps", "nav", "navigation"],
            "Communication Subsystem": ["comm", "signal", "rssi", "packet", "telemetry", "link", "tx", "rx"],
            "Health & Diagnostics Subsystem": ["err", "error", "fail", "status", "health", "warn", "warning", "fault"],
        }

        scores = {category: 0 for category in keywords}
        for var in vars_in_cluster:
            v_lower = var.lower()
            for category, keys in keywords.items():
                if any(k in v_lower for k in keys):
                    scores[category] += 1

        best_category = max(scores, key=scores.get) # type: ignore
        if scores[best_category] > 0:
            return best_category

        # Fallback: Name it after the first variable
        return f"{vars_in_cluster[0].capitalize()} Subsystem"

    def _generate_description(
        self,
        name: str,
        vars_in_cluster: list[str],
        dist_matrix: np.ndarray,
        variable_names: list[str],
    ) -> str:
        """Produce a human-readable summary of the subsystem's contents."""
        var_list_str = ", ".join(vars_in_cluster)
        
        # Calculate coherence (average intra-cluster similarity)
        var_to_idx = {name: i for i, name in enumerate(variable_names)}
        indices = [var_to_idx[v] for v in vars_in_cluster]
        
        if len(vars_in_cluster) > 1:
            sub_dist = dist_matrix[np.ix_(indices, indices)]
            # Average distance excluding diagonal
            n = len(vars_in_cluster)
            avg_dist = np.sum(sub_dist) / (n * (n - 1))
            coherence = 1.0 - avg_dist
            coherence_str = f"high coherence ({coherence:.2f} similarity)" if coherence > 0.6 else f"moderate coherence ({coherence:.2f} similarity)"
        else:
            coherence_str = "single-variable component"

        return (
            f"The {name} is a discovered logical component responsible for "
            f"monitoring the behavior of: {var_list_str}. It is characterized as a "
            f"{coherence_str} based on observational telemetry correlation."
        )
