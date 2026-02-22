"""
Tests for hallucination risk fixes #1 and #2.

#1: _create_populations_from_estimands() — uses extracted text, not boilerplate
#2: ARS default operations — no fabricated P-value for unknown methods
"""

import pytest


# ============================================================================
# Fix #1: Population creation from estimands — no boilerplate
# ============================================================================

class TestCreatePopulationsFromEstimands:
    """Verify populations use actual estimand text, not hardcoded boilerplate."""

    def _create(self, estimands):
        from pipeline.integrations import _create_populations_from_estimands
        return _create_populations_from_estimands(estimands)

    def test_uses_actual_estimand_text(self):
        """Population text should come from the estimand, not a template."""
        estimands = [{
            "id": "est_1",
            "analysisPopulation": "All enrolled subjects who received at least one dose of WTX101",
            "populationSummary": "Full Analysis Set",
        }]
        pops = self._create(estimands)
        assert len(pops) == 1
        # Text should be the actual estimand text, not boilerplate
        assert "WTX101" in pops[0]["text"]
        assert "randomized treatment assignment" not in pops[0]["text"]

    def test_no_boilerplate_itt_definition(self):
        """ITT population should NOT get generic 'randomized participants' boilerplate."""
        estimands = [{
            "id": "est_1",
            "analysisPopulation": "Intent-to-Treat Population: subjects who took study drug",
        }]
        pops = self._create(estimands)
        assert len(pops) == 1
        assert pops[0]["populationType"] == "Efficacy"
        # Should use the extracted text, not boilerplate
        assert "subjects who took study drug" in pops[0]["text"]
        assert "analyzed according to randomized treatment assignment" not in pops[0]["text"]

    def test_deduplicates_populations(self):
        """Same population referenced by two estimands should appear once."""
        estimands = [
            {"id": "est_1", "analysisPopulation": "ITT Population"},
            {"id": "est_2", "analysisPopulation": "ITT Population"},
        ]
        pops = self._create(estimands)
        assert len(pops) == 1

    def test_empty_population_text_skipped(self):
        """Estimands with no population text should not create entities."""
        estimands = [
            {"id": "est_1", "analysisPopulation": "", "populationSummary": ""},
        ]
        pops = self._create(estimands)
        assert len(pops) == 0

    def test_no_auto_safety_population(self):
        """Safety population should NOT be auto-added just because ITT exists."""
        estimands = [{
            "id": "est_1",
            "analysisPopulation": "Intent-to-Treat Population",
        }]
        pops = self._create(estimands)
        # Should only have 1 population (ITT), not auto-add Safety
        assert len(pops) == 1
        assert pops[0]["populationType"] == "Efficacy"

    def test_multiple_distinct_populations(self):
        """Multiple distinct population references should each create an entity."""
        estimands = [
            {"id": "est_1", "analysisPopulation": "Full Analysis Set (FAS)"},
            {"id": "est_2", "analysisPopulation": "Safety Population"},
        ]
        pops = self._create(estimands)
        assert len(pops) == 2
        types = {p["populationType"] for p in pops}
        assert "Efficacy" in types
        assert "Safety" in types

    def test_classifies_pk_population(self):
        """PK population text should be classified correctly."""
        estimands = [{
            "id": "est_1",
            "analysisPopulation": "Pharmacokinetic Analysis Set",
        }]
        pops = self._create(estimands)
        assert len(pops) == 1
        assert pops[0]["populationType"] == "PK"

    def test_fallback_to_population_summary(self):
        """If analysisPopulation is empty, should use populationSummary."""
        estimands = [{
            "id": "est_1",
            "analysisPopulation": "",
            "populationSummary": "All participants completing the dose escalation phase",
        }]
        pops = self._create(estimands)
        assert len(pops) == 1
        assert "dose escalation" in pops[0]["text"]

    def test_all_entities_have_required_fields(self):
        """Every population entity must have id, name, instanceType."""
        estimands = [
            {"id": "est_1", "analysisPopulation": "Safety Set"},
        ]
        pops = self._create(estimands)
        assert len(pops) == 1
        pop = pops[0]
        assert pop["id"]  # non-empty UUID
        assert pop["name"] == "Safety Set"
        assert pop["instanceType"] == "AnalysisPopulation"
        assert pop["text"] == "Safety Set"


# ============================================================================
# Fix #1b: Descriptive studies skip population creation from estimands
# ============================================================================

class TestDescriptiveStudySkipsPopulationCreation:
    """Verify that descriptive studies don't create populations from estimand refs."""

    def test_get_analysis_approach_from_design(self):
        """Helper correctly reads x-analysisApproach extension attribute."""
        from pipeline.integrations import _get_analysis_approach_from_design
        design = {
            "extensionAttributes": [{
                "url": "http://www.example.org/usdm/extensions/x-analysisApproach",
                "valueString": "descriptive",
            }]
        }
        assert _get_analysis_approach_from_design(design) == "descriptive"

    def test_get_analysis_approach_missing(self):
        """Missing extension returns 'unknown'."""
        from pipeline.integrations import _get_analysis_approach_from_design
        assert _get_analysis_approach_from_design({}) == "unknown"

    def test_descriptive_study_skips_population_fallback(self):
        """reconcile_estimand_population_refs should skip fallback for descriptive studies."""
        from pipeline.integrations import reconcile_estimand_population_refs
        study_design = {
            "estimands": [{"id": "est_1", "analysisPopulation": "ITT Population"}],
            "extensionAttributes": [{
                "url": "http://www.example.org/usdm/extensions/x-analysisApproach",
                "valueString": "descriptive",
            }],
        }
        reconcile_estimand_population_refs(study_design)
        # Should NOT have created any populations
        assert study_design.get("analysisPopulations") is None

    def test_confirmatory_study_creates_populations(self):
        """reconcile_estimand_population_refs should create populations for confirmatory studies."""
        from pipeline.integrations import reconcile_estimand_population_refs
        study_design = {
            "estimands": [{
                "id": "est_1",
                "analysisPopulation": "Intent-to-Treat Population",
                "populationSummary": "All randomized subjects",
            }],
            "extensionAttributes": [{
                "url": "http://www.example.org/usdm/extensions/x-analysisApproach",
                "valueString": "confirmatory",
            }],
        }
        reconcile_estimand_population_refs(study_design)
        pops = study_design.get("analysisPopulations", [])
        assert len(pops) == 1
        assert "Intent-to-Treat" in pops[0]["name"]


# ============================================================================
# Fix #2: ARS default operations — no fabricated P-value
# ============================================================================

class TestARSDefaultOperations:
    """Verify ARS generator doesn't fabricate P-value for unknown methods."""

    def _get_ops(self, method_name):
        from extraction.conditional.ars_generator import ARSGenerator
        gen = ARSGenerator(sap_data={}, study_name="Test")
        return gen._get_operations_for_method(method_name)

    def test_unknown_method_no_pvalue(self):
        """Unknown method should NOT get a fabricated P-value operation."""
        ops = self._get_ops("Descriptive Summary Statistics")
        op_names = [op.name for op in ops]
        assert "PValue" not in op_names
        assert "Result" in op_names

    def test_unknown_method_single_result_op(self):
        """Unknown method should get exactly 1 generic Result operation."""
        ops = self._get_ops("Some Completely Unknown Method")
        assert len(ops) == 1
        assert ops[0].name == "Result"
        assert ops[0].label == "Analysis Result"

    def test_known_method_keeps_pvalue(self):
        """Known inferential methods should still get their full operation set."""
        ops = self._get_ops("ANCOVA")
        op_names = [op.name for op in ops]
        # ANCOVA should have multiple operations including p-value
        assert len(ops) > 1

    def test_known_method_ttest(self):
        """t-test should match and get proper operations."""
        ops = self._get_ops("t-test")
        assert len(ops) > 1

    def test_kaplan_meier_matches(self):
        """Kaplan-Meier should match and get proper operations."""
        ops = self._get_ops("Kaplan-Meier")
        assert len(ops) > 1
