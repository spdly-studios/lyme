"""
Base Analyzer ABC.

All KSE analyzers implement this interface.  Each analyzer receives the
cleaned numeric DataFrame and the engine configuration, and returns an
``AnalyzerResult`` containing whatever combination of findings, relationships,
rules, modes, and transitions it discovered.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

from ..config import KSEConfig
from ..models import Finding, ModeTransition, OperationalMode, Relationship, Rule


@dataclass
class AnalyzerResult:
    """Container returned by every analyzer.

    Attributes:
        findings: Level-1 statistical observations.
        relationships: Level-2 directed relationships.
        rules: Level-3 IF/THEN interpretable rules.
        modes: Level-4 discovered operational modes.
        mode_transitions: Mode-to-mode transitions.
        mode_labels: Mapping from timestamp index position to mode label.
            Used by downstream analyzers (e.g., TransitionAnalyzer).
        errors: Any non-fatal errors or warnings encountered.
    """

    findings: list[Finding] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    modes: list[OperationalMode] = field(default_factory=list)
    mode_transitions: list[ModeTransition] = field(default_factory=list)
    mode_labels: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseAnalyzer(ABC):
    """Abstract base class for all KSE analyzers.

    Subclasses must implement :meth:`analyze`.

    Parameters:
        config: The top-level KSE configuration.
    """

    def __init__(self, config: KSEConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(
            f"kse.analyzers.{self.__class__.__name__}"
        )

    @property
    def name(self) -> str:
        """Short machine-readable name for this analyzer."""
        return self.__class__.__name__

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        """Run analysis on the provided numeric state matrix.

        Parameters:
            df: Cleaned numeric DataFrame.  Index is ``timestamp``,
                columns are variable names, values are float64.
                May contain NaN for missing observations.

        Returns:
            An :class:`AnalyzerResult` with all discovered knowledge.
        """
        ...

    # ------------------------------------------------------------------
    # Shared utility helpers
    # ------------------------------------------------------------------

    def _pair_coverage(self, df: pd.DataFrame, col_a: str, col_b: str) -> float:
        """Fraction of rows where both *col_a* and *col_b* are non-null."""
        mask = df[col_a].notna() & df[col_b].notna()
        if len(df) == 0:
            return 0.0
        return mask.sum() / len(df)

    def _log_progress(self, message: str, *args: object) -> None:
        if self.config.verbose:
            self.logger.info(message, *args)
