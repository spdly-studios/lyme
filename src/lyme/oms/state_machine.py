"""
OMS State Machine Synthesis.

Converts clustering modes and transitions into an interpretable state machine.
Maps modes to semantic names and discovers transition trigger rules from data.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from .config import OMSConfig
from .models import StateMachine, StateSummary

logger = logging.getLogger(__name__)


class StateMachineSynthesizer:
    """Synthesizes a human-readable state machine from operational modes and transitions."""

    def __init__(self, config: OMSConfig) -> None:
        self.config = config

    def synthesize(
        self,
        modes: list[Any],
        transitions: list[Any],
        df: pd.DataFrame | None = None,
        mode_labels: list[int] | None = None,
    ) -> StateMachine:
        """Synthesize the state machine.

        Parameters:
            modes: Level-4 operational modes from KSE.
            transitions: Level-4 transitions from KSE.
            df: Optional aligned state matrix.
            mode_labels: List of mode label indices corresponding to each timestamp in df.

        Returns:
            A compiled StateMachine.
        """
        if not modes:
            return StateMachine()

        # 1. Assign semantic names and generate StateSummaries
        states = self._name_and_summarize_states(modes)
        state_map = {s.original_label: s for s in states}

        # 2. Analyze transitions and discover trigger rules
        synth_transitions = []
        for t in transitions:
            from_lbl = t.from_mode
            to_lbl = t.to_mode
            
            # Find names
            from_name = state_map[from_lbl].name if from_lbl in state_map else from_lbl
            to_name = state_map[to_lbl].name if to_lbl in state_map else to_lbl

            # Discover trigger rule from data if available
            trigger_rule = "N/A"
            if df is not None and mode_labels is not None:
                trigger_rule = self._discover_transition_trigger(
                    from_lbl, to_lbl, df, mode_labels
                )

            synth_transitions.append(
                {
                    "from_mode": from_lbl,
                    "from_name": from_name,
                    "to_mode": to_lbl,
                    "to_name": to_name,
                    "probability": t.probability,
                    "confidence": t.confidence,
                    "count": t.count,
                    "trigger_rule": trigger_rule,
                }
            )

        # 3. Generate Mermaid diagram code
        mermaid_code = self._generate_mermaid(states, synth_transitions)

        return StateMachine(
            states=states,
            transitions=synth_transitions,
            mermaid_diagram=mermaid_code,
        )

    # ------------------------------------------------------------------

    def _name_and_summarize_states(self, modes: list[Any]) -> list[StateSummary]:
        """Map raw mode labels to semantic names using centroid thresholds."""
        summaries = []

        # Find min/max for each variable across all centroids to normalize comparison
        all_vars: set[str] = set()
        for m in modes:
            all_vars.update(m.centroid.keys())

        centroids_by_var: dict[str, list[float]] = {}
        for var in all_vars:
            centroids_by_var[var] = [m.centroid[var] for m in modes if var in m.centroid]

        stats: dict[str, dict[str, float]] = {}
        for var, vals in centroids_by_var.items():
            if vals:
                stats[var] = {
                    "min": min(vals),
                    "max": max(vals),
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)) if len(vals) > 1 else 1.0,
                }

        for m in modes:
            label = m.label
            centroid = m.centroid
            
            # Check variable characteristics
            char_tags = []
            
            # Specific domain-heuristics for common spacecraft/system telemetry
            is_idle = False
            is_thermal_stress = False
            is_low_power = False
            is_high_load = False
            is_nominal = True

            # Threshold indicators
            for var, val in centroid.items():
                if var not in stats:
                    continue
                var_min = stats[var]["min"]
                var_max = stats[var]["max"]
                var_range = var_max - var_min
                if var_range == 0:
                    continue

                rel_val = (val - var_min) / var_range

                # Flag high/low values
                if rel_val >= 0.75:
                    char_tags.append(f"high_{var}")
                elif rel_val <= 0.25:
                    char_tags.append(f"low_{var}")

            # Match criteria
            if any("high_temp" in tag or "high_temperature" in tag for tag in char_tags):
                is_thermal_stress = True
                is_nominal = False
            if any("low_battery" in tag or "low_voltage" in tag or "low_battery_voltage" in tag for tag in char_tags):
                is_low_power = True
                is_nominal = False
            if any("low_motor_speed" in tag or "low_speed" in tag or "low_current_draw" in tag for tag in char_tags):
                # If everything is low, it's idle
                idle_signals = [tag for tag in char_tags if "low_" in tag]
                if len(idle_signals) >= len(centroid) * 0.5:
                    is_idle = True
                    is_nominal = False
            if any("high_motor_speed" in tag or "high_speed" in tag or "high_current_draw" in tag for tag in char_tags):
                is_high_load = True
                is_nominal = False

            # Assign semantic name
            if is_idle:
                name = "Idle State"
                desc = "The system is in a standby or low-power quiescent state with minimal actuation."
            elif is_thermal_stress:
                name = "Thermal Stress State"
                desc = "The system is experiencing elevated temperatures, likely due to prolonged high actuation."
            elif is_low_power:
                name = "Low Power / Critical State"
                desc = "The system battery voltage is depleted, representing a low-power constraint."
            elif is_high_load:
                name = "High-Load Operational State"
                desc = "The system is executing high-intensity operations with elevated current draw and speeds."
            elif is_nominal:
                name = "Nominal Operational State"
                desc = "The system is operating under standard nominal parameters with expected margins."
            else:
                # Fallback: Name based on distinguishing features
                features = m.distinguishing_features
                if features:
                    main_feat = features[0]
                    centroid_val = centroid.get(main_feat, 0.0)
                    feat_min = stats[main_feat]["min"]
                    feat_max = stats[main_feat]["max"]
                    is_feat_high = centroid_val > (feat_min + 0.5 * (feat_max - feat_min))
                    name = f"{'High' if is_feat_high else 'Low'} {main_feat.replace('_', ' ').title()} State"
                else:
                    name = f"State {label}"
                desc = f"Operational state characterized by: {m.description}"

            summaries.append(
                StateSummary(
                    original_label=label,
                    name=name,
                    description=desc,
                    prevalence=m.prevalence,
                    centroid=centroid,
                    distinguishing_features=m.distinguishing_features,
                )
            )

        # Ensure order matches inputs
        return summaries

    def _discover_transition_trigger(
        self, from_mode: str, to_mode: str, df: pd.DataFrame, mode_labels: list[int]
    ) -> str:
        """Find the variable threshold that triggers a transition from from_mode to to_mode."""
        # Convert labels to string array for matching
        labels = np.array(mode_labels, dtype=object)
        
        # We need a numeric mapping for modes
        n_steps = len(labels)
        if n_steps < 2:
            return "N/A"

        # Find transitions: index t where label[t-1] == from_mode and label[t] == to_mode
        trans_indices = []
        stay_indices = []
        for t in range(1, n_steps):
            if labels[t - 1] == from_mode:
                if labels[t] == to_mode:
                    trans_indices.append(t - 1)
                elif labels[t] == from_mode:
                    stay_indices.append(t - 1)

        if not trans_indices or len(stay_indices) < 2:
            return "N/A"

        # Fit a shallow decision tree to find the splitting rule
        # Features: variables in df (except timestamp)
        feature_cols = [c for c in df.columns if c != "timestamp"]
        
        X_trans = df.loc[trans_indices, feature_cols].fillna(0.0).values
        X_stay = df.loc[stay_indices, feature_cols].fillna(0.0).values
        
        X = np.vstack([X_trans, X_stay])
        y = np.array([1] * len(X_trans) + [0] * len(X_stay))

        try:
            # Fit tree of depth 1 to find the single best splitting variable
            clf = DecisionTreeClassifier(max_depth=1, random_state=42)
            clf.fit(X, y)
            
            tree = clf.tree_
            feat_idx = tree.feature[0]
            
            if feat_idx >= 0:
                feat_name = feature_cols[feat_idx]
                threshold = tree.threshold[0]
                
                # Check which side represents the transition class (1)
                # left child (<= threshold) or right child (> threshold)
                left_class = np.argmax(tree.value[1])
                
                if left_class == 1:
                    return f"{feat_name} <= {threshold:.4g}"
                else:
                    return f"{feat_name} > {threshold:.4g}"
        except Exception:
            pass

        # Fallback to mean difference
        try:
            # If standard tree classification fails, check which variable has the largest z-score difference
            means_trans = df.loc[trans_indices, feature_cols].mean()
            means_stay = df.loc[stay_indices, feature_cols].mean()
            stds_stay = df.loc[stay_indices, feature_cols].std().replace(0.0, 1.0)
            
            diffs = (means_trans - means_stay).abs() / stds_stay
            best_feat = diffs.idxmax()
            
            if pd.notna(best_feat):
                val_trans = means_trans[best_feat]
                val_stay = means_stay[best_feat]
                threshold = (val_trans + val_stay) / 2.0
                
                if val_trans > val_stay:
                    return f"{best_feat} > {threshold:.4g}"
                else:
                    return f"{best_feat} <= {threshold:.4g}"
        except Exception:
            pass

        return "N/A"

    def _generate_mermaid(self, states: list[StateSummary], transitions: list[dict[str, Any]]) -> str:
        """Create a Mermaid state diagram string."""
        lines = ["stateDiagram-v2"]
        
        # Add state definitions (with descriptive alias)
        for s in states:
            # Clean name for node ID
            node_id = s.original_label
            clean_name = s.name.replace(" / ", " ").replace(" ", "_")
            lines.append(f"    state \"{s.name}\" as {node_id}")

        # Add transitions
        for t in transitions:
            from_id = t["from_mode"]
            to_id = t["to_mode"]
            prob = t["probability"]
            trigger = t["trigger_rule"]
            
            label = f"p={prob:.2f}"
            if trigger != "N/A":
                label += f" ({trigger})"
                
            lines.append(f"    {from_id} --> {to_id} : {label}")

        return "\n".join(lines)
