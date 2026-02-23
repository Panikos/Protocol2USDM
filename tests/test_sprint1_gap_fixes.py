"""
Regression tests for Sprint 1 extractor gap fixes (C1, H3, H5, H8, H9, H10).

Tests cover:
  C1: StudyVersion.versionIdentifier ← protocolVersion
  H3: StudyDesign.studyPhase ← metadata studyPhase
  H5: Endpoint.purpose defaults based on level
  H8: Administration.administrableProductId linked by name
  H9: AdministrableProduct.ingredients nested from substances
  H10: Ingredient.strengthId linked to Strength entity
"""

import pytest
from unittest.mock import MagicMock

from pipeline.base_phase import PhaseResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metadata_result(protocol_version=None, study_phase=None):
    """Build a minimal PhaseResult mimicking metadata extraction."""
    from extraction.metadata.schema import StudyMetadata, StudyPhase, StudyTitle, TitleType

    md = StudyMetadata(study_name="Test Study")
    md.titles = [StudyTitle(id="t1", text="Test", type=TitleType.OFFICIAL)]
    if protocol_version:
        md.protocol_version = protocol_version
    if study_phase:
        md.study_phase = StudyPhase(phase=study_phase)
    return PhaseResult(success=True, data=md)


def _make_objectives_result(endpoints_with_levels):
    """Build a PhaseResult with endpoints that have levels but no purpose."""
    from extraction.objectives.schema import (
        ObjectivesData, Objective, Endpoint, ObjectiveLevel, EndpointLevel,
    )

    eps = []
    for i, (name, level_str) in enumerate(endpoints_with_levels):
        level = EndpointLevel[level_str.upper()]
        eps.append(Endpoint(
            id=f"ep_{i}",
            name=name,
            text=f"Endpoint: {name}",
            level=level,
            # purpose intentionally left None
        ))

    data = ObjectivesData(
        objectives=[Objective(id="obj_1", name="Primary Obj", text="Test", level=ObjectiveLevel.PRIMARY)],
        endpoints=eps,
    )
    return PhaseResult(success=True, data=data)


def _base_combined():
    """Minimal combined dict for post-processing tests."""
    return {
        "study": {
            "versions": [{
                "id": "sv_1",
                "instanceType": "StudyVersion",
                "administrableProducts": [],
                "studyDesigns": [{"id": "sd_1"}],
            }]
        },
        "administrations": [],
        "substances": [],
    }


# ===================================================================
# C1 — versionIdentifier from protocolVersion
# ===================================================================

class TestC1VersionIdentifier:
    """C1: StudyVersion.versionIdentifier ← metadata.protocolVersion."""

    def test_version_identifier_set_from_protocol_version(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        result = _make_metadata_result(protocol_version="3.0")
        phase.combine(result, sv, sd, combined, {})
        assert sv["versionIdentifier"] == "3.0"

    def test_version_identifier_default_when_no_protocol_version(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        result = _make_metadata_result()  # no protocol_version
        phase.combine(result, sv, sd, combined, {})
        # Should remain at default
        assert sv["versionIdentifier"] == "1.0"

    def test_version_identifier_from_fallback(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        prev = {"metadata": {"metadata": {"protocolVersion": "2.1"}}}
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        assert sv["versionIdentifier"] == "2.1"

    def test_version_identifier_fallback_missing(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        prev = {"metadata": {"metadata": {}}}
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        assert sv["versionIdentifier"] == "1.0"


# ===================================================================
# H3 — studyPhase copied to study_design
# ===================================================================

class TestH3StudyPhase:
    """H3: StudyDesign.studyPhase ← metadata.studyPhase."""

    def test_study_phase_copied_to_design(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        result = _make_metadata_result(study_phase="Phase 3")
        phase.combine(result, sv, sd, combined, {})
        assert "studyPhase" in sd
        assert sd["studyPhase"]["instanceType"] == "AliasCode"
        assert sd["studyPhase"]["standardCode"]["code"] == "C15602"
        assert sd["studyPhase"]["standardCode"]["decode"] == "Phase III Trial"

    def test_study_phase_not_copied_when_absent(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        result = _make_metadata_result()  # no study_phase
        phase.combine(result, sv, sd, combined, {})
        assert "studyPhase" not in sd

    def test_study_phase_from_fallback(self):
        from pipeline.phases.metadata import MetadataPhase
        phase = MetadataPhase()
        sv = {"id": "sv_1", "versionIdentifier": "1.0"}
        sd = {"id": "sd_1"}
        combined = {}
        prev = {"metadata": {"metadata": {"studyPhase": {"id": "x", "standardCode": {"code": "C15601", "decode": "Phase II Trial", "instanceType": "Code"}, "instanceType": "AliasCode"}}}}
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        assert sd["studyPhase"]["standardCode"]["decode"] == "Phase II Trial"


# ===================================================================
# H5 — Endpoint.purpose defaults
# ===================================================================

class TestH5EndpointPurpose:
    """H5: Endpoint.purpose defaults based on level."""

    def test_primary_endpoint_gets_efficacy(self):
        from pipeline.phases.objectives import ObjectivesPhase
        phase = ObjectivesPhase()
        sv = {}
        sd = {}
        combined = {}
        result = _make_objectives_result([("PFS", "PRIMARY")])
        phase.combine(result, sv, sd, combined, {})
        # Endpoints are now nested inside objectives per USDM v4.0
        eps = combined["_temp_endpoints"]
        assert len(eps) == 1
        assert eps[0]["purpose"] == "Efficacy"

    def test_secondary_endpoint_gets_efficacy(self):
        from pipeline.phases.objectives import ObjectivesPhase
        phase = ObjectivesPhase()
        sv = {}
        sd = {}
        combined = {}
        result = _make_objectives_result([("ORR", "SECONDARY")])
        phase.combine(result, sv, sd, combined, {})
        assert combined["_temp_endpoints"][0]["purpose"] == "Efficacy"

    def test_exploratory_endpoint_gets_exploratory(self):
        from pipeline.phases.objectives import ObjectivesPhase
        phase = ObjectivesPhase()
        sv = {}
        sd = {}
        combined = {}
        result = _make_objectives_result([("Biomarker", "EXPLORATORY")])
        phase.combine(result, sv, sd, combined, {})
        assert combined["_temp_endpoints"][0]["purpose"] == "Exploratory"

    def test_existing_purpose_not_overwritten(self):
        from pipeline.phases.objectives import _default_endpoint_purpose
        eps = [{"level": {"decode": "Primary Endpoint"}, "purpose": "Safety"}]
        _default_endpoint_purpose(eps)
        assert eps[0]["purpose"] == "Safety"

    def test_unknown_level_no_purpose(self):
        from pipeline.phases.objectives import _default_endpoint_purpose
        eps = [{"level": {"decode": "Unknown"}}]
        _default_endpoint_purpose(eps)
        assert "purpose" not in eps[0]

    def test_string_level_decode(self):
        from pipeline.phases.objectives import _default_endpoint_purpose
        eps = [{"level": "Primary"}]
        _default_endpoint_purpose(eps)
        assert eps[0]["purpose"] == "Efficacy"

    def test_fallback_path_applies_defaults(self):
        from pipeline.phases.objectives import ObjectivesPhase
        phase = ObjectivesPhase()
        sv = {}
        sd = {}
        combined = {}
        prev = {
            "objectives": {
                "objectives": {"objectives": [{"id": "o1", "endpointIds": ["ep1", "ep2"]}], "endpoints": [
                    {"id": "ep1", "level": {"decode": "Primary Endpoint"}},
                    {"id": "ep2", "level": {"decode": "Secondary Endpoint"}, "purpose": "Safety"},
                ]}
            }
        }
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        eps = combined.get("_temp_endpoints", [])
        assert eps[0]["purpose"] == "Efficacy"
        assert eps[1]["purpose"] == "Safety"  # not overwritten


# ===================================================================
# H8 — Administration → Product linking
# ===================================================================

class TestH8AdminProductLink:
    """H8: Administration.administrableProductId linked by name."""

    def test_exact_name_match(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Canagliflozin"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Canagliflozin"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_1"

    def test_substring_match(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Canagliflozin"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Canagliflozin 100mg Tablet"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_1"

    def test_case_insensitive(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "CANAGLIFLOZIN"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "canagliflozin"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_1"

    def test_already_linked_not_overwritten(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Drug A", "administrableProductId": "prod_99"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_99"

    def test_no_match_leaves_unlinked(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Completely Different"},
        ]
        link_administrations_to_products(combined)
        assert "administrableProductId" not in combined["administrations"][0]

    def test_empty_products_no_error(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["administrations"] = [{"id": "admin_1", "name": "Drug A"}]
        result = link_administrations_to_products(combined)
        assert result is combined  # no crash

    def test_partial_word_match_does_not_link(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Drug AB Tablet"},
        ]
        link_administrations_to_products(combined)
        assert "administrableProductId" not in combined["administrations"][0]

    def test_ambiguous_fuzzy_match_does_not_link(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A"},
            {"id": "prod_2", "name": "Drug B"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Drug"},
        ]
        link_administrations_to_products(combined)
        assert "administrableProductId" not in combined["administrations"][0]

    def test_prefers_more_specific_fuzzy_match(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Canagliflozin"},
            {"id": "prod_2", "name": "Canagliflozin Tablet"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Canagliflozin Tablet 100mg"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_2"


# ===================================================================
# NX-4 — Procedure/Activity link hardening
# ===================================================================

class TestNX4ProcedureActivityLinking:
    def test_links_by_whole_phrase_match(self):
        from pipeline.post_processing import link_procedures_to_activities

        study_design = {
            "procedures": [{"id": "proc_1", "name": "Blood Pressure"}],
            "activities": [{"id": "act_1", "name": "Blood Pressure Visit 1"}],
        }

        link_procedures_to_activities(study_design)

        linked = study_design["activities"][0]["definedProcedures"][0]
        assert linked["id"] == "proc_1"
        assert linked["procedureId"] == "proc_1"

    def test_existing_procedure_id_reference_not_duplicated(self):
        from pipeline.post_processing import link_procedures_to_activities

        study_design = {
            "procedures": [{"id": "proc_1", "name": "Blood Pressure"}],
            "activities": [{
                "id": "act_1",
                "name": "Blood Pressure Visit 1",
                "definedProcedures": [{"id": "proc_1", "procedureId": "proc_1"}],
            }],
        }

        link_procedures_to_activities(study_design)

        assert len(study_design["activities"][0]["definedProcedures"]) == 1

    def test_partial_word_match_does_not_link(self):
        from pipeline.post_processing import link_procedures_to_activities

        study_design = {
            "procedures": [{"id": "proc_1", "name": "Drug A"}],
            "activities": [{"id": "act_1", "name": "Drug AB Visit"}],
        }

        link_procedures_to_activities(study_design)

        assert "definedProcedures" not in study_design["activities"][0]

    def test_ambiguous_fuzzy_match_does_not_link(self):
        from pipeline.post_processing import link_procedures_to_activities

        study_design = {
            "procedures": [
                {"id": "proc_1", "name": "Screening Visit"},
                {"id": "proc_2", "name": "Baseline Visit"},
            ],
            "activities": [{"id": "act_1", "name": "Visit"}],
        }

        link_procedures_to_activities(study_design)

        assert "definedProcedures" not in study_design["activities"][0]


# ===================================================================
# NX-5 — StudyElement key normalization
# ===================================================================

class TestNX5StudyElementNormalization:
    def test_merges_legacy_study_elements_into_elements(self):
        from pipeline.combiner import _normalize_study_elements

        study_design = {
            "studyElements": [
                {"id": "elem_1", "name": "Legacy 1"},
                {"id": "elem_2", "name": "Legacy 2"},
            ],
            "elements": [
                {"id": "elem_2", "name": "Already Canonical"},
                {"id": "elem_exec_1", "name": "Execution Element"},
            ],
        }

        _normalize_study_elements(study_design)

        assert "studyElements" not in study_design
        element_ids = {e["id"] for e in study_design["elements"]}
        assert element_ids == {"elem_1", "elem_2", "elem_exec_1"}


# ===================================================================
# H9 — Ingredient nesting
# ===================================================================

class TestH9IngredientNesting:
    """H9: Ingredients nested inside AdministrableProduct."""

    def test_substance_nested_by_id(self):
        from pipeline.post_processing import nest_ingredients_in_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A", "substanceIds": ["sub_1"]},
        ]
        combined["substances"] = [
            {"id": "sub_1", "name": "Active Ingredient A"},
        ]
        nest_ingredients_in_products(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert len(prod["ingredients"]) == 1
        assert prod["ingredients"][0]["substance"]["id"] == "sub_1"
        assert prod["ingredients"][0]["instanceType"] == "Ingredient"

    def test_substance_nested_by_name(self):
        from pipeline.post_processing import nest_ingredients_in_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Canagliflozin Tablet"},
        ]
        combined["substances"] = [
            {"id": "sub_1", "name": "Canagliflozin"},
        ]
        nest_ingredients_in_products(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert len(prod["ingredients"]) == 1

    def test_existing_ingredients_not_overwritten(self):
        from pipeline.post_processing import nest_ingredients_in_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A", "substanceIds": ["sub_1"],
             "ingredients": [{"id": "existing"}]},
        ]
        combined["substances"] = [{"id": "sub_1", "name": "Sub A"}]
        nest_ingredients_in_products(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert len(prod["ingredients"]) == 1
        assert prod["ingredients"][0]["id"] == "existing"

    def test_no_substances_no_error(self):
        from pipeline.post_processing import nest_ingredients_in_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A"},
        ]
        combined["substances"] = []
        result = nest_ingredients_in_products(combined)
        assert result is combined


# ===================================================================
# H10 — Ingredient strength linking
# ===================================================================

class TestH10IngredientStrength:
    """H10: Ingredient.strengthId linked to Strength entity."""

    def test_strength_linked(self):
        from pipeline.post_processing import link_ingredient_strengths
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {
                "id": "prod_1", "name": "Drug A", "strength": "15 mg",
                "ingredients": [{"id": "ing_1", "substanceId": "sub_1"}],
            },
        ]
        link_ingredient_strengths(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert prod["ingredients"][0]["strengthId"].startswith("str_")
        assert len(prod["strengths"]) == 1
        assert prod["strengths"][0]["value"] == "15 mg"

    def test_no_strength_string_skipped(self):
        from pipeline.post_processing import link_ingredient_strengths
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A",
             "ingredients": [{"id": "ing_1"}]},
        ]
        link_ingredient_strengths(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert "strengthId" not in prod["ingredients"][0]

    def test_existing_strength_id_not_overwritten(self):
        from pipeline.post_processing import link_ingredient_strengths
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {
                "id": "prod_1", "name": "Drug A", "strength": "15 mg",
                "ingredients": [{"id": "ing_1", "strengthId": "existing_str"}],
            },
        ]
        link_ingredient_strengths(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert prod["ingredients"][0]["strengthId"] == "existing_str"

    def test_no_ingredients_skipped(self):
        from pipeline.post_processing import link_ingredient_strengths
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Drug A", "strength": "15 mg"},
        ]
        link_ingredient_strengths(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert "strengths" not in prod

    def test_multiple_ingredients_all_linked(self):
        from pipeline.post_processing import link_ingredient_strengths
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {
                "id": "prod_1", "name": "Combo", "strength": "100 mg / 50 mg",
                "ingredients": [
                    {"id": "ing_1", "substanceId": "sub_1"},
                    {"id": "ing_2", "substanceId": "sub_2"},
                ],
            },
        ]
        link_ingredient_strengths(combined)
        prod = combined["study"]["versions"][0]["administrableProducts"][0]
        assert all(ing.get("strengthId") for ing in prod["ingredients"])
        assert prod["ingredients"][0]["strengthId"] == prod["ingredients"][1]["strengthId"]


# ---------------------------------------------------------------------------
# C2: Arm type C-codes
# ---------------------------------------------------------------------------

class TestC2ArmTypeCCodes:
    """Regression tests for arm type NCI C-code mapping (C2 fix)."""

    def test_experimental_arm_gets_c174266(self):
        from extraction.studydesign.schema import StudyArm, ArmType
        arm = StudyArm(id="arm_1", name="Nivolumab", arm_type=ArmType.EXPERIMENTAL)
        d = arm.to_dict()
        assert d["type"]["code"] == "C174266"
        assert d["type"]["decode"] == "Experimental Arm"
        assert d["type"]["instanceType"] == "Code"

    def test_active_comparator_arm_gets_c174267(self):
        from extraction.studydesign.schema import StudyArm, ArmType
        arm = StudyArm(id="arm_2", name="Sorafenib", arm_type=ArmType.ACTIVE_COMPARATOR)
        d = arm.to_dict()
        assert d["type"]["code"] == "C174267"

    def test_placebo_arm_gets_c174268(self):
        from extraction.studydesign.schema import StudyArm, ArmType
        arm = StudyArm(id="arm_3", name="Placebo", arm_type=ArmType.PLACEBO_COMPARATOR)
        d = arm.to_dict()
        assert d["type"]["code"] == "C174268"

    def test_unknown_arm_gets_fallback_c174451(self):
        from extraction.studydesign.schema import StudyArm, ArmType
        arm = StudyArm(id="arm_4", name="Other", arm_type=ArmType.UNKNOWN)
        d = arm.to_dict()
        assert d["type"]["code"] == "C174451"
        assert d["type"]["codeSystem"] == "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl"


# ---------------------------------------------------------------------------
# C1: Eligibility criterion nesting
# ---------------------------------------------------------------------------

class TestC1EligibilityCriterionNesting:
    """Regression tests for nesting EligibilityCriterion inside EligibilityCriterionItem."""

    def test_criterion_nested_in_item(self):
        from pipeline.phases.eligibility import EligibilityPhase
        items = [
            {"id": "eci_1", "name": "Age >= 18", "text": "Subject must be >= 18 years"},
            {"id": "eci_2", "name": "Confirmed diagnosis", "text": "Histologically confirmed"},
        ]
        criteria = [
            {"id": "ec_1", "criterionItemId": "eci_1", "category": {"code": "C25532", "decode": "Inclusion"}},
            {"id": "ec_2", "criterionItemId": "eci_2", "category": {"code": "C25532", "decode": "Inclusion"}},
        ]
        EligibilityPhase._nest_criteria_in_items(items, criteria)
        assert items[0]["criterion"]["id"] == "ec_1"
        assert items[0]["criterion"]["category"]["code"] == "C25532"
        assert items[1]["criterion"]["id"] == "ec_2"

    def test_already_nested_not_overwritten(self):
        from pipeline.phases.eligibility import EligibilityPhase
        existing_crit = {"id": "ec_orig", "category": {"code": "C25370"}}
        items = [{"id": "eci_1", "criterion": existing_crit}]
        criteria = [{"id": "ec_new", "criterionItemId": "eci_1", "category": {"code": "C25532"}}]
        EligibilityPhase._nest_criteria_in_items(items, criteria)
        assert items[0]["criterion"]["id"] == "ec_orig"  # Not overwritten

    def test_empty_criteria_no_error(self):
        from pipeline.phases.eligibility import EligibilityPhase
        items = [{"id": "eci_1", "name": "Test"}]
        EligibilityPhase._nest_criteria_in_items(items, [])
        assert "criterion" not in items[0]

    def test_unmatched_criterion_not_nested(self):
        from pipeline.phases.eligibility import EligibilityPhase
        items = [{"id": "eci_1"}]
        criteria = [{"id": "ec_1", "criterionItemId": "eci_99"}]
        EligibilityPhase._nest_criteria_in_items(items, criteria)
        assert "criterion" not in items[0]


# ---------------------------------------------------------------------------
# H8: Drug-name fallback matching for admin→product linking
# ---------------------------------------------------------------------------

class TestH8DrugNameFallback:
    """Regression tests for drug-name-based admin→product linking."""

    def test_nivolumab_admin_matches_product(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Nivolumab Solution for Injection"},
        ]
        combined["administrations"] = [
            {"id": "admin_1", "name": "Nivolumab 240 mg IV every 2 weeks"},
        ]
        link_administrations_to_products(combined)
        assert combined["administrations"][0]["administrableProductId"] == "prod_1"

    def test_nested_admin_also_linked(self):
        from pipeline.post_processing import link_administrations_to_products
        combined = _base_combined()
        combined["study"]["versions"][0]["administrableProducts"] = [
            {"id": "prod_1", "name": "Sorafenib Tablets"},
        ]
        combined["study"]["versions"][0]["studyInterventions"] = [
            {"id": "si_1", "name": "Sorafenib", "administrations": [
                {"id": "admin_1", "name": "Sorafenib 400 mg PO BID"},
            ]},
        ]
        combined["administrations"] = []
        link_administrations_to_products(combined)
        nested = combined["study"]["versions"][0]["studyInterventions"][0]["administrations"][0]
        assert nested["administrableProductId"] == "prod_1"


# ===========================================================================
# C1: Phase inference from study title (fallback when LLM omits studyPhase)
# ===========================================================================

class TestC1PhaseInference:
    """Regression: MetadataPhase._infer_phase_from_titles."""

    def _infer(self, title_text: str):
        from pipeline.phases.metadata import MetadataPhase
        from extraction.metadata.schema import StudyTitle, TitleType
        titles = [StudyTitle(id="t1", text=title_text, type=TitleType.OFFICIAL)]
        return MetadataPhase._infer_phase_from_titles(titles)

    def test_phase_iii_roman(self):
        result = self._infer("A Phase III, Randomized Study of Drug X")
        assert result is not None
        d = result.to_dict()
        assert d["standardCode"]["code"] == "C15602"
        assert "Phase III" in d["standardCode"]["decode"]

    def test_phase_3_arabic(self):
        result = self._infer("A Phase 3 Study of Drug X")
        assert result is not None
        d = result.to_dict()
        assert d["standardCode"]["code"] == "C15602"

    def test_phase_1_2_combined(self):
        result = self._infer("Phase I/II Dose-Escalation Study")
        assert result is not None
        d = result.to_dict()
        assert d["standardCode"]["code"] == "C15693"

    def test_no_phase_in_title(self):
        result = self._infer("Study of Drug X in Healthy Volunteers")
        assert result is None

    def test_combine_uses_fallback(self):
        """When LLM returns no studyPhase, combine should infer from titles."""
        from pipeline.phases.metadata import MetadataPhase
        from extraction.metadata.schema import StudyMetadata, StudyTitle, TitleType

        md = StudyMetadata(study_name="Test")
        md.titles = [StudyTitle(id="t1", text="A Phase III Study", type=TitleType.OFFICIAL)]
        md.study_phase = None  # LLM didn't return phase

        result = PhaseResult(success=True, data=md)
        study_version = {}
        study_design = {}
        MetadataPhase().combine(result, study_version, study_design, {}, {})

        assert "studyPhase" in study_design
        assert study_design["studyPhase"]["standardCode"]["code"] == "C15602"


# ===========================================================================
# H1: Metadata enrollment promotion to population.plannedEnrollmentNumber
# ===========================================================================

class TestH1EnrollmentPromotion:
    """Regression: promote_extensions_to_usdm Rule 1b."""

    def test_metadata_enrollment_promoted(self):
        from pipeline.promotion import promote_extensions_to_usdm
        combined = _base_combined()
        combined["_temp_planned_enrollment"] = 4500
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["population"] = {"id": "pop_1", "instanceType": "StudyDesignPopulation"}
        sd["eligibilityCriteria"] = []

        promote_extensions_to_usdm(combined)

        pop = sd["population"]
        assert "plannedEnrollmentNumber" in pop
        qty = pop["plannedEnrollmentNumber"]
        assert qty["value"] == 4500

    def test_sap_takes_priority_over_metadata(self):
        """SAP extension should win over metadata fallback."""
        from pipeline.promotion import promote_extensions_to_usdm, _build_participant_quantity
        combined = _base_combined()
        combined["_temp_planned_enrollment"] = 200  # metadata says 200
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["population"] = {
            "id": "pop_1", "instanceType": "StudyDesignPopulation",
            "plannedEnrollmentNumber": _build_participant_quantity(500),  # SAP already set 500
        }
        sd["eligibilityCriteria"] = []

        promote_extensions_to_usdm(combined)

        pop = sd["population"]
        assert pop["plannedEnrollmentNumber"]["value"] == 500  # SAP value preserved

    def test_no_enrollment_no_crash(self):
        from pipeline.promotion import promote_extensions_to_usdm
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["population"] = {"id": "pop_1", "instanceType": "StudyDesignPopulation"}
        sd["eligibilityCriteria"] = []
        promote_extensions_to_usdm(combined)
        assert "plannedEnrollmentNumber" not in sd["population"]


# ===========================================================================
# H4: Epoch type inference for enrolment/randomisation/closure keywords
# ===========================================================================

class TestH4EpochTypeKeywords:
    """Regression: infer_cdisc_epoch_type for new keywords."""

    def test_enrolment_is_screening(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, decode = infer_cdisc_epoch_type("Enrolment")
        assert code == "C48262"
        assert decode == "Trial Screening"

    def test_enrollment_us_spelling(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Enrollment Period")
        assert code == "C48262"

    def test_randomisation_is_screening(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Randomisation")
        assert code == "C48262"

    def test_randomization_us_spelling(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Randomization Visit")
        assert code == "C48262"

    def test_baseline_is_screening(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Baseline")
        assert code == "C48262"

    def test_closure_is_followup(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, decode = infer_cdisc_epoch_type("Study closure visit (SCV)")
        assert code == "C99158"
        assert decode == "Clinical Study Follow-up"

    def test_treatment_still_treatment(self):
        from core.reconciliation.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Treatment Period")
        assert code == "C101526"

    def test_legacy_reconciler_matches(self):
        """Ensure legacy epoch_reconciler.py has same behavior."""
        from core.epoch_reconciler import infer_cdisc_epoch_type
        code, _ = infer_cdisc_epoch_type("Enrolment")
        assert code == "C48262"
        code2, _ = infer_cdisc_epoch_type("Study closure visit")
        assert code2 == "C99158"


# ── H3: Admin→Intervention nesting ────────────────────────────────────

class TestH3NamesRelated:
    """Test InterventionsPhase._names_related semantic check."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from pipeline.phases.interventions import InterventionsPhase
        self.related = InterventionsPhase._names_related

    def test_drug_name_in_admin(self):
        assert self.related("Dapagliflozin", "Dapagliflozin 10 mg once daily")

    def test_placebo_matches_placebo(self):
        assert self.related("Placebo", "Placebo once daily")

    def test_dapagliflozin_not_placebo(self):
        assert not self.related("Placebo", "Dapagliflozin 5 mg once daily")

    def test_standard_of_care_not_placebo(self):
        assert not self.related("Standard of Care for HFrEF", "Placebo once daily")

    def test_empty_names(self):
        assert not self.related("", "Dapagliflozin 10 mg")
        assert not self.related("Dapagliflozin", "")

    def test_first_token_match(self):
        assert self.related("Osimertinib", "Osimertinib 80 mg once daily")

    def test_short_token_no_false_match(self):
        """Two-letter tokens should not trigger false matches."""
        assert not self.related("AB", "CD tablets")

    def test_bidirectional_containment(self):
        """Admin name contained in SI name (unusual but valid)."""
        assert self.related("Dapagliflozin 10 mg once daily", "Dapagliflozin")


class TestH3NestAdministrations:
    """Test _nest_administrations with semantic sanity check."""

    def _make_si(self, name, admin_ids=None):
        d = {"id": f"si_{name}", "name": name}
        if admin_ids:
            d["administrationIds"] = admin_ids
        return d

    def _make_admin(self, aid, name):
        return {"id": aid, "name": name}

    def test_correct_llm_linkage_preserved(self):
        """When LLM linkage is correct, admins nest properly."""
        from pipeline.phases.interventions import InterventionsPhase
        sis = [
            self._make_si("Dapagliflozin", ["a1"]),
            self._make_si("Placebo", ["a2"]),
        ]
        admins = [
            self._make_admin("a1", "Dapagliflozin 10 mg daily"),
            self._make_admin("a2", "Placebo once daily"),
        ]
        InterventionsPhase._nest_administrations(sis, admins)
        assert len(sis[0].get("administrations", [])) == 1
        assert sis[0]["administrations"][0]["name"] == "Dapagliflozin 10 mg daily"
        assert len(sis[1].get("administrations", [])) == 1
        assert sis[1]["administrations"][0]["name"] == "Placebo once daily"

    def test_wrong_llm_linkage_rejected_and_reassigned(self):
        """When LLM links Placebo SI to Dapagliflozin admin, sanity check rejects and Pass 2 fixes."""
        from pipeline.phases.interventions import InterventionsPhase
        sis = [
            self._make_si("Dapagliflozin", ["a1"]),
            self._make_si("Placebo", ["a2"]),  # LLM wrongly linked a2 (Dapagliflozin 5mg)
            self._make_si("Standard of Care", ["a3"]),  # LLM wrongly linked a3 (Placebo)
        ]
        admins = [
            self._make_admin("a1", "Dapagliflozin 10 mg daily"),
            self._make_admin("a2", "Dapagliflozin 5 mg daily"),
            self._make_admin("a3", "Placebo once daily"),
        ]
        InterventionsPhase._nest_administrations(sis, admins)
        # a1 should stay under Dapagliflozin
        dapa_admins = sis[0].get("administrations", [])
        assert any(a["id"] == "a1" for a in dapa_admins)
        # a2 (Dapagliflozin 5mg) should be re-assigned to Dapagliflozin by Pass 2
        assert any(a["id"] == "a2" for a in dapa_admins), (
            f"Expected a2 under Dapagliflozin, got: {[a['id'] for a in dapa_admins]}"
        )
        # a3 (Placebo) should be re-assigned to Placebo by Pass 2
        placebo_admins = sis[1].get("administrations", [])
        assert any(a["id"] == "a3" for a in placebo_admins), (
            f"Expected a3 under Placebo, got: {[a['id'] for a in placebo_admins]}"
        )

    def test_no_administrations_is_noop(self):
        from pipeline.phases.interventions import InterventionsPhase
        sis = [self._make_si("Drug A")]
        InterventionsPhase._nest_administrations(sis, [])
        assert "administrations" not in sis[0]

    def test_pass2_without_pass1_ids(self):
        """When no administrationIds at all, Pass 2 name-matching handles everything."""
        from pipeline.phases.interventions import InterventionsPhase
        sis = [
            self._make_si("Osimertinib"),
            self._make_si("Placebo"),
        ]
        admins = [
            self._make_admin("a1", "Osimertinib 80 mg tablet"),
            self._make_admin("a2", "Placebo tablet"),
        ]
        InterventionsPhase._nest_administrations(sis, admins)
        assert sis[0]["administrations"][0]["id"] == "a1"
        assert sis[1]["administrations"][0]["id"] == "a2"


class TestH3ExtractorLinkage:
    """Test _parse_interventions_response uses interventionName from LLM."""

    def test_intervention_name_linkage(self):
        from extraction.interventions.extractor import _parse_interventions_response
        raw = {
            "interventions": [
                {"name": "Dapagliflozin", "role": "Experimental Intervention", "type": "Drug"},
                {"name": "Placebo", "role": "Placebo", "type": "Drug"},
            ],
            "products": [],
            "substances": [],
            "administrations": [
                {"name": "Dapagliflozin 10 mg daily", "interventionName": "Dapagliflozin", "dose": "10 mg", "route": "Oral"},
                {"name": "Dapagliflozin 5 mg daily", "interventionName": "Dapagliflozin", "dose": "5 mg", "route": "Oral"},
                {"name": "Placebo once daily", "interventionName": "Placebo", "dose": "N/A", "route": "Oral"},
            ],
            "devices": [],
        }
        result = _parse_interventions_response(raw)
        assert result is not None
        dapa = next(iv for iv in result.interventions if iv.name == "Dapagliflozin")
        placebo = next(iv for iv in result.interventions if iv.name == "Placebo")
        # Dapagliflozin should have 2 admins, Placebo should have 1
        assert len(dapa.administration_ids) == 2
        assert len(placebo.administration_ids) == 1

    def test_legacy_positional_fallback(self):
        """Without interventionName, falls back to positional linkage."""
        from extraction.interventions.extractor import _parse_interventions_response
        raw = {
            "interventions": [
                {"name": "Drug A", "role": "Experimental Intervention", "type": "Drug"},
            ],
            "products": [],
            "substances": [],
            "administrations": [
                {"name": "Drug A 100 mg", "dose": "100 mg", "route": "Oral"},
            ],
            "devices": [],
        }
        result = _parse_interventions_response(raw)
        assert result is not None
        assert len(result.interventions[0].administration_ids) == 1
