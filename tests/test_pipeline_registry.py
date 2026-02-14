"""
Unit tests for pipeline phase registry, orchestrator, and promotion rules.

Tests phase registration, dependency resolution, and extension→USDM promotion.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhaseRegistry:
    """Test the PhaseRegistry class."""

    def test_registry_has_all_phases(self):
        """All 14 expected phases are registered."""
        from pipeline import phase_registry
        names = phase_registry.get_names()
        expected = [
            "metadata", "narrative", "objectives", "studydesign",
            "eligibility", "interventions", "scheduling", "execution",
            "procedures", "advanced", "amendmentdetails", "sap", "sites",
            "docstructure",
        ]
        for phase_name in expected:
            assert phase_registry.has(phase_name), f"Phase '{phase_name}' not registered"
        assert len(phase_registry) >= 14

    def test_phases_have_config(self):
        """Each registered phase has a valid config."""
        from pipeline import phase_registry
        for phase in phase_registry.get_all():
            assert phase.config.name, "Phase missing name"
            assert phase.config.phase_number >= 0, f"Phase {phase.config.name} has invalid number"

    def test_phase_ordering(self):
        """Phases are returned in phase_number order."""
        from pipeline import phase_registry
        phases = phase_registry.get_all()
        numbers = [p.config.phase_number for p in phases]
        assert numbers == sorted(numbers), "Phases not in order"

    def test_get_by_name(self):
        """Can retrieve a phase by name (case-insensitive)."""
        from pipeline import phase_registry
        meta = phase_registry.get("metadata")
        assert meta is not None
        assert meta.config.name.lower() == "metadata"
        # Case insensitive
        assert phase_registry.get("METADATA") is not None

    def test_contains(self):
        """'in' operator works on registry."""
        from pipeline import phase_registry
        assert "metadata" in phase_registry
        assert "nonexistent" not in phase_registry

    def test_phase_dependencies(self):
        """Phases with dependencies reference valid phase names."""
        from pipeline import phase_registry
        all_names = set(phase_registry.get_names())
        for phase in phase_registry.get_all():
            deps = getattr(phase.config, 'dependencies', []) or []
            for dep in deps:
                assert dep.lower() in all_names, (
                    f"Phase '{phase.config.name}' depends on '{dep}' which is not registered"
                )


class TestPromotionRules:
    """Test extension→USDM promotion rules."""

    def test_promotion_function_importable(self):
        """Promotion function is importable."""
        from pipeline.promotion import promote_extensions_to_usdm
        assert callable(promote_extensions_to_usdm)

    def test_promotion_noop_on_empty(self):
        """Promotion is a no-op on empty USDM (no crash)."""
        from pipeline.promotion import promote_extensions_to_usdm
        combined = {"study": {"versions": [{"studyDesigns": [{}]}]}}
        promote_extensions_to_usdm(combined)  # Should not raise

    def test_promotion_noop_on_missing_population(self):
        """Promotion handles missing population gracefully."""
        from pipeline.promotion import promote_extensions_to_usdm
        combined = {
            "study": {
                "versions": [{
                    "studyDesigns": [{"id": "sd1", "activities": []}]
                }]
            }
        }
        promote_extensions_to_usdm(combined)  # Should not raise


class TestOrchestratorInit:
    """Test PipelineOrchestrator initialization (no LLM calls)."""

    def test_orchestrator_creation(self):
        """Orchestrator can be created with usage_tracker."""
        from pipeline import PipelineOrchestrator
        from providers.tracker import TokenUsageTracker
        tracker = TokenUsageTracker()
        orch = PipelineOrchestrator(usage_tracker=tracker)
        assert orch.usage_tracker is tracker

    def test_orchestrator_creation_no_tracker(self):
        """Orchestrator works without usage_tracker."""
        from pipeline import PipelineOrchestrator
        orch = PipelineOrchestrator()
        assert orch.usage_tracker is None

    def test_orchestrator_accepts_registry(self):
        """Orchestrator can use an injected registry instead of global."""
        from pipeline import PipelineOrchestrator
        from pipeline.phase_registry import create_registry
        reg = create_registry()
        orch = PipelineOrchestrator(registry=reg)
        assert orch._registry is reg

    def test_orchestrator_defaults_to_global_registry(self):
        """Without injection, orchestrator uses global phase_registry."""
        from pipeline import PipelineOrchestrator, phase_registry
        orch = PipelineOrchestrator()
        assert orch._registry is phase_registry


# ============================================================================
# W-HIGH-4: Dependency Injection for Singletons
# ============================================================================

class TestRegistryDI:
    """PhaseRegistry DI: create_registry, reset."""

    def test_create_registry_returns_fresh(self):
        from pipeline.phase_registry import create_registry
        reg = create_registry()
        assert len(reg) == 0

    def test_registry_reset(self):
        from pipeline.phase_registry import create_registry
        reg = create_registry()
        # Manually add a dummy
        from unittest.mock import MagicMock
        mock_phase = MagicMock()
        mock_phase.config.name = "dummy"
        mock_phase.config.phase_number = 99
        reg.register(mock_phase)
        assert len(reg) == 1
        reg.reset()
        assert len(reg) == 0

    def test_global_registry_not_affected_by_create(self):
        from pipeline.phase_registry import phase_registry, create_registry
        original_len = len(phase_registry)
        reg = create_registry()
        assert len(reg) == 0
        assert len(phase_registry) == original_len


class TestEVSClientDI:
    """EVS client DI: set_client, reset_client."""

    def test_set_and_reset_client(self):
        from core.evs_client import get_client, set_client, reset_client
        from unittest.mock import MagicMock
        mock = MagicMock()
        set_client(mock)
        assert get_client() is mock
        reset_client()
        # After reset, get_client creates a new real instance
        client = get_client()
        assert client is not mock
        reset_client()  # cleanup

    def test_reset_client_allows_fresh_instance(self):
        from core.evs_client import get_client, reset_client
        c1 = get_client()
        reset_client()
        c2 = get_client()
        assert c1 is not c2
        reset_client()  # cleanup


class TestUsageTrackerDI:
    """TokenUsageTracker DI: create_tracker, set/reset."""

    def test_create_tracker_fresh(self):
        from providers.tracker import create_tracker
        t = create_tracker()
        assert t.call_count == 0
        assert t.total_input_tokens == 0

    def test_set_and_reset_usage_tracker(self):
        from providers.tracker import (
            usage_tracker, set_usage_tracker, reset_usage_tracker, create_tracker,
        )
        original = usage_tracker
        custom = create_tracker()
        custom.add_usage(100, 50)
        set_usage_tracker(custom)

        from providers.tracker import usage_tracker as current
        assert current.call_count == 1

        reset_usage_tracker()
        from providers.tracker import usage_tracker as after_reset
        assert after_reset.call_count == 0
