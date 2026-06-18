"""
Operational Model Synthesizer (OMS) Package.

Cognis OS Component 3 — Synthesizes discovered relationships, dependencies, rules,
and operational states into a unified operational theory and executable Digital Twin.
"""

from __future__ import annotations

from .config import OMSConfig
from .models import (
    Subsystem,
    InfluenceChain,
    FeedbackLoop,
    StateSummary,
    StateMachine,
    MathEquation,
    OperationalTheory,
)
from .synthesizer import OperationalModelSynthesizer
from .twin import DigitalTwin
from .exporters import DigitalTwinPythonExporter, JSONTheoryExporter, MarkdownTheoryExporter

__all__ = [
    "OMSConfig",
    "Subsystem",
    "InfluenceChain",
    "FeedbackLoop",
    "StateSummary",
    "StateMachine",
    "MathEquation",
    "OperationalTheory",
    "OperationalModelSynthesizer",
    "DigitalTwin",
    "MarkdownTheoryExporter",
    "JSONTheoryExporter",
    "DigitalTwinPythonExporter",
]
