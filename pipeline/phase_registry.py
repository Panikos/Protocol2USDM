"""
Phase registry for extraction phases.

Provides a central registry for all extraction phases,
enabling the orchestrator to discover and run phases dynamically.
"""

from typing import Dict, List, Optional, Type
from .base_phase import BasePhase
import logging

logger = logging.getLogger(__name__)


class PhaseRegistry:
    """
    Registry for extraction phases.
    
    Phases register themselves with a name, and the orchestrator
    queries the registry to get phases to run.
    """
    
    def __init__(self):
        self._phases: Dict[str, BasePhase] = {}
        self._order: List[str] = []
    
    def register(self, phase: BasePhase) -> None:
        """
        Register a phase instance.
        
        Args:
            phase: Phase instance to register
        """
        name = phase.config.name.lower()
        if name in self._phases:
            logger.warning(f"Phase '{name}' already registered, replacing")
        self._phases[name] = phase
        if name not in self._order:
            self._order.append(name)
        # Re-sort by phase number
        self._order.sort(key=lambda n: self._phases[n].config.phase_number)
    
    def get(self, name: str) -> Optional[BasePhase]:
        """Get a phase by name."""
        return self._phases.get(name.lower())
    
    def get_all(self) -> List[BasePhase]:
        """Get all registered phases in order."""
        return [self._phases[name] for name in self._order]
    
    def get_names(self) -> List[str]:
        """Get all registered phase names in order."""
        return list(self._order)
    
    def has(self, name: str) -> bool:
        """Check if a phase is registered."""
        return name.lower() in self._phases
    
    def __contains__(self, name: str) -> bool:
        return self.has(name)
    
    def __len__(self) -> int:
        return len(self._phases)
    
    def reset(self) -> None:
        """Clear all registered phases. Useful in tests."""
        self._phases.clear()
        self._order.clear()


# Global registry instance
phase_registry = PhaseRegistry()


def create_registry() -> PhaseRegistry:
    """Create a fresh PhaseRegistry instance (useful in tests for isolation)."""
    return PhaseRegistry()


def register_phase(phase: BasePhase) -> BasePhase:
    """
    Register a phase with the global registry.
    
    Can be used as a decorator or called directly.
    """
    phase_registry.register(phase)
    return phase
