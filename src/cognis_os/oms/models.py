"""
OMS Data Models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Subsystem:
    """A logical grouping of system variables representing a physical or functional component.

    Attributes:
        name: Name of the subsystem (e.g., "Thermal Subsystem").
        variables: List of variable names in this subsystem.
        description: Description of the subsystem's role and variables.
    """

    name: str
    variables: list[str]
    description: str


@dataclass
class InfluenceChain:
    """A causal pathway trace of directed influence through the system variables.

    Attributes:
        variables: Sequence of variable names in the chain (e.g., [A, B, C]).
        lags: Time lags between adjacent steps.
        cumulative_lag: Sum of all step lags in original timestamp units.
        confidence: Combined confidence score of the chain in [0, 1].
        relation_types: Relation categories for each step.
    """

    variables: list[str]
    lags: list[float]
    cumulative_lag: float
    confidence: float
    relation_types: list[str]

    def to_text(self) -> str:
        """Render the chain in an arrow format with lag annotations."""
        parts = []
        for i, var in enumerate(self.variables):
            if i == 0:
                parts.append(var)
            else:
                lag = self.lags[i - 1]
                parts.append(f" ──(lag={lag:.1f})──► {var}")
        return "".join(parts)


@dataclass
class FeedbackLoop:
    """A cyclic causal structure where a variable's behavior loops back to affect itself.

    Attributes:
        variables: Sequence of variable names forming the cycle (ends with the starting variable).
        loop_type: "positive" (reinforcing/runaway) or "negative" (balancing/self-stabilizing).
        confidence: Average confidence of the links in the cycle.
        description: Human-readable explanation of the cycle.
    """

    variables: list[str]
    loop_type: str
    confidence: float
    description: str


@dataclass
class StateSummary:
    """Descriptive summary of a system operational state.

    Attributes:
        original_label: The raw cluster name from KSE (e.g., "Mode_0").
        name: Synthesized semantic name (e.g., "Startup State").
        description: Readable details summarizing the conditions of the state.
        prevalence: Fraction of time the system is in this state.
        centroid: Typical variable values in this state.
        distinguishing_features: Variables that differentiate this state.
    """

    original_label: str
    name: str
    description: str
    prevalence: float
    centroid: dict[str, float]
    distinguishing_features: list[str]


@dataclass
class StateMachine:
    """Operational state transition network.

    Attributes:
        states: List of state summaries.
        transitions: List of transitions, each containing source/target names, probability, and trigger rules.
        mermaid_diagram: Mermaid code representing the state transition graph.
    """

    states: list[StateSummary] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    mermaid_diagram: str = ""


@dataclass
class MathEquation:
    """An empirical math equation explaining an endogenous variable.

    Attributes:
        target_variable: Name of variable being explained.
        equation_str: Human-readable equation (e.g., "temp = 25.10 + 0.080 * current_draw").
        coefficients: Coefficients mapping predictor variables to values.
        intercept: Constant intercept.
        r2: R-squared score.
        mse: Mean squared error.
        is_polynomial: True if polynomial models were preferred.
        lag_steps: Dictionary of time step delays for each predictor variable.
    """

    target_variable: str
    equation_str: str
    coefficients: dict[str, float]
    intercept: float
    r2: float
    mse: float
    is_polynomial: bool = False
    lag_steps: dict[str, int] = field(default_factory=dict)


@dataclass
class OperationalTheory:
    """The synthesized operational theory representing the entire system operational model.

    Attributes:
        variable_names: Names of all variables in the system.
        consolidated_variables: Mapping of canonical variable name to duplicate/alias names.
        subsystems: Discovered subsystem components.
        influence_chains: Key causal pathways.
        feedback_loops: Discovered feedback cycles.
        state_machine: Operational states and transitions.
        equations: Derived mathematical equations.
        explanations: Human-readable explanations.
        resolved_contradictions: Reconciled contradictions.
        metadata: Metadata (timestamps, etc.).
    """

    variable_names: list[str] = field(default_factory=list)
    consolidated_variables: dict[str, list[str]] = field(default_factory=dict)
    subsystems: list[Subsystem] = field(default_factory=list)
    influence_chains: list[InfluenceChain] = field(default_factory=list)
    feedback_loops: list[FeedbackLoop] = field(default_factory=list)
    state_machine: StateMachine = field(default_factory=StateMachine)
    equations: list[MathEquation] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    resolved_contradictions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
