"""
OMS Influence and Feedback Discovery.

Traces causal pathways (influence chains) and detects reinforcing/balancing feedback loops.
"""

from __future__ import annotations

import logging
from typing import Any
import networkx as nx

from .config import OMSConfig
from .models import InfluenceChain, FeedbackLoop

logger = logging.getLogger(__name__)


class InfluenceAnalyzer:
    """Analyzes the relationship graph to trace influence chains and feedback loops."""

    def __init__(self, config: OMSConfig) -> None:
        self.config = config

    def analyze(
        self,
        variable_names: list[str],
        relationships: list[Any],
        findings: list[Any],
    ) -> tuple[list[InfluenceChain], list[FeedbackLoop]]:
        """Run graph analysis on relationships.

        Parameters:
            variable_names: All variables.
            relationships: Level-2 relationships.
            findings: Level-1 findings.

        Returns:
            A tuple of (influence_chains, feedback_loops).
        """
        # 1. Build directed graph of relationships
        G = nx.DiGraph()
        G.add_nodes_from(variable_names)

        # Map relation types to weight/confidence
        valid_types = {"influences", "triggers", "threshold"}
        
        # Keep track of edge signs for feedback loop analysis
        # Key: (source, target), Value: sign (+1 or -1)
        edge_signs: dict[tuple[str, str], int] = {}
        
        # Map pair -> correlation sign
        corr_signs: dict[tuple[str, str], int] = {}
        for f in findings:
            if getattr(f, "method", "") in ("pearson", "spearman") and len(f.variables) == 2:
                v1, v2 = f.variables[0], f.variables[1]
                sign = 1 if f.metric_value >= 0 else -1
                corr_signs[(v1, v2)] = sign
                corr_signs[(v2, v1)] = sign

        for r in relationships:
            rtype = getattr(r.relation_type, "value", str(r.relation_type))
            if rtype in valid_types:
                if r.confidence >= self.config.min_influence_confidence:
                    G.add_edge(
                        r.source,
                        r.target,
                        confidence=r.confidence,
                        lag=r.estimated_lag,
                        relation_type=rtype,
                    )
                    
                    # Determine sign
                    sign = 1
                    # Try correlation sign first
                    if (r.source, r.target) in corr_signs:
                        sign = corr_signs[(r.source, r.target)]
                    # Or check metadata description for "decrease"
                    desc = r.metadata.get("description", "").lower()
                    if "decrease" in desc or "negative" in desc:
                        sign = -1
                    edge_signs[(r.source, r.target)] = sign

        # 2. Trace Influence Chains
        influence_chains = self._find_influence_chains(G)

        # 3. Detect Feedback Loops
        feedback_loops = self._find_feedback_loops(G, edge_signs)

        return influence_chains, feedback_loops

    # ------------------------------------------------------------------

    def _find_influence_chains(self, G: nx.DiGraph) -> list[InfluenceChain]:
        """Find all significant simple paths in the directed causal graph."""
        chains: list[InfluenceChain] = []
        
        # Find all sources (in-degree=0) and leaves (out-degree=0)
        sources = [n for n in G.nodes if G.in_degree(n) == 0 and G.out_degree(n) > 0]
        leaves = [n for n in G.nodes if G.out_degree(n) == 0 and G.in_degree(n) > 0]

        # If there are no strict sources or leaves (due to cycles), use all nodes
        if not sources:
            sources = [n for n in G.nodes if G.out_degree(n) > 0]
        if not leaves:
            leaves = [n for n in G.nodes if G.in_degree(n) > 0]

        visited_paths = set()

        for src in sources:
            for leaf in leaves:
                if src == leaf:
                    continue
                try:
                    paths = nx.all_simple_paths(G, src, leaf, cutoff=4)
                    for path in paths:
                        path_tuple = tuple(path)
                        if path_tuple in visited_paths:
                            continue
                        visited_paths.add(path_tuple)

                        # Extract step details
                        lags = []
                        confidences = []
                        rtypes = []
                        for i in range(len(path) - 1):
                            u, v = path[i], path[i + 1]
                            edge_data = G[u][v]
                            lags.append(edge_data["lag"])
                            confidences.append(edge_data["confidence"])
                            rtypes.append(edge_data["relation_type"])

                        # Overall chain metrics
                        cum_lag = sum(lags)
                        # Overall confidence is the bottleneck (min confidence)
                        chain_conf = min(confidences) if confidences else 0.0

                        chains.append(
                            InfluenceChain(
                                variables=path,
                                lags=lags,
                                cumulative_lag=cum_lag,
                                confidence=chain_conf,
                                relation_types=rtypes,
                            )
                        )
                except nx.NetworkXNoPath:
                    continue

        # Sort: prefer longer chains first, then higher confidence
        chains.sort(key=lambda c: (-len(c.variables), -c.confidence))
        
        # De-duplicate: filter out subchains of longer, higher-confidence chains
        unique_chains: list[InfluenceChain] = []
        for c in chains:
            # Check if this chain is a subsegment of any already accepted chain
            is_subsegment = False
            for accepted in unique_chains:
                # If path c.variables is a sublist of accepted.variables
                accepted_vars = accepted.variables
                sub_len = len(c.variables)
                for i in range(len(accepted_vars) - sub_len + 1):
                    if accepted_vars[i : i + sub_len] == c.variables:
                        is_subsegment = True
                        break
                if is_subsegment:
                    break
            
            if not is_subsegment:
                unique_chains.append(c)

        return unique_chains[:12]  # Cap at top 12 chains

    def _find_feedback_loops(
        self, G: nx.DiGraph, edge_signs: dict[tuple[str, str], int]
    ) -> list[FeedbackLoop]:
        """Identify feedback cycles and label them as positive or negative."""
        loops: list[FeedbackLoop] = []
        
        try:
            cycles = list(nx.simple_cycles(G))
        except Exception as e:
            logger.warning(f"Cycle detection failed: {e}")
            return []

        # Standardize cycles to avoid reporting rotations of the same cycle
        seen_cycles = set()
        
        for cycle in cycles:
            if len(cycle) < 2:
                continue
            
            # Sort cycle representations to prevent duplicates (rotations)
            # Find the minimum element and rotate cycle to start with it
            min_val = min(cycle)
            min_idx = cycle.index(min_val)
            normalized_cycle = cycle[min_idx:] + cycle[:min_idx]
            cycle_key = tuple(normalized_cycle)
            
            if cycle_key in seen_cycles:
                continue
            seen_cycles.add(cycle_key)

            # Build full path including return step
            full_cycle = normalized_cycle + [normalized_cycle[0]]

            # Compute loop attributes
            confidences = []
            signs = []
            
            for i in range(len(full_cycle) - 1):
                u, v = full_cycle[i], full_cycle[i + 1]
                edge_data = G[u][v]
                confidences.append(edge_data["confidence"])
                
                # Fetch sign
                sign = edge_signs.get((u, v), 1)
                signs.append(sign)

            avg_conf = sum(confidences) / len(confidences)
            
            # Multiply signs: product > 0 is positive (reinforcing), product < 0 is negative (balancing)
            loop_sign = 1
            for s in signs:
                loop_sign *= s
                
            loop_type = "positive" if loop_sign > 0 else "negative"
            
            # Human readable description
            cycle_str = " ──► ".join(full_cycle)
            if loop_type == "positive":
                desc = (
                    f"Reinforcing (Positive) feedback loop detected: {cycle_str}. "
                    "An increase in one variable cascades to further increase itself, "
                    "which may trigger system runaways or operational mode shifts."
                )
            else:
                desc = (
                    f"Self-regulating (Negative) feedback loop detected: {cycle_str}. "
                    "The feedback acts to counteract changes, stabilizing the variables "
                    "around an equilibrium value."
                )

            loops.append(
                FeedbackLoop(
                    variables=full_cycle,
                    loop_type=loop_type,
                    confidence=avg_conf,
                    description=desc,
                )
            )

        loops.sort(key=lambda l: -l.confidence)
        return loops
