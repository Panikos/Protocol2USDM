"""
Tests for AnalysisApproach classification and estimand validation.

Covers:
- AnalysisApproach enum behavior
- ObjectivesData.validate_e9_completeness() with approach awareness
- Estimand.to_dict() no longer fabricates default ICEs
- ObjectivesData.to_dict() includes analysisApproach in summary
"""

import pytest
from extraction.objectives.schema import (
    AnalysisApproach,
    ObjectivesData,
    Objective,
    Endpoint,
    Estimand,
    IntercurrentEvent,
    ObjectiveLevel,
    EndpointLevel,
    IntercurrentEventStrategy,
)


# ============================================================================
# AnalysisApproach enum
# ============================================================================

class TestAnalysisApproach:
    def test_enum_values(self):
        assert AnalysisApproach.CONFIRMATORY.value == "confirmatory"
        assert AnalysisApproach.DESCRIPTIVE.value == "descriptive"
        assert AnalysisApproach.UNKNOWN.value == "unknown"

    def test_default_is_unknown(self):
        data = ObjectivesData()
        assert data.analysis_approach == AnalysisApproach.UNKNOWN


# ============================================================================
# Estimand.to_dict() — no more default ICE fabrication
# ============================================================================

class TestEstimandNoFabrication:
    def test_estimand_empty_ices_stays_empty(self):
        """Estimand with no ICEs should NOT have fabricated default ICE."""
        est = Estimand(
            id="est_1",
            name="Test Estimand",
            intercurrent_events=[],
        )
        d = est.to_dict()
        assert d["intercurrentEvents"] == []

    def test_estimand_with_ices_preserves_them(self):
        """Estimand with real ICEs should preserve them."""
        ice = IntercurrentEvent(
            id="ice_1",
            name="Treatment discontinuation",
            text="Subject discontinues",
            strategy=IntercurrentEventStrategy.TREATMENT_POLICY,
        )
        est = Estimand(
            id="est_1",
            name="Test Estimand",
            intercurrent_events=[ice],
        )
        d = est.to_dict()
        assert len(d["intercurrentEvents"]) == 1
        assert d["intercurrentEvents"][0]["name"] == "Treatment discontinuation"


# ============================================================================
# ObjectivesData.to_dict() — includes analysisApproach
# ============================================================================

class TestObjectivesDataToDict:
    def test_summary_includes_analysis_approach(self):
        data = ObjectivesData(
            analysis_approach=AnalysisApproach.DESCRIPTIVE,
            analysis_approach_rationale="No formal hypothesis testing",
        )
        d = data.to_dict()
        assert d["summary"]["analysisApproach"] == "descriptive"
        assert d["summary"]["analysisApproachRationale"] == "No formal hypothesis testing"

    def test_summary_approach_unknown_no_rationale(self):
        data = ObjectivesData()
        d = data.to_dict()
        assert d["summary"]["analysisApproach"] == "unknown"
        assert "analysisApproachRationale" not in d["summary"]


# ============================================================================
# validate_e9_completeness — approach-aware
# ============================================================================

class TestValidateE9Completeness:
    def _make_primary_endpoint(self):
        return Endpoint(
            id="ep_1", name="Primary EP", text="Change from baseline",
            level=EndpointLevel.PRIMARY,
        )

    def _make_estimand(self, endpoint_id="ep_1"):
        return Estimand(
            id="est_1",
            name="Primary Estimand",
            variable_of_interest_id=endpoint_id,
            intervention_ids=["int_1"],
            analysis_population_id="pop_1",
            intercurrent_events=[
                IntercurrentEvent(
                    id="ice_1", name="Discontinuation",
                    text="Discontinues treatment",
                    strategy=IntercurrentEventStrategy.TREATMENT_POLICY,
                )
            ],
            summary_measure="Difference in means",
        )

    def test_descriptive_no_estimands_no_warning(self):
        """Descriptive study with no estimands should NOT warn about missing estimands."""
        data = ObjectivesData(
            endpoints=[self._make_primary_endpoint()],
            analysis_approach=AnalysisApproach.DESCRIPTIVE,
        )
        issues = data.validate_e9_completeness()
        # Should NOT have "estimand_existence" warning for descriptive studies
        existence_issues = [i for i in issues if i["attribute"] == "estimand_existence"]
        assert len(existence_issues) == 0

    def test_confirmatory_no_estimands_warns(self):
        """Confirmatory study with no estimands SHOULD warn."""
        data = ObjectivesData(
            endpoints=[self._make_primary_endpoint()],
            analysis_approach=AnalysisApproach.CONFIRMATORY,
        )
        issues = data.validate_e9_completeness()
        existence_issues = [i for i in issues if i["attribute"] == "estimand_existence"]
        assert len(existence_issues) == 1
        assert "Confirmatory" in existence_issues[0]["message"]

    def test_descriptive_with_estimands_warns_mismatch(self):
        """Descriptive study that somehow has estimands should warn about mismatch."""
        data = ObjectivesData(
            endpoints=[self._make_primary_endpoint()],
            estimands=[self._make_estimand()],
            analysis_approach=AnalysisApproach.DESCRIPTIVE,
        )
        issues = data.validate_e9_completeness()
        mismatch = [i for i in issues if i["attribute"] == "approach_mismatch"]
        assert len(mismatch) == 1
        assert "descriptive" in mismatch[0]["message"].lower()

    def test_confirmatory_with_valid_estimands_no_issues(self):
        """Confirmatory study with complete estimands should have no approach issues."""
        data = ObjectivesData(
            endpoints=[self._make_primary_endpoint()],
            estimands=[self._make_estimand()],
            analysis_approach=AnalysisApproach.CONFIRMATORY,
        )
        issues = data.validate_e9_completeness()
        approach_issues = [i for i in issues if i["attribute"] in ("approach_mismatch", "estimand_existence")]
        assert len(approach_issues) == 0
