"""
KSE Contradiction Detector.

Scans discovered findings, relationships, and rules to identify conflicting
evidence or competing explanations, helping to ensure the engine does not
blindly report inconsistent knowledge.
"""

from __future__ import annotations

from typing import Any

from ..models import Contradiction, Finding, OperationalMode, Relationship, Rule


class ContradictionDetector:
    """Analyzes synthesised knowledge to find and report contradictions."""

    def detect(
        self,
        findings: list[Finding],
        relationships: list[Relationship],
        rules: list[Rule],
        modes: list[OperationalMode],
    ) -> list[Contradiction]:
        """Detect conflicts in the extracted knowledge components.

        Parameters:
            findings: Level-1 findings.
            relationships: Level-2 relationships.
            rules: Level-3 rules.
            modes: Level-4 modes.

        Returns:
            A list of detected Contradiction instances.
        """
        contradictions: list[Contradiction] = []

        # 1. Sign contradiction: Pearson correlation vs Rule direction
        self._detect_sign_contradictions(findings, rules, contradictions)

        # 2. Loop / Feedback contradiction: A influences B AND B influences A
        # (Granger causality or cross-corr might find both, which could be feedback
        # but is worth highlighting as a warning/contradiction if their lags conflict)
        self._detect_feedback_contradictions(relationships, contradictions)

        # 3. Correlation vs Causality direction mismatch
        # (e.g. A and B correlate negatively but causal relationship claims positive increase)
        self._detect_corr_vs_causal_mismatches(findings, relationships, contradictions)

        return contradictions

    # ------------------------------------------------------------------

    def _detect_sign_contradictions(
        self,
        findings: list[Finding],
        rules: list[Rule],
        contradictions: list[Contradiction],
    ) -> None:
        """Find cases where linear correlation sign contradicts threshold rules."""
        # Map pair -> correlation sign (+1 or -1)
        corr_signs: dict[tuple[str, str], float] = {}
        for f in findings:
            if f.method in ("pearson", "spearman"):
                var_a, var_b = f.variables[0], f.variables[1]
                key = tuple(sorted([var_a, var_b]))
                corr_signs[key] = f.metric_value

        for r in rules:
            # Check rules with a single condition to keep mapping simple
            if len(r.conditions) != 1:
                continue
            cond = r.conditions[0]
            pred_var = cond.variable
            target_var = r.target_variable

            key = tuple(sorted([pred_var, target_var]))
            if key not in corr_signs:
                continue

            r_val = corr_signs[key]
            # Check outcome direction
            desc = r.outcome_description.lower()
            if "tend to increase" in desc or "tends to increase" in desc:
                # Rule says: cond (e.g. > threshold) -> increase
                # If operator is '>', it's a positive effect. If '<=', it's a negative effect.
                rule_is_positive = (cond.operator in (">", ">="))
            elif "tend to decrease" in desc or "tends to decrease" in desc:
                rule_is_positive = (cond.operator in ("<", "<="))
            else:
                continue

            corr_is_positive = (r_val > 0)
            if corr_is_positive != rule_is_positive:
                contradictions.append(
                    Contradiction(
                        description=(
                            f"Sign conflict between {pred_var} and {target_var}: "
                            f"linear correlation is {'positive' if corr_is_positive else 'negative'} "
                            f"(value={r_val:.3f}), but threshold rule suggests a "
                            f"{'positive' if rule_is_positive else 'negative'} effect."
                        ),
                        finding_a=f"Correlation finding: {pred_var} and {target_var} r={r_val:.3f}",
                        finding_b=f"Rule: {r.to_text()}",
                        severity="medium",
                    )
                )

    def _detect_feedback_contradictions(
        self,
        relationships: list[Relationship],
        contradictions: list[Contradiction],
    ) -> None:
        """Find loop/feedback loops with conflicting/unstable lag directions."""
        rel_map: dict[tuple[str, str], Relationship] = {}
        for r in relationships:
            rel_map[(r.source, r.target)] = r

        for (src, tgt), rel_ab in list(rel_map.items()):
            reverse_key = (tgt, src)
            if reverse_key in rel_map:
                rel_ba = rel_map[reverse_key]

                # We have A -> B and B -> A.
                # Highlight if their estimated lags are zero or if they indicate a circular lag conflict
                if rel_ab.estimated_lag == 0 and rel_ba.estimated_lag == 0:
                    # Instantaneous bidirectional influence: high uncertainty
                    contradictions.append(
                        Contradiction(
                            description=(
                                f"Instantaneous bidirectional causality detected between {src} and {tgt}. "
                                "Both Granger/Xcorr pathways show zero lag. Direction of influence is ambiguous."
                            ),
                            finding_a=f"A→B: {rel_ab.metadata.get('description', '')}",
                            finding_b=f"B→A: {rel_ba.metadata.get('description', '')}",
                            severity="low",
                        )
                    )

    def _detect_corr_vs_causal_mismatches(
        self,
        findings: list[Finding],
        relationships: list[Relationship],
        contradictions: list[Contradiction],
    ) -> None:
        """Verify correlation sign matches the causal metadata description if present."""
        corr_signs: dict[tuple[str, str], float] = {}
        for f in findings:
            if f.method in ("pearson", "spearman"):
                var_a, var_b = f.variables[0], f.variables[1]
                key = tuple(sorted([var_a, var_b]))
                corr_signs[key] = f.metric_value

        for rel in relationships:
            key = tuple(sorted([rel.source, rel.target]))
            if key not in corr_signs:
                continue

            r_val = corr_signs[key]
            # If cross_correlation peak is negative, check if correlation matches.
            xcorr_peak = rel.metadata.get("xcorr_peak")
            if xcorr_peak is not None:
                if (xcorr_peak > 0) != (r_val > 0):
                    contradictions.append(
                        Contradiction(
                            description=(
                                f"Temporal cross-correlation peak for {rel.source} → {rel.target} "
                                f"is {'positive' if xcorr_peak > 0 else 'negative'} ({xcorr_peak:.3f}), "
                                f"but static correlation is {'positive' if r_val > 0 else 'negative'} ({r_val:.3f})."
                            ),
                            finding_a=f"Correlation r={r_val:.3f}",
                            finding_b=f"Xcorr peak={xcorr_peak:.3f} at lag={rel.estimated_lag}",
                            severity="medium",
                        )
                    )
