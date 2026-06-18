"""
Correlation Analyzer — Level 1 Findings.

Discovers pairwise statistical associations between numeric variables using:
- Pearson correlation (linear relationships)
- Spearman correlation (monotonic relationships)
- Mutual Information (non-linear associations)

Emits ``Finding`` objects describing each significant association found.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import KBinsDiscretizer

from ..models import EvidenceLevel, Finding, RelationType
from .base import AnalyzerResult, BaseAnalyzer


class CorrelationAnalyzer(BaseAnalyzer):
    """Computes Pearson, Spearman, and Mutual Information for all variable pairs.

    Produces Level-1 ``Finding`` objects.
    """

    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        result = AnalyzerResult()
        cols = list(df.columns)

        if len(cols) < 2:
            self._log_progress("Not enough variables for correlation analysis.")
            return result

        cfg = self.config.correlation
        self._log_progress(
            "Running correlation analysis on %d variables (%d pairs)...",
            len(cols),
            len(cols) * (len(cols) - 1) // 2,
        )

        for col_a, col_b in itertools.combinations(cols, 2):
            coverage = self._pair_coverage(df, col_a, col_b)
            if coverage < cfg.min_data_coverage:
                continue

            # Drop NaNs for this pair
            pair = df[[col_a, col_b]].dropna()
            if len(pair) < 10:
                continue

            a_vals = pair[col_a].values
            b_vals = pair[col_b].values

            # --- Pearson ---
            findings = self._pearson_finding(col_a, col_b, a_vals, b_vals, coverage, cfg)
            result.findings.extend(findings)

            # --- Spearman ---
            findings = self._spearman_finding(col_a, col_b, a_vals, b_vals, coverage, cfg)
            result.findings.extend(findings)

            # --- Mutual Information ---
            findings = self._mi_finding(col_a, col_b, a_vals, b_vals, coverage, cfg)
            result.findings.extend(findings)

        self._log_progress("Correlation analysis complete: %d findings.", len(result.findings))
        return result

    # ------------------------------------------------------------------
    # Per-metric helpers
    # ------------------------------------------------------------------

    def _pearson_finding(
        self,
        col_a: str,
        col_b: str,
        a: np.ndarray,
        b: np.ndarray,
        coverage: float,
        cfg: Any,
    ) -> list[Finding]:
        try:
            r, p = pearsonr(a, b)
        except Exception:
            return []

        if abs(r) < cfg.pearson_threshold or p > cfg.p_value_threshold:
            return []

        direction = "positive" if r > 0 else "negative"
        strength = _correlation_strength(abs(r))
        confidence = _r_to_confidence(abs(r), len(a))
        evidence_level = _confidence_to_evidence(confidence)

        return [
            Finding(
                variables=[col_a, col_b],
                description=(
                    f"{col_a} and {col_b} exhibit {strength} {direction} "
                    f"linear correlation (Pearson r={r:.3f})."
                ),
                confidence=confidence,
                evidence_level=evidence_level,
                metric_name="pearson_r",
                metric_value=float(r),
                data_coverage=coverage,
                p_value=float(p),
                method="pearson",
                metadata={"n": len(a), "direction": direction},
            )
        ]

    def _spearman_finding(
        self,
        col_a: str,
        col_b: str,
        a: np.ndarray,
        b: np.ndarray,
        coverage: float,
        cfg: Any,
    ) -> list[Finding]:
        try:
            rho, p = spearmanr(a, b)
        except Exception:
            return []

        if abs(rho) < cfg.spearman_threshold or p > cfg.p_value_threshold:
            return []

        direction = "positive" if rho > 0 else "negative"
        strength = _correlation_strength(abs(rho))
        confidence = _r_to_confidence(abs(rho), len(a))
        evidence_level = _confidence_to_evidence(confidence)

        return [
            Finding(
                variables=[col_a, col_b],
                description=(
                    f"{col_a} and {col_b} exhibit {strength} {direction} "
                    f"monotonic correlation (Spearman rho={rho:.3f})."
                ),
                confidence=confidence,
                evidence_level=evidence_level,
                metric_name="spearman_rho",
                metric_value=float(rho),
                data_coverage=coverage,
                p_value=float(p),
                method="spearman",
                metadata={"n": len(a), "direction": direction},
            )
        ]

    def _mi_finding(
        self,
        col_a: str,
        col_b: str,
        a: np.ndarray,
        b: np.ndarray,
        coverage: float,
        cfg: Any,
    ) -> list[Finding]:
        try:
            mi = mutual_info_regression(
                a.reshape(-1, 1), b, random_state=42
            )[0]
        except Exception:
            return []

        if mi < cfg.mi_threshold:
            return []

        # Normalise MI by entropy of b for a [0,1] confidence proxy
        mi_norm = min(mi / (mi + 1.0), 1.0)
        confidence = float(np.clip(mi_norm * 1.5, 0.0, 1.0))
        evidence_level = _confidence_to_evidence(confidence)

        return [
            Finding(
                variables=[col_a, col_b],
                description=(
                    f"{col_a} and {col_b} share significant mutual information "
                    f"(MI={mi:.3f}), suggesting a non-linear statistical dependency."
                ),
                confidence=confidence,
                evidence_level=evidence_level,
                metric_name="mutual_information",
                metric_value=float(mi),
                data_coverage=coverage,
                p_value=None,
                method="mutual_information",
                metadata={"n": len(a)},
            )
        ]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _correlation_strength(r: float) -> str:
    if r >= 0.9:
        return "very strong"
    if r >= 0.7:
        return "strong"
    if r >= 0.5:
        return "moderate"
    return "weak"


def _r_to_confidence(r: float, n: int) -> float:
    """Convert |r| and sample size to a composite confidence score."""
    # Base confidence from |r|
    base = r
    # Sample size penalty: small samples reduce confidence
    n_factor = min(1.0, n / 100.0)
    return float(np.clip(base * (0.7 + 0.3 * n_factor), 0.0, 1.0))


def _confidence_to_evidence(confidence: float) -> EvidenceLevel:
    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
