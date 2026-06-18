"""
Threshold Analyzer — Level 3 IF/THEN Rule Discovery.

Uses shallow Decision Trees to extract human-readable threshold rules
of the form:

    IF MotorSpeed > 400 AND BatteryVoltage < 3.8
    THEN Temperature tends to increase.

For each target variable, a regression tree is trained using all other
variables as predictors.  Tree paths from root to leaf are extracted as
IF/THEN rules, keeping only leaves with sufficient support and precision.

Multi-variable conditions (involving 2-3 variables jointly) are naturally
discovered by the tree structure.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..models import Condition, EvidenceLevel, Rule
from .base import AnalyzerResult, BaseAnalyzer


class ThresholdAnalyzer(BaseAnalyzer):
    """Extracts interpretable IF/THEN threshold rules via decision trees."""

    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        result = AnalyzerResult()
        cols = list(df.columns)

        if len(cols) < 2:
            return result

        try:
            from sklearn.tree import DecisionTreeRegressor, export_text
        except ImportError:
            self.logger.warning("scikit-learn not installed — skipping threshold analysis.")
            return result

        cfg = self.config.threshold
        self._log_progress("Running threshold analysis on %d variables...", len(cols))

        for target_col in cols:
            predictor_cols = [c for c in cols if c != target_col]
            rules = self._extract_rules(df, target_col, predictor_cols, cfg)
            result.rules.extend(rules)

        self._log_progress("Threshold analysis complete: %d rules.", len(result.rules))
        return result

    # ------------------------------------------------------------------

    def _extract_rules(
        self,
        df: pd.DataFrame,
        target_col: str,
        predictor_cols: list[str],
        cfg: Any,
    ) -> list[Rule]:
        """Fit a tree for *target_col* and extract rules from leaf paths."""
        from sklearn.tree import DecisionTreeRegressor

        # Build feature matrix — use rows where all are non-null
        sub = df[predictor_cols + [target_col]].dropna()
        if len(sub) < max(30, cfg.min_samples_leaf * 4):
            return []

        X = sub[predictor_cols].values
        y = sub[target_col].values

        # Skip near-constant targets
        if np.std(y) < 1e-10:
            return []

        tree = DecisionTreeRegressor(
            max_depth=min(cfg.max_depth, cfg.max_conditions),
            min_samples_leaf=max(cfg.min_samples_leaf, int(len(sub) * cfg.min_support)),
            random_state=42,
        )
        try:
            tree.fit(X, y)
        except Exception as exc:
            self.logger.debug("Tree fit failed for %s: %s", target_col, exc)
            return []

        # Extract rules from every leaf path
        rules = _extract_leaf_rules(
            tree=tree,
            feature_names=predictor_cols,
            target_name=target_col,
            X=X,
            y=y,
            cfg=cfg,
            n_total=len(df),
        )
        return rules


# ---------------------------------------------------------------------------
# Tree path extraction
# ---------------------------------------------------------------------------


def _extract_leaf_rules(
    tree: Any,
    feature_names: list[str],
    target_name: str,
    X: np.ndarray,
    y: np.ndarray,
    cfg: Any,
    n_total: int,
) -> list[Rule]:
    """Walk the fitted tree and extract one Rule per leaf."""
    from sklearn.tree import _tree

    tree_ = tree.tree_
    rules: list[Rule] = []
    global_mean = float(np.mean(y))
    global_std = float(np.std(y))

    def recurse(node: int, conditions: list[Condition]) -> None:
        if tree_.feature[node] == _tree.TREE_UNDEFINED:
            # Leaf node
            node_value = float(tree_.value[node][0, 0])
            node_n = int(tree_.n_node_samples[node])
            support = node_n / n_total

            if support < cfg.min_support:
                return
            if not conditions:
                return
            if len(conditions) > cfg.max_conditions:
                return

            # Determine outcome description
            delta = node_value - global_mean
            if global_std > 0:
                delta_z = delta / global_std
            else:
                delta_z = 0.0

            direction = "increase" if delta > 0 else "decrease"
            magnitude = _magnitude_label(abs(delta_z))

            outcome_desc = (
                f"{target_name} tends to {direction} "
                f"({magnitude} — mean={node_value:.4g}, "
                f"global mean={global_mean:.4g})."
            )

            # Precision: how well does this leaf predict the direction?
            # Subset rows reaching this leaf
            leaf_mask = tree.apply(X) == node
            if leaf_mask.sum() < cfg.min_samples_leaf:
                return
            leaf_y = y[leaf_mask]
            if delta > 0:
                precision = float(np.mean(leaf_y > global_mean))
            else:
                precision = float(np.mean(leaf_y < global_mean))

            if precision < cfg.min_precision:
                return

            confidence = _rule_confidence(support, precision, len(conditions))
            evidence_level = _confidence_to_evidence(confidence)

            rules.append(
                Rule(
                    conditions=list(conditions),
                    target_variable=target_name,
                    outcome_description=outcome_desc,
                    confidence=confidence,
                    evidence_level=evidence_level,
                    support=support,
                    precision=precision,
                    metadata={
                        "leaf_mean": node_value,
                        "global_mean": global_mean,
                        "delta_z": delta_z,
                        "n_leaf": node_n,
                    },
                )
            )
        else:
            # Internal node — branch left (≤ threshold) and right (> threshold)
            feat_name = feature_names[tree_.feature[node]]
            threshold = float(tree_.threshold[node])

            # Left branch: feature ≤ threshold
            recurse(
                tree_.children_left[node],
                conditions + [Condition(variable=feat_name, operator="<=", threshold=threshold)],
            )
            # Right branch: feature > threshold
            recurse(
                tree_.children_right[node],
                conditions + [Condition(variable=feat_name, operator=">", threshold=threshold)],
            )

    recurse(0, [])
    return rules


def _magnitude_label(delta_z: float) -> str:
    if delta_z >= 2.0:
        return "substantially"
    if delta_z >= 1.0:
        return "notably"
    if delta_z >= 0.5:
        return "moderately"
    return "slightly"


def _rule_confidence(support: float, precision: float, n_conditions: int) -> float:
    """Composite confidence from support, precision, and rule complexity."""
    base = (support ** 0.3) * precision
    # Penalise complex rules slightly (prefer simpler explanations)
    complexity_penalty = 1.0 - (n_conditions - 1) * 0.05
    return float(np.clip(base * complexity_penalty, 0.0, 1.0))


def _confidence_to_evidence(confidence: float) -> EvidenceLevel:
    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
