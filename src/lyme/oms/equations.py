"""
OMS Equation Derivation.

Derives mathematical equations explaining target variables from their causal drivers.
Supports time-lagged linear, multiple linear, and polynomial regressions.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from .config import OMSConfig
from .models import MathEquation

logger = logging.getLogger(__name__)


class EquationDeriver:
    """Derives interpretable equations using regression analysis."""

    def __init__(self, config: OMSConfig) -> None:
        self.config = config

    def derive_equations(
        self,
        variable_names: list[str],
        relationships: list[Any],
        modes: list[Any],
        df: pd.DataFrame | None = None,
    ) -> list[MathEquation]:
        """Derive math models for influenced variables.

        Parameters:
            variable_names: All variables.
            relationships: Level-2 relationships.
            modes: Level-4 operational modes.
            df: Optional aligned state matrix.

        Returns:
            A list of MathEquation dataclasses.
        """
        equations: list[MathEquation] = []
        
        # 1. Identify causal parents for each variable
        # parents[target] = list of relationships (source -> target)
        parents: dict[str, list[Any]] = {}
        for r in relationships:
            rtype = getattr(r.relation_type, "value", str(r.relation_type))
            if rtype in ("influences", "triggers", "threshold") and r.confidence >= self.config.min_influence_confidence:
                parents.setdefault(r.target, []).append(r)

        # Calculate average dt if dataframe is available
        dt = 1.0
        if df is not None and "timestamp" in df.columns and len(df) > 1:
            dt_diff = df["timestamp"].diff().dropna()
            if len(dt_diff) > 0:
                dt = float(dt_diff.median())
                if dt <= 0:
                    dt = 1.0

        for target in variable_names:
            target_rels = parents.get(target, [])
            if not target_rels:
                continue

            eq = None
            if df is not None:
                eq = self._derive_from_data(target, target_rels, df, dt)
            
            if eq is None and modes:
                eq = self._derive_from_centroids(target, target_rels, modes)

            if eq is not None:
                equations.append(eq)

        return equations

    # ------------------------------------------------------------------

    def _derive_from_data(
        self, target: str, target_rels: list[Any], df: pd.DataFrame, dt: float
    ) -> MathEquation | None:
        """Fit OLS linear/polynomial models on the time-series state matrix."""
        if target not in df.columns:
            return None

        # Build feature matrix of lagged parents
        temp_df = pd.DataFrame({target: df[target]})
        lag_steps_map = {}
        predictor_names = []

        for r in target_rels:
            source = r.source
            if source not in df.columns:
                continue

            # Estimate lag steps
            best_lag = r.metadata.get("best_lag")
            if best_lag is not None and isinstance(best_lag, (int, float)) and best_lag > 0:
                lag_steps = int(best_lag)
            else:
                lag_steps = int(round(r.estimated_lag / dt))

            lag_steps = max(0, lag_steps)
            col_name = f"{source}_lag_{lag_steps}"
            temp_df[col_name] = df[source].shift(lag_steps)
            lag_steps_map[source] = lag_steps
            predictor_names.append((source, col_name))

        # Drop NaNs due to shifting
        temp_df = temp_df.dropna()
        if len(temp_df) < 15:
            return None

        y = temp_df[target]
        X_cols = [col_name for _, col_name in predictor_names]
        X = temp_df[X_cols]

        try:
            # 1. Try Multiple Linear Regression
            X_with_const = sm.add_constant(X)
            model = sm.OLS(y, X_with_const).fit()
            
            # Filter non-significant coefficients (except constant/intercept)
            significant_predictors = []
            for source, col_name in predictor_names:
                p_val = model.pvalues.get(col_name, 1.0)
                if p_val <= self.config.equation_significance_pval:
                    significant_predictors.append((source, col_name))

            # Re-fit with significant predictors only if subset changed
            if len(significant_predictors) < len(predictor_names) and len(significant_predictors) > 0:
                X_sig_cols = [col_name for _, col_name in significant_predictors]
                X_sig = temp_df[X_sig_cols]
                X_with_const = sm.add_constant(X_sig)
                model = sm.OLS(y, X_with_const).fit()
                active_predictors = significant_predictors
            else:
                active_predictors = predictor_names

            if len(active_predictors) == 0:
                return None

            r2 = model.rsquared
            mse = model.mse_resid
            intercept = model.params.get("const", 0.0)

            # Coefficients
            coeffs = {}
            for source, col_name in active_predictors:
                coeffs[source] = model.params.get(col_name, 0.0)

            # Try Quadratic Polynomial Fit if single predictor and R2 is moderate
            is_poly = False
            if len(active_predictors) == 1 and self.config.max_poly_degree >= 2:
                source, col_name = active_predictors[0]
                x_val = temp_df[col_name]
                # fit quadratic: y = a*x^2 + b*x + c
                poly_coeffs = np.polyfit(x_val, y, 2)
                poly_pred = np.polyval(poly_coeffs, x_val)
                # Compute r2
                poly_r2 = float(stats.pearsonr(poly_pred, y)[0] ** 2)
                
                # If polynomial significantly improves R2, choose it
                if poly_r2 > r2 + 0.05:
                    r2 = poly_r2
                    mse = float(np.mean((y - poly_pred) ** 2))
                    intercept = float(poly_coeffs[2])
                    coeffs = {
                        f"{source}": float(poly_coeffs[1]),
                        f"{source}^2": float(poly_coeffs[0]),
                    }
                    is_poly = True

            # If model is not predictive enough, reject
            if r2 < self.config.min_r2_score:
                return None

            # Build Equation string
            eq_parts = [f"{intercept:.4g}"]
            for key, val in coeffs.items():
                sign = "+" if val >= 0 else "-"
                val_abs = abs(val)
                
                # Format predictor term
                if key.endswith("^2"):
                    base = key[:-2]
                    lag = lag_steps_map.get(base, 0)
                    lag_str = f"[t-{lag}]" if lag > 0 else ""
                    term = f"{base}{lag_str}²"
                else:
                    lag = lag_steps_map.get(key, 0)
                    lag_str = f"[t-{lag}]" if lag > 0 else ""
                    term = f"{key}{lag_str}"
                    
                eq_parts.append(f" {sign} {val_abs:.4g} * {term}")

            equation_str = f"{target} = " + "".join(eq_parts)

            return MathEquation(
                target_variable=target,
                equation_str=equation_str,
                coefficients=coeffs,
                intercept=intercept,
                r2=r2,
                mse=mse,
                is_polynomial=is_poly,
                lag_steps=lag_steps_map,
            )
        except Exception as e:
            logger.warning(f"Failed regression for target {target}: {e}")
            return None

    def _derive_from_centroids(
        self, target: str, target_rels: list[Any], modes: list[Any]
    ) -> MathEquation | None:
        """Derive an approximate linear regression equation using Mode centroids."""
        # Simple centroid-based linear fit for the single primary influencer
        # Sort relationships by confidence to find the primary influencer
        target_rels.sort(key=lambda r: -r.confidence)
        primary = target_rels[0]
        source = primary.source

        # Extract centroids coordinates
        x_pts = []
        y_pts = []
        for m in modes:
            if source in m.centroid and target in m.centroid:
                x_pts.append(m.centroid[source])
                y_pts.append(m.centroid[target])

        if len(x_pts) < 2:
            return None

        # Check if x values vary, if all x values are identical, regression fails
        if max(x_pts) - min(x_pts) < 1e-6:
            return None

        try:
            slope, intercept, r_val, p_val, std_err = stats.linregress(x_pts, y_pts)
            
            # Handle nan values for 2-point fits
            r2 = r_val ** 2 if not np.isnan(r_val) else 1.0
            mse = (std_err ** 2) if (std_err is not None and not np.isnan(std_err)) else 0.0

            if np.isnan(slope) or np.isnan(intercept):
                return None

            if r2 < self.config.min_r2_score:
                return None

            sign = "+" if slope >= 0 else "-"
            equation_str = f"{target} = {intercept:.4g} {sign} {abs(slope):.4g} * {source}"

            return MathEquation(
                target_variable=target,
                equation_str=equation_str,
                coefficients={source: slope},
                intercept=intercept,
                r2=r2,
                mse=mse,
                is_polynomial=False,
                lag_steps={source: 0},
            )
        except Exception:
            return None
