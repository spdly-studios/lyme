"""
OMS Exporters.

Exports the synthesized OperationalTheory to:
1. A human-readable Markdown report.
2. A standalone, runnable Python Digital Twin simulation script.
3. A machine-readable JSON structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import OperationalTheory


class MarkdownTheoryExporter:
    """Exports the synthesized theory to a formatted Markdown report."""

    def export(self, theory: OperationalTheory, filepath: Path) -> None:
        """Export the operational theory to a Markdown file.

        Parameters:
            theory: The synthesized OperationalTheory object.
            filepath: Path to save the markdown report.
        """
        lines = []
        lines.append("# Lyme - Operational Model Synthesizer (OMS) Report")
        lines.append(f"**Synthesized System Operational Theory**")
        lines.append("")
        
        # Section 1: Executive Natural Language Summary
        lines.append("## 1. Executive Summary")
        lines.append("")
        for exp in theory.explanations:
            lines.append(exp)
            lines.append("")

        # Section 2: Variable Consolidation
        if theory.consolidated_variables:
            lines.append("## 2. Variable Consolidation")
            lines.append("Identified and merged redundant variables representing duplicate concept observations.")
            lines.append("")
            lines.append("| Canonical Variable | Consolidated Aliases / Redundant Variables |")
            lines.append("| :--- | :--- |")
            for canonical, aliases in theory.consolidated_variables.items():
                lines.append(f"| `{canonical}` | {', '.join(f'`{a}`' for a in aliases)} |")
            lines.append("")

        # Section 3: Subsystem Hierarchy
        lines.append("## 3. Subsystem Hierarchy")
        lines.append("Discovered physical and functional groupings of variables based on correlation clusters.")
        lines.append("")
        for sub in theory.subsystems:
            lines.append(f"### 📦 Subsystem: {sub.name}")
            lines.append(f"- **Description:** {sub.description}")
            lines.append(f"- **Monitored Variables:** {', '.join(f'`{v}`' for v in sub.variables)}")
            lines.append("")
        lines.append("---")

        # Section 4: Causal Influence Chains
        lines.append("## 4. Causal Influence Chains")
        lines.append("Traced causal pathways of directed influence showing how inputs propagate through variables.")
        lines.append("")
        if theory.influence_chains:
            lines.append("| Causal Influence Chain | Cumulative Lag | Bottleneck Confidence |")
            lines.append("| :--- | :--- | :--- |")
            for chain in theory.influence_chains:
                lines.append(
                    f"| {chain.to_text()} | {chain.cumulative_lag:.2f} | {chain.confidence:.3f} |"
                )
        else:
            lines.append("*No significant multi-step influence chains detected.*")
        lines.append("")

        # Section 5: Feedback Loops
        lines.append("## 5. Feedback Loops")
        lines.append("Discovered feedback structures that regulate or amplify system dynamics.")
        lines.append("")
        for loop in theory.feedback_loops:
            badge = "🔄 Reinforcing (Positive)" if loop.loop_type == "positive" else "⚖️ Balancing (Negative)"
            lines.append(f"### {badge} Loop (Confidence: {loop.confidence:.2f})")
            lines.append(f"- **Loop Path:** {' ──► '.join(f'`{v}`' for v in loop.variables)}")
            lines.append(f"- **Behavioral Effect:** {loop.description}")
            lines.append("")
        if not theory.feedback_loops:
            lines.append("*No feedback loops identified.*")
            lines.append("")
        lines.append("---")

        # Section 6: Operational States & Transitions (State Machine)
        lines.append("## 6. Operational State Machine")
        lines.append("System operational states and transition dynamics discovered from behavior clustering.")
        lines.append("")
        
        lines.append("### Discovered States")
        lines.append("")
        for s in theory.state_machine.states:
            lines.append(f"#### ❖ {s.name} (`{s.original_label}`)")
            lines.append(f"- **Description:** {s.description}")
            lines.append(f"- **Prevalence (Time Spent):** {s.prevalence * 100:.1f}%")
            lines.append("- **Centroid values:**")
            centroid_lines = []
            for var, val in s.centroid.items():
                centroid_lines.append(f"`{var}`: {val:.4g}")
            lines.append(f"  {', '.join(centroid_lines)}")
            lines.append("")

        lines.append("### Transitions & Triggers")
        lines.append("")
        lines.append("| Source State | Target State | Probability | Trigger Condition |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for t in theory.state_machine.transitions:
            lines.append(
                f"| {t['from_name']} | {t['to_name']} | {t['probability'] * 100:.1f}% | `{t['trigger_rule']}` |"
            )
        lines.append("")

        if theory.state_machine.mermaid_diagram:
            lines.append("### State Transition Diagram")
            lines.append("```mermaid")
            lines.append(theory.state_machine.mermaid_diagram)
            lines.append("```")
            lines.append("")

        # Section 7: Mathematical Model Equations
        lines.append("## 7. Derived Mathematical Equations")
        lines.append("Derived empirical equations mapping relationships with lag shifting.")
        lines.append("")
        if theory.equations:
            lines.append("| Variable Model | R-Squared | Residual MSE | Model Type |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for eq in theory.equations:
                eq_type = "Polynomial (Degree 2)" if eq.is_polynomial else "Linear / Multiple Linear"
                lines.append(
                    f"| `{eq.equation_str}` | {eq.r2:.3f} | {eq.mse:.4g} | {eq_type} |"
                )
        else:
            lines.append("*No mathematical equations met confidence thresholds.*")
        lines.append("")

        # Section 8: Contradiction Resolution
        lines.append("## 8. Contradiction Resolution")
        lines.append("Reconciled conflicting observations or competing causal hypotheses.")
        lines.append("")
        for c in theory.resolved_contradictions:
            lines.append(f"> [!WARNING]")
            lines.append(f"> **Conflict:** {c['conflict_description']}")
            lines.append(f"> - **Selected Primary Theory:** {c['primary_explanation']}")
            lines.append(f"> - **Rejected Alternative Hypothesis:** {c['rejected_explanation']}")
            lines.append(f"> - **Resolution Rationale:** {c['resolution_rationale']} (Confidence delta = {c['confidence_delta']:.2f})")
            lines.append("")
        if not theory.resolved_contradictions:
            lines.append("*No data contradictions required reconciliation.*")
            lines.append("")

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


class DigitalTwinPythonExporter:
    """Exports the executable Digital Twin simulator to a standalone Python script."""

    def export(self, theory: OperationalTheory, filepath: Path) -> None:
        """Export standalone Python file.

        Parameters:
            theory: The synthesized OperationalTheory object.
            filepath: Path to save the python code.
        """
        def sanitize_numpy(val: Any) -> Any:
            import numpy as np
            if isinstance(val, dict):
                return {k: sanitize_numpy(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [sanitize_numpy(v) for v in val]
            elif isinstance(val, (np.floating, float)):
                return float(val) if not np.isnan(val) else 0.0
            elif isinstance(val, (np.integer, int)):
                return int(val)
            return val

        # Prepare structures for serialization
        eqs_serialized = []
        for eq in theory.equations:
            eqs_serialized.append(
                {
                    "target_variable": eq.target_variable,
                    "intercept": eq.intercept,
                    "coefficients": eq.coefficients,
                    "is_polynomial": eq.is_polynomial,
                    "lag_steps": eq.lag_steps,
                }
            )

        states_serialized = []
        for s in theory.state_machine.states:
            states_serialized.append(
                {
                    "original_label": s.original_label,
                    "name": s.name,
                    "centroid": s.centroid,
                }
            )

        transitions_serialized = []
        for t in theory.state_machine.transitions:
            transitions_serialized.append(
                {
                    "from_mode": t["from_mode"],
                    "to_mode": t["to_mode"],
                    "probability": t["probability"],
                    "trigger_rule": t["trigger_rule"],
                }
            )

        eqs_serialized = sanitize_numpy(eqs_serialized)
        states_serialized = sanitize_numpy(states_serialized)
        transitions_serialized = sanitize_numpy(transitions_serialized)

        # Code template
        code = f"""#!/usr/bin/env python3
\"\"\"
Lyme - Standalone Digital Twin Model.

THIS FILE WAS AUTOMATICALLY GENERATED BY THE OPERATIONAL MODEL SYNTHESIZER (OMS).
Contains an executable simulation of the synthesized system.
\"\"\"

import sys
import time

class DigitalTwin:
    \"\"\"An executable simulation of the synthesized system model.

    Maintains variables, history buffers for lagged relationships, evaluates
    equations, and updates operational state transitions.
    \"\"\"

    # Serialized structures from synthesis
    VARIABLE_NAMES = {repr(theory.variable_names)}
    EQUATIONS = {repr(eqs_serialized)}
    STATES = {repr(states_serialized)}
    TRANSITIONS = {repr(transitions_serialized)}

    def __init__(self, initial_state_label=None):
        self.variable_names = self.VARIABLE_NAMES
        self.equations = self.EQUATIONS
        
        # Build maps for evaluation
        self.equations_map = {{eq["target_variable"]: eq for eq in self.equations}}
        
        # Determine max history needed
        self.max_lag_steps = 0
        for eq in self.equations:
            for parent, lag in eq["lag_steps"].items():
                self.max_lag_steps = max(self.max_lag_steps, lag)

        # Set initial operational mode
        self.current_state_label = initial_state_label
        if not self.current_state_label and self.STATES:
            self.current_state_label = self.STATES[0]["original_label"]

        self.state = {{}}
        self.history = {{}}
        self.reset()

    def reset(self, initial_values=None):
        \"\"\"Reset the simulation state and history buffers.\"\"\"
        self.state = {{}}
        
        # Initialize state with defaults (centroids of current state)
        current_centroid = {{}}
        if self.current_state_label:
            for s in self.STATES:
                if s["original_label"] == self.current_state_label:
                    current_centroid = s["centroid"]
                    break

        for var in self.variable_names:
            if initial_values and var in initial_values:
                self.state[var] = initial_values[var]
            else:
                self.state[var] = current_centroid.get(var, 0.0)

        # Reset history
        self.history = {{var: [self.state[var]] for var in self.variable_names}}

    def step(self, inputs):
        \"\"\"Perform a single simulation step.

        Parameters:
            inputs: Dict of exogenous control variables (e.g. motor_speed).

        Returns:
            The updated system state dictionary.
        \"\"\"
        # 1. Update exogenous inputs in state
        for var, val in inputs.items():
            if var in self.state:
                self.state[var] = val

        # 2. Maintain history buffers
        for var in self.variable_names:
            self.history.setdefault(var, []).append(self.state[var])
            if len(self.history[var]) > self.max_lag_steps + 1:
                self.history[var].pop(0)

        # 3. Evaluate equations to update endogenous variables
        next_state = self.state.copy()

        for target, eq in self.equations_map.items():
            if target in inputs:
                continue
            val = eq["intercept"]
            
            if eq["is_polynomial"]:
                # Polynomial model
                for term, coeff in eq["coefficients"].items():
                    if term.endswith("^2"):
                        base = term[:-2]
                        lag = eq["lag_steps"].get(base, 0)
                        x_val = self._get_historical_value(base, lag)
                        val += coeff * (x_val ** 2)
                    else:
                        lag = eq["lag_steps"].get(term, 0)
                        x_val = self._get_historical_value(term, lag)
                        val += coeff * x_val
            else:
                # Multiple linear model
                for predictor, coeff in eq["coefficients"].items():
                    lag = eq["lag_steps"].get(predictor, 0)
                    x_val = self._get_historical_value(predictor, lag)
                    val += coeff * x_val

            next_state[target] = val

        self.state = next_state

        # 4. Check transitions
        if self.current_state_label:
            out_trans = [
                t
                for t in self.TRANSITIONS
                if t["from_mode"] == self.current_state_label
            ]
            
            triggered_transition = None
            max_prob = -1.0
            
            for t in out_trans:
                trigger = t["trigger_rule"]
                if self._evaluate_trigger(trigger):
                    if t["probability"] > max_prob:
                        triggered_transition = t
                        max_prob = t["probability"]

            if triggered_transition:
                self.current_state_label = triggered_transition["to_mode"]

        return self.state.copy()

    def _get_historical_value(self, var, lag_steps):
        buf = self.history.get(var, [])
        if not buf:
            return self.state.get(var, 0.0)
        idx = -1 - lag_steps
        try:
            return buf[idx]
        except IndexError:
            return buf[0] if buf else self.state.get(var, 0.0)

    def _evaluate_trigger(self, trigger_rule):
        if trigger_rule == "N/A" or not trigger_rule:
            return False

        try:
            parts = trigger_rule.split()
            if len(parts) != 3:
                return False

            var, op, threshold_str = parts[0], parts[1], parts[2]
            if var not in self.state:
                return False

            val = self.state[var]
            threshold = float(threshold_str)

            if op == ">":
                return val > threshold
            elif op == ">=":
                return val >= threshold
            elif op == "<":
                return val < threshold
            elif op == "<=":
                return val <= threshold
            elif op == "==":
                return val == threshold
        except Exception:
            pass
        return False


def main():
    print("==================================================")
    print("Initializing digital twin simulator...")
    twin = DigitalTwin()
    print("Variables:", twin.variable_names)
    print("Initial State:", twin.state)
    print("Initial Operational Mode:", twin.current_state_label)
    print("")

    # Run a simple step test
    print("Running 10 step simulation test (accelerating motor speed)...")
    print("-" * 55)
    
    # We will vary motor_speed over time and check current and temp
    for step in range(1, 11):
        # Accelerate speed
        speed = 100.0 + step * 70.0
        inputs = {{"motor_speed": speed}}
        
        # Perform step
        out = twin.step(inputs)
        print(
            f"Step {{step:02d}} | Inputs: Speed={{speed:.1f}} | "
            f"Outputs: Current={{out.get('current_draw', 0.0):.2f}}, "
            f"Temp={{out.get('temp', 0.0):.2f}}, "
            f"Mode={{twin.current_state_label}}"
        )
        time.sleep(0.05)
    
    print("==================================================")
    print("Digital twin simulation completed successfully!")

if __name__ == '__main__':
    main()
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)


class JSONTheoryExporter:
    """Exports the operational theory to JSON format."""

    def export(self, theory: OperationalTheory, filepath: Path) -> None:
        """Export raw theory to a json file.

        Parameters:
            theory: The OperationalTheory object.
            filepath: Path to write JSON structure.
        """
        # Build serializable dictionary
        data = {
            "variable_names": theory.variable_names,
            "consolidated_variables": theory.consolidated_variables,
            "subsystems": [
                {
                    "name": s.name,
                    "variables": s.variables,
                    "description": s.description,
                }
                for s in theory.subsystems
            ],
            "influence_chains": [
                {
                    "variables": c.variables,
                    "lags": c.lags,
                    "cumulative_lag": c.cumulative_lag,
                    "confidence": c.confidence,
                    "relation_types": c.relation_types,
                    "text": c.to_text(),
                }
                for c in theory.influence_chains
            ],
            "feedback_loops": [
                {
                    "variables": l.variables,
                    "loop_type": l.loop_type,
                    "confidence": l.confidence,
                    "description": l.description,
                }
                for l in theory.feedback_loops
            ],
            "state_machine": {
                "states": [
                    {
                        "original_label": s.original_label,
                        "name": s.name,
                        "description": s.description,
                        "prevalence": s.prevalence,
                        "centroid": s.centroid,
                    }
                    for s in theory.state_machine.states
                ],
                "transitions": theory.state_machine.transitions,
                "mermaid_diagram": theory.state_machine.mermaid_diagram,
            },
            "equations": [
                {
                    "target_variable": eq.target_variable,
                    "equation_str": eq.equation_str,
                    "coefficients": eq.coefficients,
                    "intercept": eq.intercept,
                    "r2": eq.r2,
                    "mse": eq.mse,
                    "is_polynomial": eq.is_polynomial,
                    "lag_steps": eq.lag_steps,
                }
                for eq in theory.equations
            ],
            "explanations": theory.explanations,
            "resolved_contradictions": theory.resolved_contradictions,
            "metadata": theory.metadata,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
