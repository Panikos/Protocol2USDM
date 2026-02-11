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
        assert sd["studyPhase"]["decode"] == "Phase 3"

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
        prev = {"metadata": {"metadata": {"studyPhase": {"code": "Phase 2", "codeSystem": "USDM", "decode": "Phase 2"}}}}
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        assert sd["studyPhase"]["decode"] == "Phase 2"


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
        eps = sd["endpoints"]
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
        assert sd["endpoints"][0]["purpose"] == "Efficacy"

    def test_exploratory_endpoint_gets_exploratory(self):
        from pipeline.phases.objectives import ObjectivesPhase
        phase = ObjectivesPhase()
        sv = {}
        sd = {}
        combined = {}
        result = _make_objectives_result([("Biomarker", "EXPLORATORY")])
        phase.combine(result, sv, sd, combined, {})
        assert sd["endpoints"][0]["purpose"] == "Exploratory"

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
                "objectives": {"objectives": [{"id": "o1"}], "endpoints": [
                    {"id": "ep1", "level": {"decode": "Primary Endpoint"}},
                    {"id": "ep2", "level": {"decode": "Secondary Endpoint"}, "purpose": "Safety"},
                ]}
            }
        }
        result = PhaseResult(success=False)
        phase.combine(result, sv, sd, combined, prev)
        eps = sd.get("endpoints", [])
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
        assert prod["ingredients"][0]["substanceId"] == "sub_1"
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
