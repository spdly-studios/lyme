"""
Mode Analyzer — Operational Mode Discovery.

Discovers naturally occurring operational states of the system through
unsupervised clustering of the aligned state matrix.

Strategy:
1. Standardise the numeric state matrix.
2. Run HDBSCAN (density-based, no need to specify k).
3. If HDBSCAN finds < 2 meaningful clusters, fall back to KMeans with
   BIC-optimal k (tested from 2 to ``kmeans_max_k``).
4. Label each cluster with human-readable mode descriptions based on
   the dominant variable ranges relative to global statistics.
5. Identify the top distinguishing features per cluster using per-feature
   effect sizes (|mean_cluster - mean_global| / global_std).

Emits ``OperationalMode`` objects and a ``mode_labels`` list parallel to
the DataFrame index, which is passed to the TransitionAnalyzer.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..models import EvidenceLevel, OperationalMode
from .base import AnalyzerResult, BaseAnalyzer


class ModeAnalyzer(BaseAnalyzer):
    """Discovers operational modes via density-based or centroid clustering."""

    def analyze(self, df: pd.DataFrame) -> AnalyzerResult:
        result = AnalyzerResult()
        cfg = self.config.mode

        if len(df) < max(20, cfg.min_cluster_size * 2):
            self._log_progress("Too few observations for mode analysis.")
            return result

        if df.shape[1] == 0:
            return result

        # Impute NaN with column medians before scaling
        df_imputed = df.copy()
        for col in df_imputed.columns:
            median = df_imputed[col].median()
            df_imputed[col] = df_imputed[col].fillna(median)

        # Standardise
        means = df_imputed.mean()
        stds = df_imputed.std().replace(0, 1)
        X = ((df_imputed - means) / stds).values

        self._log_progress(
            "Running mode discovery on %d timestamps × %d variables...",
            X.shape[0],
            X.shape[1],
        )

        labels, method_used = self._cluster(X, cfg)

        if labels is None:
            self._log_progress("Mode discovery found no meaningful clusters.")
            return result

        unique_labels = [l for l in np.unique(labels) if l != -1]
        if len(unique_labels) < 2:
            self._log_progress("Only one mode found — system may be in a single state.")

        # Build OperationalMode objects
        total_count = len(df)
        mode_label_list: list[str] = ["noise"] * total_count

        for lbl in unique_labels:
            mask = labels == lbl
            member_count = int(mask.sum())
            prevalence = member_count / total_count

            if prevalence < cfg.min_mode_prevalence:
                continue

            # Centroid in original scale
            centroid = {
                col: float(df_imputed.iloc[mask][col].mean())
                for col in df_imputed.columns
            }
            global_means = means.to_dict()
            global_stds = stds.to_dict()

            # Distinguishing features: highest |effect size|
            effect_sizes = {
                col: abs(centroid[col] - global_means[col]) / (global_stds[col] + 1e-10)
                for col in df_imputed.columns
            }
            sorted_feats = sorted(effect_sizes, key=lambda c: -effect_sizes[c])
            distinguishing = sorted_feats[: cfg.n_distinguishing_features]

            # Build human-readable description
            mode_name = f"Mode_{lbl}"
            description = _describe_mode(
                mode_name, centroid, global_means, global_stds, distinguishing
            )

            # Silhouette-based confidence proxy
            confidence = _cluster_confidence(X, labels, lbl)

            mode = OperationalMode(
                label=mode_name,
                description=description,
                centroid=centroid,
                member_count=member_count,
                total_count=total_count,
                distinguishing_features=distinguishing,
                confidence=confidence,
                metadata={
                    "method": method_used,
                    "cluster_id": int(lbl),
                },
            )
            result.modes.append(mode)

            # Assign label string for transition analysis
            indices = np.where(mask)[0]
            for i in indices:
                mode_label_list[i] = mode_name

        # Sort modes by prevalence (most common first)
        result.modes.sort(key=lambda m: -m.prevalence)
        result.mode_labels = mode_label_list

        self._log_progress(
            "Mode analysis complete: %d operational modes discovered.", len(result.modes)
        )
        return result

    # ------------------------------------------------------------------

    def _cluster(
        self, X: np.ndarray, cfg: Any
    ) -> tuple[np.ndarray | None, str]:
        """Run HDBSCAN first; fall back to KMeans if needed."""
        # --- HDBSCAN ---
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=cfg.min_cluster_size,
                min_samples=cfg.min_samples,
                prediction_data=True,
            )
            labels = clusterer.fit_predict(X)
            n_clusters = len(set(labels) - {-1})
            if n_clusters >= 2:
                return labels, "hdbscan"
            self._log_progress("HDBSCAN found %d clusters — falling back to KMeans.", n_clusters)
        except ImportError:
            self.logger.info("hdbscan not installed — using KMeans fallback.")
        except Exception as exc:
            self.logger.debug("HDBSCAN failed: %s — falling back to KMeans.", exc)

        # --- KMeans with BIC proxy (inertia elbow via gap) ---
        return self._kmeans_best_k(X, cfg)

    def _kmeans_best_k(
        self, X: np.ndarray, cfg: Any
    ) -> tuple[np.ndarray | None, str]:
        """Select optimal k via silhouette score; return labels."""
        try:
            from sklearn.cluster import KMeans
            from sklearn.metrics import silhouette_score
        except ImportError:
            self.logger.warning("scikit-learn not installed — mode analysis unavailable.")
            return None, "none"

        max_k = min(cfg.kmeans_max_k, len(X) // max(cfg.min_cluster_size, 2))
        if max_k < 2:
            return None, "none"

        best_score = -1.0
        best_labels = None

        for k in range(2, max_k + 1):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(X)
                if len(np.unique(labels)) < 2:
                    continue
                score = float(silhouette_score(X, labels, sample_size=min(1000, len(X))))
                if score > best_score:
                    best_score = score
                    best_labels = labels
            except Exception:
                continue

        if best_labels is None or best_score < 0.1:
            return None, "none"

        return best_labels, f"kmeans_k{len(np.unique(best_labels))}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _describe_mode(
    name: str,
    centroid: dict[str, float],
    global_means: dict[str, float],
    global_stds: dict[str, float],
    features: list[str],
) -> str:
    """Build a plain-language description of a mode from its dominant features."""
    parts = []
    for feat in features:
        mean = global_means.get(feat, 0.0)
        std = global_stds.get(feat, 1.0)
        val = centroid.get(feat, mean)
        delta = val - mean
        if std > 0:
            z = delta / std
        else:
            z = 0.0

        if abs(z) < 0.3:
            level = "typical"
        elif z > 1.5:
            level = "high"
        elif z > 0.5:
            level = "above-average"
        elif z < -1.5:
            level = "low"
        else:
            level = "below-average"

        parts.append(f"{level} {feat} ({val:.3g})")

    return f"{name}: " + ", ".join(parts) + "."


def _cluster_confidence(
    X: np.ndarray, labels: np.ndarray, target_label: int
) -> float:
    """Estimate confidence for a cluster via intra-cluster vs inter-cluster distance."""
    try:
        from sklearn.metrics import silhouette_samples

        unique = set(labels) - {-1}
        if len(unique) < 2:
            return 0.5

        scores = silhouette_samples(X, labels)
        mask = labels == target_label
        if mask.sum() == 0:
            return 0.5
        cluster_score = float(np.mean(scores[mask]))
        # Silhouette in [-1, 1]; map to [0, 1]
        return float(np.clip((cluster_score + 1.0) / 2.0, 0.0, 1.0))
    except Exception:
        return 0.5
