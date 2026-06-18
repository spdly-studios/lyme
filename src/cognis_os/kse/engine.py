"""
KSE Main Engine.

Orchestrates the entire Knowledge Synthesis pipeline.  Loads a DataFrame
(via IngestionResult), feeds it sequentially to all active analyzers,
sends the resulting set of findings to the assembler, and compiles the
final multi-level SystemModel.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .analyzers import (
    AnalyzerResult,
    CausalAnalyzer,
    CorrelationAnalyzer,
    ModeAnalyzer,
    TemporalAnalyzer,
    ThresholdAnalyzer,
    TransitionAnalyzer,
)
from .config import KSEConfig
from .ingestion import IngestionResult, load_dataframe
from .knowledge import KnowledgeAssembler
from .models import SystemModel

logger = logging.getLogger(__name__)


class KnowledgeSynthesisEngine:
    """The orchestrator for the Knowledge Synthesis Engine (KSE) pipeline.

    Parameters:
        config: The top-level KSE configuration settings.
    """

    def __init__(self, config: KSEConfig | None = None) -> None:
        self.config = config or KSEConfig()
        self.assembler = KnowledgeAssembler(self.config)

    def analyze(self, ingestion: IngestionResult) -> SystemModel:
        """Run the full analysis pipeline on the provided IngestionResult.

        Parameters:
            ingestion: Loaded telemetry observations.

        Returns:
            The compiled SystemModel containing all 5 levels of understanding.
        """
        start_time = time.time()
        df = ingestion.numeric_df
        variables = list(df.columns)

        if len(variables) == 0:
            logger.warning("Empty DataFrame passed to KSE — no variables to analyze.")
            return SystemModel(
                variable_names=list(ingestion.raw_df.columns),
                timestamp_count=ingestion.n_timestamps,
                metadata=self.config.metadata,
            )

        if self.config.verbose:
            print(f"[*] Starting Knowledge Synthesis for {len(variables)} variables across {len(df)} timestamps...")

        # 1. Level 1: Static Correlation & MI
        corr_analyzer = CorrelationAnalyzer(self.config)
        corr_res = corr_analyzer.analyze(df)

        # 2. Level 2: Temporal lag & Trigger detection
        temp_analyzer = TemporalAnalyzer(self.config)
        temp_res = temp_analyzer.analyze(df)

        # 3. Level 2 Causal: Granger Causality
        # Extract candidate pairs from Correlation & Temporal results to avoid testing all pairs
        candidate_pairs = self._extract_candidate_pairs(corr_res, temp_res)
        causal_analyzer = CausalAnalyzer(self.config, candidate_pairs=candidate_pairs)
        causal_res = causal_analyzer.analyze(df)

        # 4. Level 3: Threshold rules (Decision Trees)
        thresh_analyzer = ThresholdAnalyzer(self.config)
        thresh_res = thresh_analyzer.analyze(df)

        # 5. Level 4: Operational Mode Clustering
        mode_analyzer = ModeAnalyzer(self.config)
        mode_res = mode_analyzer.analyze(df)

        # 6. Level 4/5: State Transitions
        trans_analyzer = TransitionAnalyzer(self.config)
        trans_res = trans_analyzer.analyze(df, mode_labels=mode_res.mode_labels)

        # Combine all analyzer results
        all_findings = corr_res.findings + causal_res.findings + thresh_res.findings
        all_relationships = temp_res.relationships + causal_res.relationships
        all_rules = thresh_res.rules
        all_modes = mode_res.modes
        all_transitions = trans_res.mode_transitions

        # Assemble and build knowledge graph
        system_model = self.assembler.assemble(
            variable_names=list(ingestion.raw_df.columns),
            findings=all_findings,
            relationships=all_relationships,
            rules=all_rules,
            modes=all_modes,
            transitions=all_transitions,
            variable_metadata=ingestion.variable_metadata,
            total_timestamps=ingestion.n_timestamps,
        )

        elapsed = time.time() - start_time
        if self.config.verbose:
            print(f"[+] Knowledge Synthesis complete in {elapsed:.2f} seconds.")
            print(f"    - Findings (L1): {len(system_model.findings)}")
            print(f"    - Relationships (L2): {len(system_model.relationships)}")
            print(f"    - Rules (L3): {len(system_model.rules)}")
            print(f"    - Operational Modes (L4): {len(system_model.modes)}")
            print(f"    - Contradictions: {len(system_model.contradictions)}")

        return system_model

    def analyze_dataframe(self, df: Any) -> SystemModel:
        """Helper to run analysis directly on a pandas DataFrame.

        Parameters:
            df: A pandas DataFrame containing variable columns and a timestamp.

        Returns:
            The compiled SystemModel.
        """
        ingest = load_dataframe(df)
        return self.analyze(ingest)

    # ------------------------------------------------------------------

    def _extract_candidate_pairs(
        self, corr_res: AnalyzerResult, temp_res: AnalyzerResult
    ) -> list[tuple[str, str]]:
        """Combine variables from L1 and L2 findings to build a list of candidate causal pairs."""
        candidates = set()

        # From correlations (order doesn't matter for Granger candidates, we test both directions)
        for f in corr_res.findings:
            if len(f.variables) == 2:
                candidates.add(tuple(sorted(f.variables)))

        # From cross-correlation relationships
        for r in temp_res.relationships:
            candidates.add(tuple(sorted([r.source, r.target])))

        # Return as list of sorted pairs
        return [tuple(pair) for pair in candidates] # type: ignore
