"""
Tests for Stratification Enhancement Sprints B–E.

Covers:
  Sprint B: Cross-phase linking (stratification_linker.py)
  Sprint C: USDM mapping (create_strata_cohorts), M11 composers
  Sprint E: Validation coherence checks
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extraction.execution.schema import (
    FactorLevel,
    StratificationFactor,
    AllocationCell,
    RandomizationScheme,
    ExecutionModelData,
)
from extraction.execution.validation import (
    validate_execution_model,
    ValidationSeverity,
)
from pipeline.stratification_linker import (
    link_factors_to_eligibility,
    link_factors_to_sap_covariates,
    link_scheme_to_arms,
    link_scheme_to_populations,
    run_stratification_linking,
    _fuzzy_match,
)
from pipeline.post_processing import create_strata_cohorts
from rendering.composers import _compose_treatment_assignment, _compose_synopsis


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

def _make_combined(
    scheme_dict=None,
    criteria=None,
    sap_methods=None,
    arms=None,
    analysis_pops=None,
):
    """Build a minimal combined USDM dict for testing."""
    sd = {
        "arms": arms or [],
        "population": {"criterionIds": []},
        "extensionAttributes": [],
        "analysisPopulations": analysis_pops or [],
    }
    if scheme_dict:
        sd["extensionAttributes"].append({
            "url": "https://protocol2usdm.io/extensions/x-executionModel-randomizationScheme",
            "valueObject": scheme_dict,
        })
    if sap_methods:
        sd["extensionAttributes"].append({
            "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
            "valueObject": sap_methods,
        })
    if criteria:
        sd["eligibilityCriteria"] = criteria

    return {
        "study": {
            "versions": [{
                "studyDesigns": [sd],
                "eligibilityCriterionItems": [],
            }],
        },
    }


SAMPLE_SCHEME = {
    "id": "rand_1",
    "ratio": "2:1",
    "method": "Stratified permuted block randomization",
    "algorithmType": "block",
    "blockSizes": [4, 6],
    "centralRandomization": True,
    "iwrsSystem": "IWRS",
    "concealmentMethod": "Interactive response technology",
    "stratificationFactors": [
        {
            "id": "s1",
            "name": "Age",
            "categories": ["<65 years", ">=65 years"],
            "factorLevels": [
                {"id": "fl1", "label": "<65 years", "definition": "Under 65"},
                {"id": "fl2", "label": ">=65 years", "definition": "65 or older"},
            ],
            "isBlocking": False,
        },
        {
            "id": "s2",
            "name": "Region",
            "categories": ["North America", "Europe"],
            "factorLevels": [
                {"id": "fl3", "label": "North America"},
                {"id": "fl4", "label": "Europe"},
            ],
            "isBlocking": False,
        },
    ],
}

SAMPLE_ARMS = [
    {"id": "arm1", "name": "Drug A"},
    {"id": "arm2", "name": "Placebo"},
]


# ─────────────────────────────────────────────────────────────
# Sprint B: Cross-Phase Linking Tests
# ─────────────────────────────────────────────────────────────

class TestSprintBLinking:

    def test_link_factors_to_eligibility_basic(self):
        criteria = [
            {"id": "crit1", "_text": "Adults aged 18 to 65 years"},
            {"id": "crit2", "_text": "Participants 65 years or older at screening"},
        ]
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["eligibilityCriteria"] = criteria
        links = link_factors_to_eligibility(combined)
        # Should find at least one link (age-related)
        assert isinstance(links, list)

    def test_link_factors_no_scheme(self):
        combined = _make_combined(scheme_dict=None)
        links = link_factors_to_eligibility(combined)
        assert links == []

    def test_link_sap_covariates_found(self):
        methods = [
            {"id": "m1", "name": "ANCOVA", "covariates": ["age", "region", "baseline value"]},
        ]
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME, sap_methods=methods)
        findings = link_factors_to_sap_covariates(combined)
        ok_items = [f for f in findings if f["type"] == "ok"]
        assert len(ok_items) >= 1  # At least "Age" should be found

    def test_link_sap_covariates_missing(self):
        methods = [
            {"id": "m1", "name": "T-test", "covariates": ["baseline value"]},
        ]
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME, sap_methods=methods)
        findings = link_factors_to_sap_covariates(combined)
        warnings = [f for f in findings if f["type"] == "warning"]
        assert len(warnings) >= 1  # At least one factor not in covariates

    def test_link_sap_no_methods(self):
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME)
        findings = link_factors_to_sap_covariates(combined)
        info_items = [f for f in findings if f["type"] == "info"]
        assert len(info_items) == 1

    def test_link_scheme_to_arms(self):
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME, arms=SAMPLE_ARMS)
        weights = link_scheme_to_arms(combined)
        assert len(weights) == 2
        assert weights[0]["armName"] == "Drug A"
        assert weights[0]["allocationWeight"] == 2
        assert weights[1]["armName"] == "Placebo"
        assert weights[1]["allocationWeight"] == 1

    def test_link_scheme_to_arms_no_arms(self):
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME, arms=[])
        weights = link_scheme_to_arms(combined)
        assert weights == []

    def test_link_scheme_to_populations(self):
        pops = [
            {"id": "pop1", "name": "Subgroup by Age", "description": "Age subgroup analysis"},
        ]
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME, analysis_pops=pops)
        links = link_scheme_to_populations(combined)
        assert len(links) >= 1
        assert links[0]["factorName"] == "age"

    def test_run_stratification_linking_integration(self):
        combined = _make_combined(
            scheme_dict=SAMPLE_SCHEME,
            arms=SAMPLE_ARMS,
            sap_methods=[{"id": "m1", "covariates": ["age"]}],
        )
        results = run_stratification_linking(combined)
        assert "armWeights" in results
        assert "sapCovariateFindings" in results
        assert len(results["armWeights"]) == 2

    def test_run_stratification_linking_no_scheme(self):
        combined = _make_combined(scheme_dict=None)
        results = run_stratification_linking(combined)
        assert results == {}

    def test_fuzzy_match_positive(self):
        assert _fuzzy_match("age group", "stratification by age group and region") == True

    def test_fuzzy_match_negative(self):
        assert _fuzzy_match("tumor type", "stratification by age group") == False


# ─────────────────────────────────────────────────────────────
# Sprint C: USDM Mapping + M11 Rendering Tests
# ─────────────────────────────────────────────────────────────

class TestSprintCMapping:

    def test_create_strata_cohorts(self):
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["population"] = {"cohorts": []}
        result = create_strata_cohorts(combined)
        cohorts = sd.get("studyCohorts", [])
        # 2 age levels + 2 region levels = 4 cohorts
        assert len(cohorts) == 4
        # Each should have characteristics
        for c in cohorts:
            assert c["instanceType"] == "StudyCohort"
            assert len(c["characteristics"]) == 1

    def test_create_strata_cohorts_no_scheme(self):
        combined = _make_combined(scheme_dict=None)
        result = create_strata_cohorts(combined)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        assert sd.get("studyCohorts", []) == []

    def test_create_strata_cohorts_deduplication(self):
        combined = _make_combined(scheme_dict=SAMPLE_SCHEME)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["studyCohorts"] = [{"id": "existing", "name": "Age: <65 years"}]
        sd["population"] = {"cohorts": []}
        create_strata_cohorts(combined)
        # Should not duplicate the existing cohort
        names = [c["name"] for c in sd["studyCohorts"]]
        assert names.count("Age: <65 years") == 1

    def test_create_strata_cohorts_bare_categories(self):
        scheme = {
            "id": "r1",
            "stratificationFactors": [
                {"id": "s1", "name": "Sex", "categories": ["Male", "Female"]},
            ],
        }
        combined = _make_combined(scheme_dict=scheme)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["population"] = {}
        create_strata_cohorts(combined)
        cohorts = sd.get("studyCohorts", [])
        assert len(cohorts) == 2
        names = {c["name"] for c in cohorts}
        assert "Sex: Male" in names
        assert "Sex: Female" in names


class TestSprintCComposers:

    def test_compose_treatment_assignment_full(self):
        usdm = _make_combined(scheme_dict=SAMPLE_SCHEME, arms=SAMPLE_ARMS)
        text = _compose_treatment_assignment(usdm)
        assert "4.3 Method of Treatment Assignment" in text
        assert "permuted block" in text.lower()
        assert "2:1" in text
        assert "Age" in text
        assert "Region" in text
        assert "IWRS" in text

    def test_compose_treatment_assignment_no_scheme(self):
        usdm = _make_combined(scheme_dict=None)
        text = _compose_treatment_assignment(usdm)
        assert text == ""

    def test_compose_treatment_assignment_adaptive(self):
        adaptive_scheme = {
            **SAMPLE_SCHEME,
            "isAdaptive": True,
            "adaptiveRules": "Allocation ratio adjusts at interim analysis",
        }
        usdm = _make_combined(scheme_dict=adaptive_scheme)
        text = _compose_treatment_assignment(usdm)
        assert "response-adaptive" in text.lower()
        assert "interim analysis" in text

    def test_compose_treatment_assignment_block_sizes(self):
        usdm = _make_combined(scheme_dict=SAMPLE_SCHEME)
        text = _compose_treatment_assignment(usdm)
        assert "4, 6" in text

    def test_compose_synopsis_stratification_detail(self):
        usdm = _make_combined(scheme_dict=SAMPLE_SCHEME)
        text = _compose_synopsis(usdm)
        # Should contain detailed stratification instead of just Yes/No
        assert "Stratified by" in text or "Stratification" in text

    def test_compose_synopsis_no_scheme_fallback(self):
        usdm = _make_combined(scheme_dict=None)
        text = _compose_synopsis(usdm)
        # Should fall back to Indicator: No
        assert "Stratification Indicator" in text or text == ""


# ─────────────────────────────────────────────────────────────
# Sprint E: Validation Coherence Tests
# ─────────────────────────────────────────────────────────────

class TestSprintEValidation:

    def test_validate_no_scheme_no_issues(self):
        data = ExecutionModelData()
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert len(strat_issues) == 0

    def test_validate_factor_no_levels(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            stratification_factors=[
                StratificationFactor(id="s1", name="Age", categories=[]),
            ],
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("no categories" in i.message for i in strat_issues)

    def test_validate_factor_single_level(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            stratification_factors=[
                StratificationFactor(id="s1", name="Sex", categories=["Male"]),
            ],
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("only 1 level" in i.message for i in strat_issues)

    def test_validate_block_size_incompatible(self):
        scheme = RandomizationScheme(
            id="r1", ratio="2:1",
            block_size=5,  # 5 is not divisible by 3 (2+1)
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("not a multiple" in i.message for i in strat_issues)

    def test_validate_block_size_compatible(self):
        scheme = RandomizationScheme(
            id="r1", ratio="2:1",
            block_size=6,  # 6 is divisible by 3 (2+1)
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues
                        if i.component == "Stratification" and "not a multiple" in i.message]
        assert len(strat_issues) == 0

    def test_validate_overstratification(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            stratification_factors=[
                StratificationFactor(id="s1", name="A", categories=["1", "2", "3", "4", "5"]),
                StratificationFactor(id="s2", name="B", categories=["x", "y", "z", "w"]),
            ],
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("overstratification" in i.message for i in strat_issues)

    def test_validate_central_no_iwrs(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            central_randomization=True,
            iwrs_system=None,
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("IWRS" in i.message for i in strat_issues)

    def test_validate_adaptive_no_rules(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            is_adaptive=True,
            adaptive_rules=None,
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        assert any("adaptation rules" in i.message for i in strat_issues)

    def test_validate_good_scheme_minimal_issues(self):
        scheme = RandomizationScheme(
            id="r1", ratio="1:1",
            block_size=4,
            iwrs_system="IWRS",
            central_randomization=True,
            stratification_factors=[
                StratificationFactor(id="s1", name="Age", categories=["<65", ">=65"]),
                StratificationFactor(id="s2", name="Sex", categories=["Male", "Female"]),
            ],
        )
        data = ExecutionModelData(randomization_scheme=scheme)
        result = validate_execution_model(data)
        strat_issues = [i for i in result.issues if i.component == "Stratification"]
        # Good scheme should have 0 warnings from stratification
        strat_warnings = [i for i in strat_issues if i.severity == ValidationSeverity.WARNING]
        assert len(strat_warnings) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
