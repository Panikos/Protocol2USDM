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
