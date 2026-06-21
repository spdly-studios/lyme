"""
KSE Data Ingestion.

Loads canonical observations produced by UOC (Component 1) into a
pandas DataFrame suitable for analysis.  Supports three input modes:

1. **CSV** — reads ``aligned_state_matrix.csv`` directly.
2. **Parquet** — reads ``aligned_state_matrix.parquet``.
3. **API** — accepts a UOC ``ObservationStore`` + ``VariableRegistry``
   and constructs the aligned state matrix in memory.

In all cases, the result is a pandas DataFrame with a ``timestamp`` index
and one column per variable, containing only numeric (float) values.
Non-numeric columns are preserved separately for reference.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class IngestionResult:
    """Result of loading canonical observations into the KSE.

    Attributes:
        numeric_df: Time-indexed DataFrame of numeric variables (float64).
            Index is ``timestamp`` (float, Unix epoch seconds or sequence
            counter — whatever UOC produced).
        raw_df: Full DataFrame including non-numeric columns.
        variable_metadata: Dict mapping variable name to metadata dict
            (dtype, unit, source) if available from UOC registry.
        source_path: Path of the file loaded, if applicable.
        n_timestamps: Number of unique timestamps.
        n_variables: Total number of variables (numeric + non-numeric).
        n_numeric_variables: Number of purely numeric variables.
    """

    def __init__(
        self,
        numeric_df: pd.DataFrame,
        raw_df: pd.DataFrame,
        variable_metadata: dict[str, dict[str, Any]],
        source_path: Path | None = None,
    ) -> None:
        self.numeric_df = numeric_df
        self.raw_df = raw_df
        self.variable_metadata = variable_metadata
        self.source_path = source_path

    @property
    def n_timestamps(self) -> int:
        return len(self.numeric_df)

    @property
    def n_variables(self) -> int:
        return len(self.raw_df.columns)

    @property
    def n_numeric_variables(self) -> int:
        return len(self.numeric_df.columns)

    def __repr__(self) -> str:
        return (
            f"IngestionResult("
            f"timestamps={self.n_timestamps}, "
            f"variables={self.n_variables}, "
            f"numeric={self.n_numeric_variables})"
        )


def load_csv(path: Path | str) -> IngestionResult:
    """Load an aligned state matrix CSV produced by UOC.

    Parameters:
        path: Path to the CSV file.

    Returns:
        An :class:`IngestionResult` ready for analysis.
    """
    path = Path(path)
    logger.info("Loading CSV: %s", path)
    df = pd.read_csv(path)
    return _process_dataframe(df, source_path=path)


def load_parquet(path: Path | str) -> IngestionResult:
    """Load an aligned state matrix Parquet file produced by UOC.

    Parameters:
        path: Path to the Parquet file.

    Returns:
        An :class:`IngestionResult` ready for analysis.
    """
    path = Path(path)
    logger.info("Loading Parquet: %s", path)
    df = pd.read_parquet(path)
    return _process_dataframe(df, source_path=path)


def load_from_uoc(
    store: Any,
    registry: Any,
    alignment_strategy: str = "forward_fill",
) -> IngestionResult:
    """Load observations directly from UOC in-memory objects.

    Parameters:
        store: A UOC ``ObservationStore`` instance.
        registry: A UOC ``VariableRegistry`` instance.
        alignment_strategy: Alignment strategy name passed to UOC alignment.

    Returns:
        An :class:`IngestionResult` ready for analysis.
    """
    # Import UOC alignment lazily to avoid hard dependency if not installed
    try:
        from ..uoc.alignment import align, get_unique_timestamps
        from ..uoc.config import AlignmentStrategy as AlignStrat
    except ImportError as exc:
        raise ImportError(
            "uoc package is required for load_from_uoc(). "
            "Install UOC or use load_csv() / load_parquet() instead."
        ) from exc

    # Map string to enum
    strategy_map = {
        "exact": AlignStrat.EXACT,
        "nearest": AlignStrat.NEAREST,
        "forward_fill": AlignStrat.FORWARD_FILL,
        "interpolate": AlignStrat.INTERPOLATE,
    }
    strategy = strategy_map.get(alignment_strategy.lower(), AlignStrat.FORWARD_FILL)

    timestamps = get_unique_timestamps(store)
    var_ids = [v.id for v in registry]

    aligned = align(
        store=store,
        registry=registry,
        strategy=strategy,
        timestamps=timestamps,
        variables=var_ids,
    )

    # Build DataFrame
    rows = []
    for t in timestamps:
        row: dict[str, Any] = {"timestamp": t}
        for vid in var_ids:
            var = registry.get_by_id(vid)
            if var:
                row[var.name] = aligned[t].get(vid)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Build variable metadata from registry
    variable_metadata: dict[str, dict[str, Any]] = {}
    for var in registry:
        variable_metadata[var.name] = {
            "dtype": var.dtype.value if hasattr(var.dtype, "value") else str(var.dtype),
            "unit": var.unit,
            "source": var.source,
            "id": var.id,
        }

    return _process_dataframe(df, source_path=None, variable_metadata=variable_metadata)


def load_dataframe(df: pd.DataFrame) -> IngestionResult:
    """Load observations from an existing pandas DataFrame.

    The DataFrame must have a ``timestamp`` column (or be timestamp-indexed).
    All other columns are treated as variables.

    Parameters:
        df: The input DataFrame.

    Returns:
        An :class:`IngestionResult` ready for analysis.
    """
    return _process_dataframe(df.copy(), source_path=None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _process_dataframe(
    df: pd.DataFrame,
    source_path: Path | None = None,
    variable_metadata: dict[str, dict[str, Any]] | None = None,
) -> IngestionResult:
    """Normalise a raw DataFrame into a clean IngestionResult.

    Steps:
    1. Set ``timestamp`` as the index if present.
    2. Sort by timestamp.
    3. Separate numeric and non-numeric columns.
    4. Coerce numeric columns to float64 with NaN for un-parseable values.
    5. Log a coverage summary.
    """
    df = df.copy()

    # Normalise timestamp column / index
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    elif df.index.name != "timestamp":
        # Assume the index is already timestamps
        df.index.name = "timestamp"

    df = df.sort_index()

    # Separate numeric from non-numeric columns
    numeric_cols = []
    non_numeric_cols = []

    for col in df.columns:
        series = df[col]
        coerced = pd.to_numeric(series, errors="coerce")
        non_null_original = series.notna().sum()
        non_null_coerced = coerced.notna().sum()

        # Accept as numeric if ≥80% of non-null values survive coercion
        if non_null_original == 0 or (non_null_coerced / max(non_null_original, 1)) >= 0.8:
            df[col] = coerced
            numeric_cols.append(col)
        else:
            non_numeric_cols.append(col)

    numeric_df = df[numeric_cols].astype(float)
    raw_df = df

    # Log coverage
    total = len(numeric_df)
    for col in numeric_cols:
        coverage = numeric_df[col].notna().mean()
        if coverage < 0.5:
            logger.warning(
                "Variable '%s' has low coverage: %.0f%%", col, coverage * 100
            )

    logger.info(
        "Ingested %d timestamps, %d numeric variables, %d non-numeric variables.",
        total,
        len(numeric_cols),
        len(non_numeric_cols),
    )

    if non_numeric_cols:
        logger.info("Non-numeric variables (excluded from numeric analysis): %s", non_numeric_cols)

    meta = variable_metadata or {}
    return IngestionResult(
        numeric_df=numeric_df,
        raw_df=raw_df,
        variable_metadata=meta,
        source_path=source_path,
    )
