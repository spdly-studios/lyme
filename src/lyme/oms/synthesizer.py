"""
OMS Synthesizer.

Main orchestration module for the Operational Model Synthesizer (OMS).
Synthesizes the multi-level OperationalTheory from KSE outputs.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd

from .config import OMSConfig
from .models import OperationalTheory, StateMachine
from .subsystem import SubsystemDiscoverer
from .influence import InfluenceAnalyzer
from .state_machine import StateMachineSynthesizer
from .equations import EquationDeriver

logger = logging.getLogger(__name__)


class OperationalModelSynthesizer:
    """Orchestrates the synthesis of an interpretable system operational model."""

    def __init__(self, config: OMSConfig | None = None) -> None:
        self.config = config or OMSConfig()
        self.subsystem_discoverer = SubsystemDiscoverer(self.config)
        self.influence_analyzer = InfluenceAnalyzer(self.config)
        self.state_machine_synthesizer = StateMachineSynthesizer(self.config)
        self.equation_deriver = EquationDeriver(self.config)

    def synthesize(
        self,
        model: Any,
        df: pd.DataFrame | None = None,
        mode_labels: list[int] | None = None,
    ) -> OperationalTheory:
        """Run the full synthesis pipeline on the KSE SystemModel.

        Parameters:
            model: The KSE SystemModel object.
            df: Optional aligned state matrix DataFrame from Component 1.
            mode_labels: Optional list of mode labels for each row in df.

        Returns:
            The compiled OperationalTheory containing the unified system model.
        """
        if self.config.verbose:
            print("[*] Starting Operational Model Synthesis (OMS)...")

        # Extract variables
        vars_all = list(model.variable_names)

        # 1. Consolidate redundant variables
        consolidated, vars_filtered, alias_map = self._consolidate_variables(vars_all, model)

        # Filter the dataframe columns if df is provided
        df_filtered = None
        if df is not None:
            df_filtered = df.copy()
            # Map alias columns to canonical names by taking the average or canonical values
            for canonical, aliases in consolidated.items():
                for alias in aliases:
                    if alias in df_filtered.columns and canonical in df_filtered.columns:
                        # Drop alias to avoid redundancy
                        df_filtered = df_filtered.drop(columns=[alias])
        else:
            df_filtered = None

        # Reconstruct mode_labels if df is provided and labels are missing
        if df_filtered is not None and mode_labels is None and model.modes:
            mode_labels = self._reconstruct_mode_labels(df_filtered, model.modes)

        # 2. Build Subsystem Structure
        subsystems = self.subsystem_discoverer.discover(
            variable_names=vars_filtered,
            relationships=model.relationships,
            findings=model.findings,
            df=df_filtered,
        )

        # 3. Build Influence Chains and Feedback Loops
        influence_chains, feedback_loops = self.influence_analyzer.analyze(
            variable_names=vars_filtered,
            relationships=model.relationships,
            findings=model.findings,
        )

        # 4. Synthesize State Machine
        state_machine = self.state_machine_synthesizer.synthesize(
            modes=model.modes,
            transitions=model.mode_transitions,
            df=df_filtered,
            mode_labels=mode_labels,
        )

        # 5. Derive Mathematical Models
        equations = self.equation_deriver.derive_equations(
            variable_names=vars_filtered,
            relationships=model.relationships,
            modes=model.modes,
            df=df_filtered,
        )

        # 6. Resolve Contradictions
        resolved_contradictions = self._resolve_contradictions(model)

        # 7. Generate Natural Language Explanations
        explanations = self._generate_explanations(
            subsystems, influence_chains, feedback_loops, state_machine, equations
        )

        # Compile and return OperationalTheory
        theory = OperationalTheory(
            variable_names=vars_filtered,
            consolidated_variables=consolidated,
            subsystems=subsystems,
            influence_chains=influence_chains,
            feedback_loops=feedback_loops,
            state_machine=state_machine,
            equations=equations,
            explanations=explanations,
            resolved_contradictions=resolved_contradictions,
            metadata={
                "timestamp_count": model.timestamp_count,
                "original_variable_count": len(vars_all),
                "consolidated_variable_count": len(vars_filtered),
            },
        )

        if self.config.verbose:
            print("[+] Operational Model Synthesis complete!")
            print(f"    - Subsystems: {len(theory.subsystems)}")
            # Filter unique chains for print summary
            print(f"    - Causal Chains: {len(theory.influence_chains)}")
            print(f"    - Feedback Loops: {len(theory.feedback_loops)}")
            print(f"    - Math Equations: {len(theory.equations)}")
            print(f"    - Resolved Contradictions: {len(theory.resolved_contradictions)}")

        return theory

    # ------------------------------------------------------------------

    def _consolidate_variables(
        self, variables: list[str], model: Any
    ) -> tuple[dict[str, list[str]], list[str], dict[str, str]]:
        """Deduplicate/merge variables with very high correlation and name similarity."""
        consolidated: dict[str, list[str]] = {}
        merged_aliases = set()
        alias_map = {}

        # Scan Level 1 findings for pearson correlation
        for f in model.findings:
            method = getattr(f, "method", "")
            if method in ("pearson", "spearman") and len(f.variables) == 2:
                v1, v2 = f.variables[0], f.variables[1]
                if v1 in merged_aliases or v2 in merged_aliases:
                    continue

                # Threshold correlation coefficient at 0.98
                if abs(f.metric_value) >= 0.98:
                    s1, s2 = v1.lower(), v2.lower()
                    
                    # Basic name similarity: sharing prefix or substring
                    common_prefix = s1[:4] == s2[:4]
                    substring_match = (s1 in s2) or (s2 in s1)
                    
                    if common_prefix or substring_match:
                        # Pick shorter name as canonical variable representation
                        canonical = v1 if len(v1) <= len(v2) else v2
                        alias = v2 if canonical == v1 else v1
                        
                        consolidated.setdefault(canonical, []).append(alias)
                        merged_aliases.add(alias)
                        alias_map[alias] = canonical

        # Compute filtered variable list
        vars_filtered = [v for v in variables if v not in merged_aliases]
        return consolidated, vars_filtered, alias_map

    def _reconstruct_mode_labels(self, df: pd.DataFrame, modes: list[Any]) -> list[int]:
        """Map each state row to the closest operational mode cluster centroid."""
        labels = []
        for _, row in df.iterrows():
            best_lbl = 0
            min_dist = float("inf")
            for m in modes:
                dist = 0.0
                for var, centroid_val in m.centroid.items():
                    if var in row and pd.notna(row[var]):
                        dist += (row[var] - centroid_val) ** 2
                if dist < min_dist:
                    min_dist = dist
                    
                    # Extract numeric index if label is e.g. "Mode_0"
                    lbl_str = m.label
                    try:
                        lbl_idx = int(lbl_str.split("_")[-1])
                    except Exception:
                        lbl_idx = 0
                    best_lbl = lbl_idx
            labels.append(best_lbl)
        return labels

    def _resolve_contradictions(self, model: Any) -> list[dict[str, Any]]:
        """Scans contradictions and resolves them by comparing confidence scores."""
        resolved = []
        
        # Build maps for looking up confidences of findings, relationships, rules
        item_confidences: dict[str, float] = {}
        for f in model.findings:
            item_confidences[f.description] = f.confidence
        for r in model.relationships:
            desc = r.metadata.get("description", "")
            if desc:
                item_confidences[desc] = r.confidence
        for ru in model.rules:
            item_confidences[ru.to_text()] = ru.confidence
            
        for c in model.contradictions:
            desc_a = c.finding_a
            desc_b = c.finding_b
            
            # Look up confidences
            conf_a = 0.5
            conf_b = 0.5
            for desc, conf in item_confidences.items():
                if desc_a in desc or desc in desc_a:
                    conf_a = conf
                if desc_b in desc or desc in desc_b:
                    conf_b = conf

            # Determine winner
            if conf_a >= conf_b:
                primary_exp = desc_a
                rejected_exp = desc_b
                delta = conf_a - conf_b
            else:
                primary_exp = desc_b
                rejected_exp = desc_a
                delta = conf_b - conf_a

            resolved.append(
                {
                    "conflict_description": c.description,
                    "primary_explanation": primary_exp,
                    "rejected_explanation": rejected_exp,
                    "confidence_delta": delta,
                    "resolution_rationale": (
                        "Primary explanation selected due to stronger empirical confidence score "
                        f"({max(conf_a, conf_b):.2f} vs {min(conf_a, conf_b):.2f})."
                    ),
                }
            )
        return resolved

    def _generate_explanations(
        self,
        subsystems: list[Any],
        chains: list[Any],
        loops: list[Any],
        state_machine: StateMachine,
        equations: list[Any],
    ) -> list[str]:
        """Generate engineer-readable paragraphs summarizing system dynamics."""
        paragraphs = []

        # 1. Introduction
        sub_list = ", ".join(s.name for s in subsystems)
        intro = (
            f"The analyzed system has been automatically synthesized into {len(subsystems)} "
            f"primary functional subsystems: {sub_list}. This grouping separates the telemetry "
            "variables into highly coherent clusters that represent distinct thermal, power, "
            "or actuation domains."
        )
        paragraphs.append(intro)

        # 2. Causal Dynamics
        if chains:
            primary_chain = chains[0]
            chain_text = " -> ".join(primary_chain.variables)
            causal = (
                f"Causal analysis reveals significant influence pathways. The dominant influence pathway "
                f"traced is: {chain_text}. This indicating that changes in the root variable propagate "
                f"through intermediate states to affect the system with a cumulative lag of "
                f"{primary_chain.cumulative_lag:.2f} seconds."
            )
            paragraphs.append(causal)

        # 3. Feedback Loop Summary
        if loops:
            pos_loops = [l for l in loops if l.loop_type == "positive"]
            neg_loops = [l for l in loops if l.loop_type == "negative"]
            
            feedback_desc = "System stability is moderated by feedback loops. "
            if pos_loops:
                feedback_desc += (
                    f"We discovered {len(pos_loops)} reinforcing (positive) feedback structure(s) "
                    f"involving: {', '.join(pos_loops[0].variables[:-1])}. This loop can lead to "
                    "thermal runaway or rapid operational transitions. "
                )
            if neg_loops:
                feedback_desc += (
                    f"We also identified {len(neg_loops)} balancing (negative) feedback structure(s) "
                    "which act as stabilizing regulators for system dynamics."
                )
            paragraphs.append(feedback_desc)

        # 4. State Machine Summary
        if state_machine.states:
            names = [s.name for s in state_machine.states]
            most_prev = max(state_machine.states, key=lambda s: s.prevalence)
            state_desc = (
                f"The system exhibits {len(state_machine.states)} main behavioral operational states: "
                f"{', '.join(names)}. The system spends the majority of its time ({most_prev.prevalence * 100:.1f}%) "
                f"in the {most_prev.name}. Transitions between these states are regulated by specific trigger rules "
                "discovered from behavioral transitions."
            )
            paragraphs.append(state_desc)

        # 5. Equation summary
        if equations:
            eq_examples = [eq.equation_str for eq in equations[:2]]
            eq_desc = (
                "Empirical mathematical models have been fitted to represent the numerical dynamics. "
                f"Key physical couplings are represented by the following derived equations: "
                f"{'; '.join(eq_examples)}."
            )
            paragraphs.append(eq_desc)

        return paragraphs
