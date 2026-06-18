"""
Temporal Analyzer — Level 2 Lag and Trigger Detection.

Discovers:
1. **Cross-correlation lags** — peak lag between pairs of variables,
   estimating how many time steps after A changes that B responds.
2. **Trigger events** — discrete jumps (step changes) in one variable
   that are followed by a systematic response in another variable.

Emits ``Relationship`` objects with estimated lags and trigger descriptions.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import correlate, correlation_lags

from ..models import EvidenceLevel, Relationship, RelationType
from .base import AnalyzerResult, BaseAnalyzer


class TemporalAnalyzer(BaseAnalyzer):
    """Discovers lagged relationships and trigger events between variables."""

    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        result = AnalyzerResult()
        cols = list(df.columns)

        if len(cols) < 2:
            return result

        cfg = self.config.temporal
        self._log_progress(
            "Running temporal analysis on %d variables (max_lag=%d steps)...",
            len(cols),
            cfg.max_lag_steps,
        )

        for col_a, col_b in itertools.combinations(cols, 2):
            coverage = self._pair_coverage(df, col_a, col_b)
            if coverage < 0.5:
                continue

            pair = df[[col_a, col_b]].dropna()
            if len(pair) < max(20, cfg.max_lag_steps * 2):
                continue

            a = pair[col_a].values
            b = pair[col_b].values

            # Cross-correlation in both directions: A→B and B→A
            lag_rels = self._xcorr_relationships(col_a, col_b, a, b, coverage, cfg)
            result.relationships.extend(lag_rels)

            # Trigger detection: does a step change in A precede a change in B?
            trig_rels = self._trigger_relationships(col_a, col_b, a, b, pair.index, coverage, cfg)
            result.relationships.extend(trig_rels)

        self._log_progress("Temporal analysis complete: %d relationships.", len(result.relationships))
        return result

    # ------------------------------------------------------------------
    # Cross-correlation
    # ------------------------------------------------------------------

    def _xcorr_relationships(
        self,
        col_a: str,
        col_b: str,
        a: np.ndarray,
        b: np.ndarray,
        coverage: float,
        cfg: Any,
    ) -> list[Relationship]:
        """Detect lagged influence between col_a and col_b in both directions."""
        a_norm = _zscore(a)
        b_norm = _zscore(b)
        if a_norm is None or b_norm is None:
            return []

        max_lag = min(cfg.max_lag_steps, len(a) // 4)

        # Full cross-correlation
        xcorr = correlate(b_norm, a_norm, mode="full")
        lags = correlation_lags(len(b_norm), len(a_norm), mode="full")

        # Restrict to window
        mask = (lags >= -max_lag) & (lags <= max_lag)
        xcorr_windowed = xcorr[mask]
        lags_windowed = lags[mask]

        # Normalise to [-1, 1]
        norm_factor = len(a_norm)
        xcorr_norm = xcorr_windowed / norm_factor

        # Find the peak (max absolute)
        peak_idx = np.argmax(np.abs(xcorr_norm))
        peak_val = xcorr_norm[peak_idx]
        peak_lag = int(lags_windowed[peak_idx])

        if abs(peak_val) < cfg.min_xcorr_threshold:
            return []

        # Determine direction from lag sign:
        # positive lag means A leads B (A influences B)
        # negative lag means B leads A (B influences A)
        relationships = []

        if peak_lag > 0:
            source, target = col_a, col_b
            lag_val = peak_lag
        elif peak_lag < 0:
            source, target = col_b, col_a
            lag_val = -peak_lag
        else:
            # Lag=0: both directions are equally plausible — emit as correlation
            source, target = col_a, col_b
            lag_val = 0

        confidence = float(np.clip(abs(peak_val), 0.0, 1.0))
        lag_confidence = _lag_confidence(xcorr_norm, peak_idx, max_lag)
        evidence_level = _confidence_to_evidence(confidence)

        lag_desc = f"{lag_val} time step(s)" if lag_val > 0 else "immediately"
        relationships.append(
            Relationship(
                source=source,
                target=target,
                relation_type=RelationType.INFLUENCES,
                confidence=confidence,
                evidence_level=evidence_level,
                estimated_lag=float(lag_val),
                lag_confidence=lag_confidence,
                data_coverage=coverage,
                supporting_methods=["cross_correlation"],
                metadata={
                    "xcorr_peak": float(peak_val),
                    "lag_steps": lag_val,
                    "description": (
                        f"{source} appears to influence {target} "
                        f"with a delay of approximately {lag_desc} "
                        f"(cross-correlation peak={peak_val:.3f})."
                    ),
                },
            )
        )
        return relationships

    # ------------------------------------------------------------------
    # Trigger detection
    # ------------------------------------------------------------------

    def _trigger_relationships(
        self,
        col_a: str,
        col_b: str,
        a: np.ndarray,
        b: np.ndarray,
        timestamps: Any,
        coverage: float,
        cfg: Any,
    ) -> list[Relationship]:
        """Detect step-change triggers: a jump in A followed by a response in B."""
        results = []
        for source, target, src_vals, tgt_vals in [
            (col_a, col_b, a, b),
            (col_b, col_a, b, a),
        ]:
            rel = self._detect_trigger(
                source, target, src_vals, tgt_vals, coverage, cfg
            )
            if rel:
                results.append(rel)
        return results

    def _detect_trigger(
        self,
        source: str,
        target: str,
        src: np.ndarray,
        tgt: np.ndarray,
        coverage: float,
        cfg: Any,
    ) -> Relationship | None:
        """Detect whether step changes in *source* reliably precede changes in *target*."""
        if len(src) < 20:
            return None

        src_diff = np.diff(src)
        tgt_diff = np.diff(tgt)

        if np.std(src_diff) == 0:
            return None

        # Find "jump" indices in source (z-score > threshold)
        src_z = np.abs(src_diff) / (np.std(src_diff) + 1e-10)
        jump_indices = np.where(src_z > cfg.trigger_jump_z)[0]

        if len(jump_indices) < cfg.min_trigger_samples:
            return None

        max_lag = min(cfg.max_lag_steps, len(tgt) // 4)

        # For each jump, measure the response in tgt in the next max_lag steps
        response_scores = []
        for idx in jump_indices:
            window_end = min(idx + 1 + max_lag, len(tgt_diff))
            if window_end <= idx + 1:
                continue
            window = tgt_diff[idx + 1 : window_end]
            if len(window) == 0:
                continue
            # Score: mean absolute change in target after jump
            response_scores.append(np.mean(np.abs(window)))

        if not response_scores:
            return None

        # Baseline: mean absolute change in target at random times
        baseline_scores = []
        rng = np.random.default_rng(42)
        n_baseline = min(len(jump_indices) * 3, len(tgt_diff) - max_lag)
        if n_baseline < 3:
            return None
        random_indices = rng.integers(0, len(tgt_diff) - max_lag, size=n_baseline)
        for idx in random_indices:
            window_end = min(idx + max_lag, len(tgt_diff))
            window = tgt_diff[idx:window_end]
            if len(window):
                baseline_scores.append(np.mean(np.abs(window)))

        if not baseline_scores:
            return None

        mean_response = np.mean(response_scores)
        mean_baseline = np.mean(baseline_scores)

        # Trigger is meaningful if post-jump response is at least 50% larger
        ratio = mean_response / (mean_baseline + 1e-10)
        if ratio < 1.5:
            return None

        # Confidence based on ratio and number of samples
        confidence = float(np.clip((ratio - 1.0) / 3.0, 0.0, 0.85))
        evidence_level = _confidence_to_evidence(confidence)

        return Relationship(
            source=source,
            target=target,
            relation_type=RelationType.TRIGGERS,
            confidence=confidence,
            evidence_level=evidence_level,
            estimated_lag=0.0,
            lag_confidence=0.0,
            data_coverage=coverage,
            supporting_methods=["trigger_detection"],
            metadata={
                "n_triggers": len(jump_indices),
                "response_ratio": float(ratio),
                "description": (
                    f"Step changes in {source} are followed by a "
                    f"{ratio:.1f}x larger response in {target} "
                    f"compared to baseline (n={len(jump_indices)} events)."
                ),
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _zscore(a: np.ndarray) -> np.ndarray | None:
    """Standardise array; return None if std is zero."""
    std = np.std(a)
    if std == 0:
        return None
    return (a - np.mean(a)) / std


def _lag_confidence(xcorr: np.ndarray, peak_idx: int, max_lag: int) -> float:
    """Estimate how sharp the peak is relative to the surroundings."""
    peak_abs = abs(xcorr[peak_idx])
    neighbours = np.concatenate([xcorr[:peak_idx], xcorr[peak_idx + 1 :]])
    if len(neighbours) == 0:
        return 0.5
    mean_neighbour = np.mean(np.abs(neighbours))
    sharpness = (peak_abs - mean_neighbour) / (peak_abs + 1e-10)
    return float(np.clip(sharpness, 0.0, 1.0))


def _confidence_to_evidence(confidence: float) -> EvidenceLevel:
    if confidence >= 0.7:
        return EvidenceLevel.OBSERVED
    if confidence >= 0.45:
        return EvidenceLevel.PROBABLE
    return EvidenceLevel.SPECULATIVE
