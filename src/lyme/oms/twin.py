"""
OMS Digital Twin.

Implements the executable DigitalTwin simulator capable of running step simulations
using the derived equations and state transition rules.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import MathEquation, StateMachine

logger = logging.getLogger(__name__)


class DigitalTwin:
    """An executable simulation of the synthesized system.

    Maintains variables, history buffers for lagged relationships, evaluates
    equations, and updates operational state transitions.
    """

    def __init__(
        self,
        variable_names: list[str],
        equations: list[MathEquation],
        state_machine: StateMachine,
        initial_state_label: str | None = None,
    ) -> None:
        self.variable_names = variable_names
        self.equations = equations
        self.state_machine = state_machine
        
        # Build maps for evaluation
        self.equations_map = {eq.target_variable: eq for eq in equations}
        
        # Determine max history needed
        self.max_lag_steps = 0
        for eq in equations:
            for parent, lag in eq.lag_steps.items():
                self.max_lag_steps = max(self.max_lag_steps, lag)

        # Set initial operational mode
        self.current_state_label = initial_state_label
        if not self.current_state_label and state_machine.states:
            # Default to the most prevalent state
            most_prevalent = max(state_machine.states, key=lambda s: s.prevalence)
            self.current_state_label = most_prevalent.original_label

        self.state: dict[str, float] = {}
        self.history: dict[str, list[float]] = {}
        self.reset()

    def reset(self, initial_values: dict[str, float] | None = None) -> None:
        """Reset the simulation state and history buffers."""
        self.state = {}
        
        # Initialize state with defaults (0.0 or centroids of current state)
        current_centroid = {}
        if self.state_machine and self.current_state_label:
            for s in self.state_machine.states:
                if s.original_label == self.current_state_label:
                    current_centroid = s.centroid
                    break

        for var in self.variable_names:
            if initial_values and var in initial_values:
                self.state[var] = initial_values[var]
            else:
                self.state[var] = current_centroid.get(var, 0.0)

        # Reset history
        self.history = {var: [self.state[var]] for var in self.variable_names}

    def step(self, inputs: dict[str, float]) -> dict[str, float]:
        """Perform a single simulation step.

        Parameters:
            inputs: Dict of exogenous control variables (e.g. motor_speed).

        Returns:
            The updated system state dictionary.
        """
        # 1. Update exogenous inputs in state
        for var, val in inputs.items():
            if var in self.state:
                self.state[var] = val

        # 2. Maintain history buffers
        for var in self.variable_names:
            self.history.setdefault(var, []).append(self.state[var])
            # Keep history size bounded to max_lag_steps + 1
            if len(self.history[var]) > self.max_lag_steps + 1:
                self.history[var].pop(0)

        # 3. Evaluate equations to update endogenous variables
        # Iterate over equations. Since equations can be chained, we evaluate them.
        # To avoid order-of-evaluation issues, we evaluate based on previous step history
        # for lags > 0, and use newly calculated values for immediate effects (lag = 0).
        next_state = self.state.copy()

        for target, eq in self.equations_map.items():
            if target in inputs:
                continue
            val = eq.intercept
            
            if eq.is_polynomial:
                # Polynomial model (quadratic for a single parent)
                # coefficients has keys e.g. "motor_speed" and "motor_speed^2"
                for term, coeff in eq.coefficients.items():
                    if term.endswith("^2"):
                        base = term[:-2]
                        lag = eq.lag_steps.get(base, 0)
                        x_val = self._get_historical_value(base, lag)
                        val += coeff * (x_val ** 2)
                    else:
                        lag = eq.lag_steps.get(term, 0)
                        x_val = self._get_historical_value(term, lag)
                        val += coeff * x_val
            else:
                # Standard multiple linear model
                for predictor, coeff in eq.coefficients.items():
                    lag = eq.lag_steps.get(predictor, 0)
                    x_val = self._get_historical_value(predictor, lag)
                    val += coeff * x_val

            next_state[target] = val

        self.state = next_state

        # 4. Check State Machine transitions
        if self.state_machine and self.current_state_label:
            # Find outgoing transitions
            out_trans = [
                t
                for t in self.state_machine.transitions
                if t["from_mode"] == self.current_state_label
            ]
            
            # Check rules
            triggered_transition = None
            max_prob = -1.0
            
            for t in out_trans:
                trigger = t["trigger_rule"]
                if self._evaluate_trigger(trigger):
                    # If trigger is satisfied, choose transition with highest probability
                    if t["probability"] > max_prob:
                        triggered_transition = t
                        max_prob = t["probability"]

            if triggered_transition:
                self.current_state_label = triggered_transition["to_mode"]

        return self.state.copy()

    # ------------------------------------------------------------------

    def _get_historical_value(self, var: str, lag_steps: int) -> float:
        """Retrieve variable value at t - lag_steps."""
        buf = self.history.get(var, [])
        if not buf:
            return self.state.get(var, 0.0)
            
        # Index from end: -1 is current step t, -2 is t-1, and so on.
        idx = -1 - lag_steps
        try:
            return buf[idx]
        except IndexError:
            # Fallback to the oldest available history value or current state
            return buf[0] if buf else self.state.get(var, 0.0)

    def _evaluate_trigger(self, trigger_rule: str) -> bool:
        """Evaluate a transition trigger rule (e.g., 'motor_speed > 700') in current state."""
        if trigger_rule == "N/A" or not trigger_rule:
            return False

        try:
            parts = trigger_rule.split()
            if len(parts) != 3:
                return False

            var, op, threshold_str = parts[0], parts[1], parts[2]
            if var not in self.state:
                return False

            val = self.state[var]
            threshold = float(threshold_str)

            if op == ">":
                return val > threshold
            elif op == ">=":
                return val >= threshold
            elif op == "<":
                return val < threshold
            elif op == "<=":
                return val <= threshold
            elif op == "==":
                return val == threshold
        except Exception:
            pass

        return False
