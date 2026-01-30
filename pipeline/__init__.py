"""
Pipeline module for Protocol2USDM.

This module provides a phase registry pattern for orchestrating
extraction phases in a clean, extensible way.
"""

from .phase_registry import PhaseRegistry, phase_registry
from .base_phase import BasePhase, PhaseResult
from .orchestrator import PipelineOrchestrator

# Import phases to trigger registration
from . import phases as _phases  # noqa

__all__ = [
    'PhaseRegistry',
    'phase_registry',
    'BasePhase',
    'PhaseResult',
    'PipelineOrchestrator',
]
