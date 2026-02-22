"""Tests for SAP extraction enhancement (Sprints 1-3).

Covers:
  - Multi-pass extraction helpers (_call_sap_pass, _build_context_summary, _safe_list)
  - Entity parsers (populations, methods, sensitivity, etc.)
  - AnalysisSpecification entity
  - MissingDataStrategy entity + ICE mapping
  - Analysis approach gating for Pass 3
  - ARS ResultPattern on operations
  - Endpoint map building + analysis specification reconciliation
"""

import json
import uuid
import pytest

from extraction.conditional.sap_extractor import (
    AnalysisPopulation,
    AnalysisSpecification,
    Characteristic,
    DataHandlingRule,
    DerivedVariable,
    InterimAnalysis,
    MissingDataStrategy,
    MultiplicityAdjustment,
    SampleSizeCalculation,
    SAPData,
    SensitivityAnalysis,
    StatisticalMethod,
    SubgroupAnalysis,
    ICE_MISSING_DATA_MAP,
    _build_context_summary,
    _safe_list,
    _parse_populations,
    _parse_characteristics,
    _parse_sample_size,
    _parse_statistical_methods,
    _parse_multiplicity,
    _parse_sensitivity,
    _parse_subgroups,
    _parse_interim,
    _parse_derived_variables,
    _parse_data_handling,
)


# =============================================================================
# Helper function tests
# =============================================================================

class TestBuildContextSummary:
    def test_empty_items(self):
        result = _build_context_summary("Populations", [], ['id', 'name'])
        assert "None extracted" in result

    def test_with_items(self):
        items = [
            {"id": "pop_1", "name": "FAS", "populationType": "FullAnalysis"},
            {"id": "pop_2", "name": "Safety", "populationType": "Safety"},
        ]
        result = _build_context_summary("Populations", items, ['id', 'name'])
        assert "2 items" in result
        assert "pop_1" in result
        assert "FAS" in result

    def test_caps_at_20(self):
        items = [{"id": f"pop_{i}", "name": f"Pop {i}"} for i in range(25)]
        result = _build_context_summary("Populations", items, ['id', 'name'])
        assert "pop_19" in result
        assert "pop_20" not in result


class TestSafeList:
    def test_none_data(self):
        assert _safe_list(None, 'key') == []

    def test_missing_key(self):
        assert _safe_list({"other": [1]}, 'key') == []

    def test_non_list_value(self):
        assert _safe_list({"key": "string"}, 'key') == []

    def test_valid_list(self):
        assert _safe_list({"key": [1, 2, 3]}, 'key') == [1, 2, 3]


# =============================================================================
# Entity parser tests
# =============================================================================

class TestParsePopulations:
    def test_basic_dict(self):
        pops = _parse_populations([
            {"id": "pop_1", "name": "FAS", "populationType": "FullAnalysis"},
        ])
        assert len(pops) == 1
        assert pops[0].name == "FAS"
        assert pops[0].population_type == "FullAnalysis"

    def test_string_fallback(self):
        pops = _parse_populations(["ITT Population"])
        assert pops[0].name == "ITT Population"
        assert pops[0].id == "pop_1"

    def test_empty_list(self):
        assert _parse_populations([]) == []

    def test_definition_field(self):
        pops = _parse_populations([
            {"name": "FAS", "definition": "All randomized subjects"},
        ])
        assert pops[0].definition == "All randomized subjects"


class TestParseStatisticalMethods:
    def test_full_method(self):
        methods = _parse_statistical_methods([{
            "id": "sm_1",
            "name": "ANCOVA",
            "description": "Primary analysis",
            "endpointName": "Change from baseline",
            "statoCode": "STATO:0000029",
            "hypothesisType": "superiority",
            "alphaLevel": 0.05,
            "covariates": ["baseline", "region"],
        }])
        assert len(methods) == 1
        m = methods[0]
        assert m.name == "ANCOVA"
        assert m.stato_code == "STATO:0000029"
        assert m.hypothesis_type == "superiority"
        assert m.alpha_level == 0.05
        assert len(m.covariates) == 2

    def test_minimal_method(self):
        methods = _parse_statistical_methods([{"name": "Descriptive"}])
        assert methods[0].name == "Descriptive"
        assert methods[0].hypothesis_type is None


class TestParseSensitivity:
    def test_basic(self):
        sens = _parse_sensitivity([{
            "name": "PP Analysis",
            "primaryEndpoint": "Primary",
            "methodVariation": "Per-protocol population",
        }])
        assert sens[0].name == "PP Analysis"
        assert sens[0].primary_endpoint == "Primary"

    def test_empty(self):
        assert _parse_sensitivity([]) == []


class TestParseSubgroups:
    def test_with_categories(self):
        subs = _parse_subgroups([{
            "name": "Age subgroup",
            "subgroupVariable": "Age",
            "categories": ["<65", ">=65"],
            "interactionTest": True,
        }])
        assert subs[0].subgroup_variable == "Age"
        assert subs[0].categories == ["<65", ">=65"]
        assert subs[0].interaction_test is True


class TestParseInterim:
    def test_with_stopping_rules(self):
        ias = _parse_interim([{
            "name": "IA1",
            "timing": "50% events",
            "informationFraction": 0.5,
            "stoppingRuleEfficacy": "p < 0.001",
            "spendingFunction": "O'Brien-Fleming",
        }])
        assert ias[0].information_fraction == 0.5
        assert ias[0].spending_function == "O'Brien-Fleming"


# =============================================================================
# New entity tests (Sprint 2B + 3D)
# =============================================================================

class TestAnalysisSpecification:
    def test_to_dict_full(self):
        spec = AnalysisSpecification(
            id="as_1",
            endpoint_id="ep_1",
            endpoint_name="Primary Efficacy",
            method_id="sm_1",
            method_name="ANCOVA",
            population_id="pop_1",
            population_name="FAS",
            estimand_id="est_1",
            analysis_type="primary",
            missing_data_strategy="MMRM under MAR",
            model_specification="ANCOVA with baseline and region as covariates",
        )
        d = spec.to_dict()
        assert d["endpointId"] == "ep_1"
        assert d["methodId"] == "sm_1"
        assert d["populationId"] == "pop_1"
        assert d["estimandId"] == "est_1"
        assert d["missingDataStrategy"] == "MMRM under MAR"
        assert d["instanceType"] == "AnalysisSpecification"

    def test_to_dict_minimal(self):
        spec = AnalysisSpecification(id="as_2", analysis_type="exploratory")
        d = spec.to_dict()
        assert d["analysisType"] == "exploratory"
        assert "endpointId" not in d
        assert "estimandId" not in d

    def test_descriptive_no_estimand(self):
        spec = AnalysisSpecification(
            id="as_3",
            method_name="Descriptive Statistics",
            analysis_type="primary",
        )
        d = spec.to_dict()
        assert "estimandId" not in d


class TestMissingDataStrategy:
    def test_to_dict(self):
        mds = MissingDataStrategy(
            id="mds_1",
            name="MMRM for primary endpoint",
            method="MMRM",
            endpoint_name="Change from baseline in NCC",
            estimand_alignment="Treatment Policy",
            assumptions="MAR",
            sensitivity_method="Tipping point analysis",
        )
        d = mds.to_dict()
        assert d["method"] == "MMRM"
        assert d["estimandAlignment"] == "Treatment Policy"
        assert d["assumptions"] == "MAR"
        assert d["instanceType"] == "MissingDataStrategy"

    def test_ice_mapping_treatment_policy(self):
        methods = ICE_MISSING_DATA_MAP["treatment policy"]
        assert "MMRM" in methods
        assert "MI" in methods

    def test_ice_mapping_composite(self):
        methods = ICE_MISSING_DATA_MAP["composite"]
        assert methods == []  # No imputation needed

    def test_ice_mapping_while_on_treatment(self):
        methods = ICE_MISSING_DATA_MAP["while on treatment"]
        assert "censor" in methods


# =============================================================================
# SAPData container tests
# =============================================================================

class TestSAPData:
    def test_includes_analysis_specs(self):
        data = SAPData(
            analysis_specifications=[
                AnalysisSpecification(id="as_1", analysis_type="primary"),
            ],
        )
        d = data.to_dict()
        assert len(d["analysisSpecifications"]) == 1
        assert d["summary"]["analysisSpecificationCount"] == 1

    def test_includes_missing_data(self):
        data = SAPData(
            missing_data_strategies=[
                MissingDataStrategy(id="mds_1", name="MMRM", method="MMRM"),
            ],
        )
        d = data.to_dict()
        assert len(d["missingDataStrategies"]) == 1
        assert d["summary"]["missingDataStrategyCount"] == 1

    def test_empty_data(self):
        data = SAPData()
        d = data.to_dict()
        assert all(d["summary"][k] == 0 for k in d["summary"])


# =============================================================================
# ARS ResultPattern tests (Sprint 3F)
# =============================================================================

class TestARSResultPattern:
    def test_ancova_has_result_patterns(self):
        from extraction.conditional.ars_generator import ARS_OPERATION_PATTERNS
        ops = ARS_OPERATION_PATTERNS["ANCOVA"]
        for op in ops:
            assert op.resultPattern is not None, f"{op.name} missing resultPattern"
        # P-value should have X.XXXX pattern
        pvalue_op = [o for o in ops if "PValue" in o.name][0]
        assert pvalue_op.resultPattern == "X.XXXX"

    def test_all_patterns_have_result_patterns(self):
        from extraction.conditional.ars_generator import ARS_OPERATION_PATTERNS
        for method_name, ops in ARS_OPERATION_PATTERNS.items():
            for op in ops:
                assert op.resultPattern is not None, \
                    f"{method_name}/{op.name} missing resultPattern"

    def test_ci_patterns_have_parentheses(self):
        from extraction.conditional.ars_generator import ARS_OPERATION_PATTERNS
        for method_name, ops in ARS_OPERATION_PATTERNS.items():
            for op in ops:
                if "CI" in op.name or "ci" in op.label.lower():
                    assert "(" in op.resultPattern, \
                        f"{method_name}/{op.name} CI should have parentheses in pattern"

    def test_result_pattern_serialized(self):
        from extraction.conditional.ars_generator import ARS_OPERATION_PATTERNS
        ops = ARS_OPERATION_PATTERNS["ANCOVA"]
        d = ops[0].to_dict()
        assert "resultPattern" in d
        assert d["resultPattern"] == "XX.XX"


# =============================================================================
# Endpoint map + analysis specification building (Sprint 2B)
# =============================================================================

class TestBuildEndpointMap:
    def test_basic_mapping(self):
        from pipeline.phases.sap import _build_endpoint_map
        design = {
            "objectives": [
                {
                    "endpoints": [
                        {"id": "ep_1", "text": "Change from baseline in NCC at Week 48"},
                        {"id": "ep_2", "text": "Overall survival"},
                    ]
                }
            ]
        }
        ep_map = _build_endpoint_map(design)
        assert "change from baseline in ncc at week 48" in ep_map
        assert ep_map["change from baseline in ncc at week 48"] == "ep_1"
        assert "overall survival" in ep_map
        # First 5 words also indexed for long endpoints
        assert "change from baseline in ncc" in ep_map

    def test_empty_design(self):
        from pipeline.phases.sap import _build_endpoint_map
        assert _build_endpoint_map({}) == {}
        assert _build_endpoint_map({"objectives": []}) == {}


class TestBuildAnalysisSpecifications:
    def test_basic_reconciliation(self):
        from pipeline.phases.sap import _build_analysis_specifications
        sap = {
            "statisticalMethods": [
                {"id": "sm_1", "name": "ANCOVA", "endpointName": "Primary endpoint", "arsReason": "PRIMARY"},
            ],
            "analysisPopulations": [
                {"id": "pop_1", "name": "FAS", "populationType": "FullAnalysis"},
            ],
        }
        design = {
            "objectives": [
                {"endpoints": [{"id": "ep_1", "text": "Primary endpoint"}]}
            ],
            "estimands": [],
        }
        specs = _build_analysis_specifications(sap, design, {})
        assert len(specs) == 1
        assert specs[0]["endpointId"] == "ep_1"
        assert specs[0]["methodName"] == "ANCOVA"
        assert specs[0]["analysisType"] == "primary"

    def test_no_methods(self):
        from pipeline.phases.sap import _build_analysis_specifications
        specs = _build_analysis_specifications({"statisticalMethods": []}, {}, {})
        assert specs == []

    def test_fuzzy_endpoint_matching(self):
        from pipeline.phases.sap import _build_analysis_specifications
        sap = {
            "statisticalMethods": [
                {"id": "sm_1", "name": "MMRM", "endpointName": "Change in copper balance from baseline"},
            ],
            "analysisPopulations": [],
        }
        design = {
            "objectives": [
                {"endpoints": [
                    {"id": "ep_1", "text": "Change in copper balance from baseline at Week 48"},
                ]}
            ],
            "estimands": [],
        }
        specs = _build_analysis_specifications(sap, design, {})
        # Should fuzzy match via word overlap
        assert len(specs) == 1
        assert specs[0].get("endpointId") == "ep_1"


# =============================================================================
# ARS Generator endpoint_map integration
# =============================================================================

class TestARSGeneratorEndpointMap:
    def test_accepts_endpoint_map(self):
        from extraction.conditional.ars_generator import ARSGenerator
        gen = ARSGenerator(
            sap_data={"analysisPopulations": [], "statisticalMethods": []},
            study_name="Test",
            endpoint_map={"primary endpoint": "ep_1"},
        )
        assert gen.endpoint_map == {"primary endpoint": "ep_1"}

    def test_default_empty_map(self):
        from extraction.conditional.ars_generator import ARSGenerator
        gen = ARSGenerator(
            sap_data={"analysisPopulations": [], "statisticalMethods": []},
        )
        assert gen.endpoint_map == {}

    def test_generate_ars_from_sap_with_map(self):
        from extraction.conditional.ars_generator import generate_ars_from_sap
        result = generate_ars_from_sap(
            sap_data={"analysisPopulations": [], "statisticalMethods": []},
            study_name="Test",
            endpoint_map={"ep": "id_1"},
        )
        assert "reportingEvent" in result


# =============================================================================
# Multi-pass prompts import test
# =============================================================================

class TestSAPPrompts:
    def test_all_prompts_importable(self):
        from extraction.conditional.sap_prompts import (
            SAP_PASS1_PROMPT, SAP_PASS2_PROMPT, SAP_PASS3_PROMPT, SAP_PASS4_PROMPT,
        )
        assert "{sap_text}" in SAP_PASS1_PROMPT
        assert "{pass1_context}" in SAP_PASS2_PROMPT
        assert "{endpoints_context}" in SAP_PASS2_PROMPT
        assert "{pass2_context}" in SAP_PASS3_PROMPT
        assert "{endpoints_context}" in SAP_PASS4_PROMPT

    def test_pass1_focuses_on_populations(self):
        from extraction.conditional.sap_prompts import SAP_PASS1_PROMPT
        assert "analysisPopulations" in SAP_PASS1_PROMPT
        assert "sampleSizeCalculations" in SAP_PASS1_PROMPT
        assert "sensitivityAnalyses" not in SAP_PASS1_PROMPT

    def test_pass3_focuses_on_sensitivity(self):
        from extraction.conditional.sap_prompts import SAP_PASS3_PROMPT
        assert "sensitivityAnalyses" in SAP_PASS3_PROMPT
        assert "subgroupAnalyses" in SAP_PASS3_PROMPT
        assert "interimAnalyses" in SAP_PASS3_PROMPT
