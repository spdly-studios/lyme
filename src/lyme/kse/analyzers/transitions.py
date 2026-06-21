"""
Transition Analyzer — State Machine Extraction.

Uses the mode labels produced by the ModeAnalyzer to build a directed
state-transition graph.

For each consecutive pair of timestamps, if the mode label changes, a
transition is recorded.  Transition probabilities are computed from
observed counts.

Emits ``ModeTransition`` objects forming the Level 4/5 operational
state machine of the system.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

import pandas as pd

from ..models import ModeTransition
from .base import AnalyzerResult, BaseAnalyzer


class TransitionAnalyzer(BaseAnalyzer):
    """Extracts a probabilistic state-transition graph from mode label sequences."""

    def analyze(self, df: pd.DataFrame, mode_labels: list[str] | None = None) -> AnalyzerResult:  # type: ignore[override]
        result = AnalyzerResult()

        if not mode_labels or len(mode_labels) < 2:
            self._log_progress("No mode labels provided — skipping transition analysis.")
            return result

        self._log_progress("Running transition analysis on %d mode labels...", len(mode_labels))

        # Count transitions
        transition_counts: dict[tuple[str, str], int] = defaultdict(int)
        from_counts: dict[str, int] = defaultdict(int)

        for i in range(len(mode_labels) - 1):
            frm = mode_labels[i]
            to = mode_labels[i + 1]
            if frm == "noise" or to == "noise":
                continue
            if frm != to:  # Only record actual transitions
                transition_counts[(frm, to)] += 1
                from_counts[frm] += 1

        if not transition_counts:
            self._log_progress("No transitions found between modes.")
            return result

        # Build ModeTransition objects
        for (frm, to), count in sorted(transition_counts.items(), key=lambda x: -x[1]):
            total_from = from_counts[frm]
            prob = count / total_from if total_from > 0 else 0.0

            # Confidence is proportional to count and probability
            confidence = float(np.clip(prob * np.log1p(count) / 3.0, 0.0, 1.0))

            result.mode_transitions.append(
                ModeTransition(
                    from_mode=frm,
                    to_mode=to,
                    count=count,
                    probability=prob,
                    confidence=confidence,
                )
            )

        self._log_progress(
            "Transition analysis complete: %d transitions.", len(result.mode_transitions)
        )
        return result
