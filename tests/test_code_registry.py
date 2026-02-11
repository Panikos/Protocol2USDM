"""
Tests for the centralized CodeRegistry.

Validates:
- Loading from usdm_ct.json
- Supplementary NCI EVS codelists
- Lookup, match, make_code operations
- Alias resolution
- UI export format
- Backward compatibility with terminology_codes.py
"""
import json
import pytest
from pathlib import Path

from core.code_registry import CodeRegistry, CodeList, CodeTerm, registry


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

class TestRegistryLoading:
    """Test that the registry loads correctly from JSON + supplementary."""

    def test_singleton_exists(self):
        assert registry is not None
        assert isinstance(registry, CodeRegistry)

    def test_has_usdm_ct_codelists(self):
        """All 25 USDM CT codelists should be loaded."""
        usdm_ct_keys = [
            "Encounter.type", "Endpoint.level", "Objective.level",
            "Organization.type", "StudyTitle.type", "Timing.type",
            "Timing.relativeToFrom", "StudyIntervention.role",
            "StudyArm.dataOriginType", "StudyDesign.characteristics",
            "AdministrableProduct.productDesignation",
            "AdministrableProduct.sourcing",
            "GeographicScope.type", "GovernanceDate.type",
            "StudyAmendmentReason.code", "StudyAmendmentImpact.type",
            "StudyDefinitionDocumentVersion.status",
            "StudyRole.code",
        ]
        for key in usdm_ct_keys:
            cl = registry.get_codelist(key)
            assert cl is not None, f"Missing USDM CT codelist: {key}"
            assert cl.source == "USDM_CT"

    def test_has_supplementary_codelists(self):
        """Supplementary NCI EVS codelists should be loaded."""
        supp_keys = [
            "StudyDesign.studyType", "StudyDesign.trialPhase",
            "Masking.blindingSchema", "StudyArm.type",
            "EligibilityCriterion.category", "StudyEpoch.type",
            "StudyDesign.model", "StudyIntervention.type",
            "Population.plannedSex", "Administration.route",
        ]
        for key in supp_keys:
            cl = registry.get_codelist(key)
            assert cl is not None, f"Missing supplementary codelist: {key}"
            assert cl.source == "NCI_EVS"

    def test_total_codelists(self):
        """Should have 25 USDM CT + supplementary codelists."""
        assert len(registry) >= 25 + 10  # at least 35 total

    def test_all_codes_flat(self):
        """all_codes_flat should return a non-empty dict."""
        flat = registry.all_codes_flat()
        assert isinstance(flat, dict)
        assert len(flat) > 100  # we know there are 178+


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------

class TestAliases:
    """Test that camelCase aliases resolve to canonical keys."""

    ALIAS_TESTS = [
        ("studyPhase", "StudyDesign.trialPhase"),
        ("studyType", "StudyDesign.studyType"),
        ("blindingSchema", "Masking.blindingSchema"),
        ("armType", "StudyArm.type"),
        ("epochType", "StudyEpoch.type"),
        ("encounterType", "Encounter.type"),
        ("objectiveLevel", "Objective.level"),
        ("endpointLevel", "Endpoint.level"),
        ("endpointPurpose", "Endpoint.level"),
        ("interventionRole", "StudyIntervention.role"),
        ("interventionType", "StudyIntervention.type"),
        ("organizationType", "Organization.type"),
        ("titleType", "StudyTitle.type"),
        ("timingType", "Timing.type"),
        ("timingRelativeToFrom", "Timing.relativeToFrom"),
        ("dataOriginType", "StudyArm.dataOriginType"),
        ("amendmentReason", "StudyAmendmentReason.code"),
        ("documentStatus", "StudyDefinitionDocumentVersion.status"),
        ("studyRoleCode", "StudyRole.code"),
        ("procedureType", "Procedure.type"),
    ]

    @pytest.mark.parametrize("alias,canonical", ALIAS_TESTS)
    def test_alias_resolves(self, alias, canonical):
        cl = registry.get_codelist(alias)
        assert cl is not None, f"Alias '{alias}' did not resolve"
        assert cl.key == canonical or registry._resolve(alias) == canonical

    def test_contains_by_alias(self):
        assert "studyPhase" in registry
        assert "blindingSchema" in registry
        assert "nonExistentAlias" not in registry


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

class TestLookup:
    """Test code lookup by C-code."""

    def test_lookup_objective_level(self):
        term = registry.lookup("Objective.level", "C85826")
        assert term is not None
        assert term.code == "C85826"
        assert term.decode == "Primary Objective"

    def test_lookup_endpoint_level(self):
        term = registry.lookup("endpointLevel", "C94496")
        assert term is not None
        assert term.decode == "Primary Endpoint"

    def test_lookup_encounter_type(self):
        term = registry.lookup("encounterType", "C25716")
        assert term is not None
        assert term.decode == "Visit"

    def test_lookup_missing_code(self):
        term = registry.lookup("Objective.level", "C99999")
        assert term is None

    def test_lookup_missing_codelist(self):
        term = registry.lookup("NonExistent.field", "C85826")
        assert term is None


# ---------------------------------------------------------------------------
# Match (fuzzy text)
# ---------------------------------------------------------------------------

class TestMatch:
    """Test fuzzy text matching."""

    def test_match_exact_decode(self):
        term = registry.match("Objective.level", "Primary Objective")
        assert term is not None
        assert term.code == "C85826"

    def test_match_partial(self):
        term = registry.match("studyPhase", "Phase III")
        assert term is not None
        assert term.code == "C15602"

    def test_match_case_insensitive(self):
        term = registry.match("blindingSchema", "double blind study")
        assert term is not None
        assert term.code == "C15228"

    def test_match_none(self):
        term = registry.match("Objective.level", "nonexistent level")
        assert term is None

    def test_match_empty(self):
        term = registry.match("Objective.level", "")
        assert term is None


# ---------------------------------------------------------------------------
# make_code
# ---------------------------------------------------------------------------

class TestMakeCode:
    """Test USDM Code dict generation."""

    def test_make_code_known(self):
        code = registry.make_code("Objective.level", "C85826")
        assert code["code"] == "C85826"
        assert code["decode"] == "Primary Objective"
        assert code["instanceType"] == "Code"
        assert code["codeSystem"] == "http://www.cdisc.org"
        assert code["codeSystemVersion"] == "2024-09-27"

    def test_make_code_unknown_falls_back(self):
        code = registry.make_code("Objective.level", "C99999")
        assert code["code"] == "C99999"
        assert code["decode"] == "C99999"  # falls back to code itself

    def test_make_code_from_text(self):
        code = registry.make_code_from_text("blindingSchema", "Double Blind Study")
        assert code["code"] == "C15228"
        assert code["decode"] == "Double Blind Study"

    def test_make_code_from_text_fallback(self):
        code = registry.make_code_from_text("blindingSchema", "Quadruple Blind")
        assert code["code"] == "Quadruple Blind"
        assert code["decode"] == "Quadruple Blind"


# ---------------------------------------------------------------------------
# Options (UI dropdown)
# ---------------------------------------------------------------------------

class TestOptions:
    """Test UI dropdown option generation."""

    def test_options_format(self):
        opts = registry.options("Objective.level")
        assert len(opts) == 3
        for opt in opts:
            assert "code" in opt
            assert "decode" in opt

    def test_options_by_alias(self):
        opts = registry.options("studyPhase")
        assert len(opts) >= 6  # Phase I through IV + combos + N/A

    def test_options_missing_codelist(self):
        opts = registry.options("NonExistent.field")
        assert opts == []


# ---------------------------------------------------------------------------
# UI export
# ---------------------------------------------------------------------------

class TestUIExport:
    """Test the export_for_ui method."""

    def test_export_has_aliases(self):
        ui = registry.export_for_ui()
        assert "studyPhase" in ui
        assert "blindingSchema" in ui
        assert "armType" in ui
        assert "organizationType" in ui

    def test_export_values_format(self):
        ui = registry.export_for_ui()
        for key, options in ui.items():
            assert isinstance(options, list)
            for opt in options:
                assert "code" in opt
                assert "decode" in opt

    def test_export_matches_generated_json(self):
        """The export should match what's in the generated JSON file."""
        json_path = Path(__file__).parent.parent / "web-ui" / "lib" / "codelist.generated.json"
        if not json_path.exists():
            pytest.skip("codelist.generated.json not found")
        with open(json_path) as f:
            generated = json.load(f)
        ui = registry.export_for_ui()
        # All generated keys should be in the export
        for key in generated:
            assert key in ui, f"Generated key '{key}' not in export"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """Test that terminology_codes.py still works via the registry."""

    def test_usdm_codes_registry_populated(self):
        from core.terminology_codes import USDM_CODES_REGISTRY
        assert len(USDM_CODES_REGISTRY) > 100
        assert "C85826" in USDM_CODES_REGISTRY
        assert USDM_CODES_REGISTRY["C85826"] == "Primary Objective"

    def test_get_objective_level_code(self):
        from core.terminology_codes import get_objective_level_code
        code = get_objective_level_code("primary")
        assert code["code"] == "C85826"
        assert code["instanceType"] == "Code"

    def test_get_endpoint_level_code(self):
        from core.terminology_codes import get_endpoint_level_code
        code = get_endpoint_level_code("secondary")
        assert code["code"] == "C139173"

    def test_legacy_dicts_still_exist(self):
        from core.terminology_codes import (
            OBJECTIVE_LEVEL_CODES,
            ENDPOINT_LEVEL_CODES,
            STUDY_PHASE_CODES,
            BLINDING_CODES,
            ELIGIBILITY_CODES,
            ARM_TYPE_CODES,
            STUDY_MODEL_CODES,
            STUDY_TYPE_CODES,
            ENCOUNTER_TYPE_CODES,
        )
        assert "primary" in OBJECTIVE_LEVEL_CODES
        assert "primary" in ENDPOINT_LEVEL_CODES
        assert "phase 3" in STUDY_PHASE_CODES
        assert "double blind" in BLINDING_CODES
        assert "inclusion" in ELIGIBILITY_CODES
        assert "experimental" in ARM_TYPE_CODES
        assert "parallel" in STUDY_MODEL_CODES
        assert "interventional" in STUDY_TYPE_CODES
        assert "visit" in ENCOUNTER_TYPE_CODES


# ---------------------------------------------------------------------------
# CodeList / CodeTerm data classes
# ---------------------------------------------------------------------------

class TestDataClasses:
    """Test CodeList and CodeTerm data classes."""

    def test_codelist_key(self):
        cl = CodeList(
            codelist_code="C188725",
            entity="Objective",
            attribute="level",
            extensible=False,
            terms=[CodeTerm("C85826", "Primary Objective")],
        )
        assert cl.key == "Objective.level"

    def test_codelist_lookup(self):
        cl = CodeList(
            codelist_code="C188725",
            entity="Objective",
            attribute="level",
            extensible=False,
            terms=[
                CodeTerm("C85826", "Primary Objective"),
                CodeTerm("C85827", "Secondary Objective"),
            ],
        )
        assert cl.lookup("C85826").decode == "Primary Objective"
        assert cl.lookup("C99999") is None

    def test_codelist_match(self):
        cl = CodeList(
            codelist_code="C188725",
            entity="Objective",
            attribute="level",
            extensible=False,
            terms=[
                CodeTerm("C85826", "Primary Objective"),
                CodeTerm("C85827", "Secondary Objective"),
            ],
        )
        assert cl.match("Primary Objective").code == "C85826"
        assert cl.match("primary").code == "C85826"
        assert cl.match("") is None
        assert cl.match(None) is None

    def test_codeterm_frozen(self):
        t = CodeTerm("C85826", "Primary Objective")
        with pytest.raises(AttributeError):
            t.code = "C99999"


# ---------------------------------------------------------------------------
# CDISC API adapter stub
# ---------------------------------------------------------------------------

class TestCDISCApiAdapter:
    """Test the CDISC API adapter stub."""

    def test_import(self):
        from core.cdisc_api_adapter import CDISCApiAdapter
        adapter = CDISCApiAdapter()
        assert adapter is not None

    def test_not_available_without_key(self):
        import os
        from core.cdisc_api_adapter import CDISCApiAdapter
        # Temporarily clear the env var
        old = os.environ.pop("CDISC_API_KEY", None)
        try:
            adapter = CDISCApiAdapter()
            assert not adapter.is_available
        finally:
            if old:
                os.environ["CDISC_API_KEY"] = old

    def test_fetch_raises(self):
        from core.cdisc_api_adapter import CDISCApiAdapter
        adapter = CDISCApiAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch_usdm_ct()

    def test_fetch_codelist_raises(self):
        from core.cdisc_api_adapter import CDISCApiAdapter
        adapter = CDISCApiAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch_codelist("C188725")

    def test_check_for_updates_raises(self):
        from core.cdisc_api_adapter import CDISCApiAdapter
        adapter = CDISCApiAdapter()
        with pytest.raises(NotImplementedError):
            adapter.check_for_updates()


# ---------------------------------------------------------------------------
# Specific USDM CT code verification
# ---------------------------------------------------------------------------

class TestUSDMCTCodes:
    """Verify specific codes from the USDM CT xlsx are correctly loaded."""

    def test_objective_level_codes(self):
        cl = registry.get_codelist("Objective.level")
        assert cl.codelist_code == "C188725"
        assert not cl.extensible
        codes = {t.code for t in cl.terms}
        assert codes == {"C85826", "C85827", "C163559"}

    def test_endpoint_level_codes(self):
        cl = registry.get_codelist("Endpoint.level")
        assert cl.codelist_code == "C188726"
        codes = {t.code for t in cl.terms}
        assert codes == {"C94496", "C139173", "C170559"}

    def test_organization_type_codes(self):
        cl = registry.get_codelist("Organization.type")
        assert cl.codelist_code == "C188724"
        assert cl.extensible
        assert len(cl.terms) == 9

    def test_study_title_type_codes(self):
        cl = registry.get_codelist("StudyTitle.type")
        assert cl.codelist_code == "C207419"
        codes = {t.code for t in cl.terms}
        assert "C207616" in codes  # Official Study Title
        assert "C94108" in codes   # Study Acronym

    def test_timing_type_codes(self):
        cl = registry.get_codelist("Timing.type")
        assert cl.codelist_code == "C201264"
        codes = {t.code for t in cl.terms}
        assert codes == {"C201356", "C201357", "C201358"}

    def test_timing_relative_to_from_codes(self):
        cl = registry.get_codelist("Timing.relativeToFrom")
        assert cl.codelist_code == "C201265"
        codes = {t.code for t in cl.terms}
        assert codes == {"C201352", "C201353", "C201354", "C201355"}

    def test_intervention_role_codes(self):
        cl = registry.get_codelist("StudyIntervention.role")
        assert cl.codelist_code == "C207417"
        assert not cl.extensible
        assert len(cl.terms) == 8

    def test_study_arm_data_origin_type(self):
        cl = registry.get_codelist("StudyArm.dataOriginType")
        assert cl.codelist_code == "C188727"
        codes = {t.code for t in cl.terms}
        assert "C188866" in codes  # Data Generated Within Study

    def test_amendment_reason_codes(self):
        cl = registry.get_codelist("StudyAmendmentReason.code")
        assert cl.codelist_code == "C207415"
        assert len(cl.terms) >= 14
