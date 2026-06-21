"""
Causal Analyzer — Granger Causality Direction Detection.

Uses Granger causality tests to determine whether the history of variable A
helps predict variable B beyond what B's own history already predicts.

Only tests pairs that have already been found by the CorrelationAnalyzer or
TemporalAnalyzer (passed as ``candidate_pairs``), which avoids the O(n²)
blowup when testing hundreds of variables.

Emits ``Relationship`` objects with ``RelationType.INFLUENCES`` and a
causal direction backed by statistical significance.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

from ..models import EvidenceLevel, Relationship, RelationType
from .base import AnalyzerResult, BaseAnalyzer


class CausalAnalyzer(BaseAnalyzer):
    """Granger-causality-based direction analyser.

    Parameters:
        config: Top-level KSE config.
        candidate_pairs: Optional list of ``(col_a, col_b)`` tuples to test.
            If None the analyzer selects pairs based on correlation strength.
    """

    def __init__(self, config: Any, candidate_pairs: list[tuple[str, str]] | None = None) -> None:
        super().__init__(config)
        self._candidate_pairs = candidate_pairs

    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        result = AnalyzerResult()
        cfg = self.config.causal

        try:
            from statsmodels.tsa.stattools import grangercausalitytests
        except ImportError:
            self.logger.warning(
                "statsmodels not installed — skipping Granger causality analysis."
            )
            return result

        cols = list(df.columns)
        if len(cols) < 2:
            return result

        # Build candidate pairs
        if self._candidate_pairs:
            pairs = [
                p for p in self._candidate_pairs
                if p[0] in df.columns and p[1] in df.columns
            ]
        else:
            pairs = self._select_pairs(df, cfg.max_pairs)

        if not pairs:
            return result

        self._log_progress(
            "Running Granger causality on %d candidate pairs (max_lag=%d)...",
            len(pairs),
            cfg.max_lag_steps,
        )

        for col_a, col_b in pairs:
            rels = self._test_pair(df, col_a, col_b, cfg, grangercausalitytests)
            result.relationships.extend(rels)

        self._log_progress(
            "Granger analysis complete: %d causal relationships.", len(result.relationships)
        )
        return result

    # ------------------------------------------------------------------

    def _select_pairs(
        self, df: pd.DataFrame, max_pairs: int
    ) -> list[tuple[str, str]]:
        """Select the top ``max_pairs`` variable pairs by absolute correlation."""
        import itertools

        corr = df.corr(numeric_only=True).abs()
        pairs_scored = []
        for col_a, col_b in itertools.combinations(df.columns, 2):
            if col_a in corr.index and col_b in corr.columns:
                r = corr.loc[col_a, col_b]
                if not np.isnan(r):
                    pairs_scored.append((r, col_a, col_b))

        pairs_scored.sort(key=lambda x: -x[0])
        return [(b, c) for _, b, c in pairs_scored[:max_pairs]]

    def _test_pair(
        self,
        df: pd.DataFrame,
        col_a: str,
        col_b: str,
        cfg: Any,
        gct_fn: Any,
    ) -> list[Relationship]:
        """Test A→B and B→A Granger causality and emit Relationships."""
        pair = df[[col_a, col_b]].dropna()
        if len(pair) < max(30, cfg.max_lag_steps * 3):
            return []

        coverage = len(pair) / len(df)
        results = []

        for source, target in [(col_a, col_b), (col_b, col_a)]:
            rel = self._granger_direction(
                pair, source, target, cfg, gct_fn, coverage
            )
            if rel:
                results.append(rel)

        return results

    def _granger_direction(
        self,
        pair: pd.DataFrame,
        source: str,
        target: str,
        cfg: Any,
        gct_fn: Any,
        coverage: float,
    ) -> Relationship | None:
        """Run Granger test: does *source* Granger-cause *target*?"""
        # grangercausalitytests expects [target, source] column order
        data = pair[[target, source]].values.astype(float)

        # Check for near-constant columns (would break the test)
        if np.std(data[:, 0]) < 1e-10 or np.std(data[:, 1]) < 1e-10:
            return None

        max_lag = min(cfg.max_lag_steps, len(data) // 6)
        if max_lag < 1:
            return None

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gc_result = gct_fn(
                    data, maxlag=max_lag, verbose=False
                )
        except Exception as exc:
            self.logger.debug("Granger test failed for %s→%s: %s", source, target, exc)
            return None

        # Find best lag by minimum F-test p-value across all tested lags
        best_p = 1.0
        best_lag = 1
        for lag, tests in gc_result.items():
            # 'ssr_ftest' is the F-test result: (F-stat, p-value, df_denom, df_num)
            p = tests[0]["ssr_ftest"][1]
            if p < best_p:
                best_p = p
                best_lag = lag

        if best_p > cfg.p_value_threshold:
            return None

        # Convert p-value to confidence (lower p → higher confidence)
        confidence = float(np.clip(1.0 - best_p * 10, 0.3, 0.95))
        evidence_level = _confidence_to_evidence(confidence)

        return Relationship(
            source=source,
            target=target,
            relation_type=RelationType.INFLUENCES,
            confidence=confidence,
            evidence_level=evidence_level,
            estimated_lag=float(best_lag),
            lag_confidence=float(np.clip(1.0 - best_p, 0.0, 1.0)),
            p_value=float(best_p),
            data_coverage=coverage,
            supporting_methods=["granger_causality"],
            metadata={
                "best_lag": best_lag,
                "description": (
                    f"{source} Granger-causes {target} at lag {best_lag} "
                    f"(F-test p={best_p:.4f})."
                ),
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence_to_evidence(confidence: float) -> EvidenceLevel:
    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
