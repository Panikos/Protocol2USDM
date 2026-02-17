"""Tests for core.core_compliance and pipeline.post_processing structural fixes."""
import copy
import pytest
from core.core_compliance import (
    normalize_for_core_compliance,
    _normalize_code_system,
    _walk_normalize_codes,
    _walk_generate_ids,
    _walk_populate_labels,
    _walk_sanitize_xhtml,
    _sanitize_xhtml_value,
    CDISC_CODE_SYSTEM,
    CDISC_CODE_SYSTEM_VERSION,
)
from pipeline.post_processing import (
    _extract_sort_key,
    build_ordering_chains,
    fix_primary_endpoint_linkage,
    fix_timing_references,
)


# ---------------------------------------------------------------------------
# 1. codeSystem normalization
# ---------------------------------------------------------------------------

class TestCodeSystemNormalization:

    def test_usdm_code_system_remapped(self):
        code = {"code": "C25532", "decode": "Inclusion", "codeSystem": "USDM", "codeSystemVersion": "2024-09-27"}
        fixed = _normalize_code_system(code, parent_key="category")
        assert fixed == 1
        assert code["codeSystem"] == CDISC_CODE_SYSTEM

    def test_usdm_sex_variant_remapped(self):
        code = {"code": "C16576", "decode": "Female", "codeSystem": "http://www.cdisc.org/USDM/sex", "codeSystemVersion": "2024-09-27"}
        fixed = _normalize_code_system(code, parent_key="plannedSex")
        assert fixed == 1
        assert code["codeSystem"] == CDISC_CODE_SYSTEM

    def test_evs_uri_on_ddf_parent_remapped(self):
        code = {"code": "C25532", "decode": "Inclusion", "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl", "codeSystemVersion": "26.01d"}
        fixed = _normalize_code_system(code, parent_key="category")
        assert fixed == 1
        assert code["codeSystem"] == CDISC_CODE_SYSTEM
        assert code["codeSystemVersion"] == CDISC_CODE_SYSTEM_VERSION

    def test_evs_uri_on_non_ddf_parent_kept(self):
        code = {"code": "C28221", "decode": "Venipuncture", "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl", "codeSystemVersion": "26.01d"}
        fixed = _normalize_code_system(code, parent_key="procedureCode")
        assert fixed == 0
        assert code["codeSystem"] == "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl"

    def test_already_cdisc_untouched(self):
        code = {"code": "C85826", "decode": "Primary", "codeSystem": "http://www.cdisc.org", "codeSystemVersion": "2024-09-27"}
        fixed = _normalize_code_system(code, parent_key="level")
        assert fixed == 0

    def test_blank_version_fixed_when_cdisc(self):
        code = {"code": "C85826", "decode": "Primary", "codeSystem": "http://www.cdisc.org", "codeSystemVersion": ""}
        fixed = _normalize_code_system(code, parent_key="level")
        assert fixed == 1
        assert code["codeSystemVersion"] == CDISC_CODE_SYSTEM_VERSION

    def test_non_code_dict_returns_zero(self):
        obj = {"name": "foo"}
        assert _normalize_code_system(obj) == 0

    def test_walk_normalizes_nested_codes(self):
        data = {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "eligibilityCriteria": [{
                            "id": "ec_1",
                            "category": {
                                "code": "C25532", "decode": "Inclusion",
                                "codeSystem": "USDM", "codeSystemVersion": "2024-09-27",
                                "instanceType": "Code",
                            }
                        }],
                        "objectives": [{
                            "id": "obj_1",
                            "level": {
                                "code": "C85826", "decode": "Primary",
                                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                                "codeSystemVersion": "26.01d",
                                "instanceType": "Code",
                            }
                        }]
                    }]
                }]
            }
        }
        fixed = _walk_normalize_codes(data)
        assert fixed == 2
        assert data["study"]["versions"][0]["studyDesigns"][0]["eligibilityCriteria"][0]["category"]["codeSystem"] == CDISC_CODE_SYSTEM
        assert data["study"]["versions"][0]["studyDesigns"][0]["objectives"][0]["level"]["codeSystem"] == CDISC_CODE_SYSTEM


# ---------------------------------------------------------------------------
# 2. Empty ID generation
# ---------------------------------------------------------------------------

class TestEmptyIdGeneration:

    def test_entity_with_empty_id_gets_uuid(self):
        obj = {"id": "", "instanceType": "Code", "code": "C25532", "decode": "Inclusion"}
        gen = _walk_generate_ids(obj)
        assert gen == 1
        assert len(obj["id"]) == 36  # UUID format

    def test_entity_with_none_id_gets_uuid(self):
        obj = {"id": None, "instanceType": "ExtensionAttribute", "url": "x-foo", "valueString": "bar"}
        gen = _walk_generate_ids(obj)
        assert gen == 1
        assert obj["id"] is not None

    def test_entity_with_existing_id_untouched(self):
        obj = {"id": "existing_id", "instanceType": "Activity", "name": "Test"}
        gen = _walk_generate_ids(obj)
        assert gen == 0
        assert obj["id"] == "existing_id"

    def test_code_without_instance_type_gets_id(self):
        obj = {"code": "C25532", "decode": "Inclusion", "id": ""}
        gen = _walk_generate_ids(obj)
        assert gen == 1
        assert len(obj["id"]) == 36

    def test_walk_generates_nested_ids(self):
        data = {
            "activities": [
                {"id": "act_1", "instanceType": "Activity", "definedProcedures": [
                    {"id": "", "instanceType": "Procedure", "name": "ECG"}
                ]}
            ]
        }
        gen = _walk_generate_ids(data)
        assert gen == 1
        assert len(data["activities"][0]["definedProcedures"][0]["id"]) == 36


# ---------------------------------------------------------------------------
# 3. Label / description population
# ---------------------------------------------------------------------------

class TestLabelPopulation:

    def test_activity_gets_label_from_name(self):
        obj = {"instanceType": "Activity", "name": "Blood draw", "id": "act_1"}
        pop = _walk_populate_labels(obj)
        assert pop >= 1
        assert obj["label"] == "Blood draw"

    def test_activity_gets_description_from_name(self):
        obj = {"instanceType": "Activity", "name": "Blood draw", "id": "act_1"}
        _walk_populate_labels(obj)
        assert obj["description"] == "Blood draw"

    def test_existing_label_not_overwritten(self):
        obj = {"instanceType": "Activity", "name": "Blood draw", "label": "Custom label", "id": "act_1"}
        _walk_populate_labels(obj)
        assert obj["label"] == "Custom label"

    def test_encounter_gets_label(self):
        obj = {"instanceType": "Encounter", "name": "Visit 1", "id": "enc_1"}
        _walk_populate_labels(obj)
        assert obj["label"] == "Visit 1"

    def test_objective_gets_label(self):
        obj = {"instanceType": "Objective", "name": "Primary Objective", "id": "obj_1"}
        _walk_populate_labels(obj)
        assert obj["label"] == "Primary Objective"

    def test_non_entity_type_ignored(self):
        obj = {"instanceType": "Code", "code": "C25532"}
        pop = _walk_populate_labels(obj)
        assert pop == 0

    def test_no_name_no_label(self):
        obj = {"instanceType": "Activity", "id": "act_1"}
        pop = _walk_populate_labels(obj)
        assert pop == 0


# ---------------------------------------------------------------------------
# 4. XHTML sanitization
# ---------------------------------------------------------------------------

class TestXhtmlSanitization:

    def test_raw_angle_bracket_escaped(self):
        text = "Value must be < 10 mg/dL"
        result = _sanitize_xhtml_value(text)
        assert "&lt;" in result
        assert "< 10" not in result

    def test_valid_xml_tag_preserved(self):
        text = "<div>Hello</div>"
        result = _sanitize_xhtml_value(text)
        assert result == text

    def test_no_brackets_unchanged(self):
        text = "Normal text without brackets"
        result = _sanitize_xhtml_value(text)
        assert result == text

    def test_walk_sanitizes_text_fields(self):
        data = {
            "conditions": [
                {"id": "cond_1", "text": "eGFR < 30 mL/min", "name": "Renal Exclusion"}
            ]
        }
        sanitized = _walk_sanitize_xhtml(data)
        assert sanitized == 1
        assert "&lt;" in data["conditions"][0]["text"]

    def test_non_text_keys_untouched(self):
        data = {"name": "value < 10", "id": "x"}
        sanitized = _walk_sanitize_xhtml(data)
        assert sanitized == 0
        assert data["name"] == "value < 10"


# ---------------------------------------------------------------------------
# Integration: normalize_for_core_compliance
# ---------------------------------------------------------------------------

class TestNormalizeForCoreCompliance:

    def test_full_pipeline_returns_stats(self):
        data = {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "activities": [
                            {"id": "act_1", "instanceType": "Activity", "name": "ECG"},
                        ],
                        "eligibilityCriteria": [{
                            "id": "ec_1",
                            "category": {
                                "code": "C25532", "decode": "Inclusion",
                                "codeSystem": "USDM", "id": "",
                                "instanceType": "Code",
                            }
                        }],
                    }]
                }]
            }
        }
        result, stats = normalize_for_core_compliance(data)
        assert stats["codes_fixed"] >= 1
        assert stats["ids_generated"] >= 1
        assert stats["labels_populated"] >= 1
        # Verify original data was deep-copied
        assert data["study"]["versions"][0]["studyDesigns"][0]["eligibilityCriteria"][0]["category"]["codeSystem"] == "USDM"

    def test_does_not_mutate_input(self):
        data = {"study": {"versions": [{"studyDesigns": [{"activities": []}]}]}}
        original = copy.deepcopy(data)
        normalize_for_core_compliance(data)
        assert data == original


# ---------------------------------------------------------------------------
# 5. Ordering Chains
# ---------------------------------------------------------------------------

class TestExtractSortKey:

    def test_day_positive(self):
        assert _extract_sort_key("Day 1") == 1.0

    def test_day_negative(self):
        assert _extract_sort_key("Check-in (Day -8)") == -8.0

    def test_week(self):
        assert _extract_sort_key("Visit 3a (Week 0)") == 0.0  # day-scale: 0*7

    def test_visit_number(self):
        assert _extract_sort_key("Visit 5") == 0.05

    def test_terminal_pushed_to_end(self):
        assert _extract_sort_key("EOS or ET") >= 9000.0
        assert _extract_sort_key("PTDV") >= 9000.0
        assert _extract_sort_key("Unscheduled") >= 9000.0

    def test_empty_name(self):
        assert _extract_sort_key("") == 9999.0

    def test_ordering_correctness(self):
        names = ["Day 8", "Day -7", "Day 1", "EOS Day 54"]
        sorted_names = sorted(names, key=_extract_sort_key)
        assert sorted_names == ["Day -7", "Day 1", "Day 8", "EOS Day 54"]


class TestBuildOrderingChains:

    def test_encounter_chain_built(self):
        sd = {
            "encounters": [
                {"id": "enc_3", "name": "Day 8"},
                {"id": "enc_1", "name": "Day -7"},
                {"id": "enc_2", "name": "Day 1"},
            ],
            "epochs": [],
        }
        linked = build_ordering_chains(sd)
        assert linked >= 4  # at least 2 previousId + 2 nextId
        # Verify chain order: enc_1 → enc_2 → enc_3
        by_id = {e["id"]: e for e in sd["encounters"]}
        assert "previousId" not in by_id["enc_1"] or by_id["enc_1"].get("previousId") is None
        assert by_id["enc_1"]["nextId"] == "enc_2"
        assert by_id["enc_2"]["previousId"] == "enc_1"
        assert by_id["enc_2"]["nextId"] == "enc_3"
        assert by_id["enc_3"]["previousId"] == "enc_2"
        assert by_id["enc_3"].get("nextId") is None

    def test_epoch_chain_uses_array_position(self):
        """Epochs use array position (reconciler output order), not name heuristics."""
        sd = {
            "epochs": [
                {"id": "ep_screen", "name": "Screening"},
                {"id": "ep_treat", "name": "Treatment"},
                {"id": "ep_eos", "name": "EOS"},
            ],
            "encounters": [
                {"id": "enc_1", "name": "Day -7", "epochId": "ep_screen"},
                {"id": "enc_2", "name": "Day 1", "epochId": "ep_treat"},
                {"id": "enc_3", "name": "Day 54", "epochId": "ep_eos"},
            ],
        }
        build_ordering_chains(sd)
        by_id = {e["id"]: e for e in sd["epochs"]}
        # Chain follows array position: Screening → Treatment → EOS
        assert by_id["ep_screen"]["nextId"] == "ep_treat"
        assert by_id["ep_treat"]["previousId"] == "ep_screen"
        assert by_id["ep_treat"]["nextId"] == "ep_eos"
        assert by_id["ep_eos"]["previousId"] == "ep_treat"

    def test_epoch_chain_preserves_reconciler_order(self):
        """Even with non-numeric epoch names (Wilson-like), array order is preserved."""
        sd = {
            "epochs": [
                {"id": "ep_1", "name": "Screening"},
                {"id": "ep_2", "name": "C-I"},
                {"id": "ep_3", "name": "Inpatient Period 1"},
                {"id": "ep_4", "name": "OP"},
                {"id": "ep_5", "name": "Inpatient Period 2"},
                {"id": "ep_6", "name": "EOS or ET"},
            ],
            "encounters": [],
        }
        build_ordering_chains(sd)
        # Chain follows array position exactly
        assert sd["epochs"][0].get("previousId") is None
        assert sd["epochs"][0]["nextId"] == "ep_2"
        assert sd["epochs"][3]["previousId"] == "ep_3"
        assert sd["epochs"][3]["nextId"] == "ep_5"
        assert sd["epochs"][5]["previousId"] == "ep_5"
        assert sd["epochs"][5].get("nextId") is None

    def test_single_encounter_no_chain(self):
        sd = {"encounters": [{"id": "enc_1", "name": "Day 1"}], "epochs": []}
        linked = build_ordering_chains(sd)
        assert linked == 0

    def test_empty_design(self):
        assert build_ordering_chains({"epochs": [], "encounters": []}) == 0


# ---------------------------------------------------------------------------
# 6. Primary Endpoint Linkage
# ---------------------------------------------------------------------------

class TestPrimaryEndpointLinkage:

    def test_links_primary_endpoint_to_objective(self):
        sd = {
            "objectives": [
                {
                    "id": "obj_1",
                    "level": {"code": "C85826", "decode": "Primary"},
                    "endpoints": [
                        {"id": "ep_2", "level": {"code": "C139173", "decode": "Secondary"}},
                    ],
                },
                {
                    "id": "obj_2",
                    "level": {"code": "C85827", "decode": "Secondary"},
                    "endpoints": [
                        {"id": "ep_1", "level": {"code": "C94496", "decode": "Primary"}},
                    ],
                },
            ],
        }
        fixed = fix_primary_endpoint_linkage(sd)
        assert fixed == 1
        # Primary endpoint should now be nested in primary objective
        primary_obj_eps = sd["objectives"][0]["endpoints"]
        assert any(ep["id"] == "ep_1" for ep in primary_obj_eps)

    def test_already_linked_no_change(self):
        sd = {
            "objectives": [{
                "id": "obj_1",
                "level": {"code": "C85826", "decode": "Primary"},
                "endpoints": [
                    {"id": "ep_1", "level": {"code": "C94496", "decode": "Primary"}},
                ],
            }],
        }
        fixed = fix_primary_endpoint_linkage(sd)
        assert fixed == 0

    def test_no_primary_objective_no_fix(self):
        sd = {
            "objectives": [{"id": "obj_1", "level": {"code": "C85827"}, "endpoints": [
                {"id": "ep_1", "level": {"code": "C94496"}},
            ]}],
        }
        assert fix_primary_endpoint_linkage(sd) == 0

    def test_no_primary_endpoint_no_fix(self):
        sd = {
            "objectives": [{"id": "obj_1", "level": {"code": "C85826"}, "endpoints": [
                {"id": "ep_1", "level": {"code": "C139173"}},
            ]}],
        }
        assert fix_primary_endpoint_linkage(sd) == 0

    def test_empty_design(self):
        assert fix_primary_endpoint_linkage({"objectives": []}) == 0


# ---------------------------------------------------------------------------
# 7. Timing Reference IDs
# ---------------------------------------------------------------------------

class TestFixTimingReferences:

    def test_populates_relative_to(self):
        sd = {
            "scheduleTimelines": [{
                "entryId": "anchor_1",
                "timings": [
                    {"id": "t1", "relativeFromScheduledInstanceId": "inst_1"},
                    {"id": "t2", "relativeFromScheduledInstanceId": "inst_2"},
                ],
                "instances": [],
            }]
        }
        fixed = fix_timing_references(sd)
        assert fixed == 2
        assert sd["scheduleTimelines"][0]["timings"][0]["relativeToScheduledInstanceId"] == "anchor_1"
        assert sd["scheduleTimelines"][0]["timings"][1]["relativeToScheduledInstanceId"] == "anchor_1"

    def test_skips_already_populated(self):
        sd = {
            "scheduleTimelines": [{
                "entryId": "anchor_1",
                "timings": [
                    {"id": "t1", "relativeFromScheduledInstanceId": "inst_1", "relativeToScheduledInstanceId": "inst_2"},
                ],
                "instances": [],
            }]
        }
        fixed = fix_timing_references(sd)
        assert fixed == 0
        assert sd["scheduleTimelines"][0]["timings"][0]["relativeToScheduledInstanceId"] == "inst_2"

    def test_skips_no_from(self):
        sd = {
            "scheduleTimelines": [{
                "entryId": "anchor_1",
                "timings": [
                    {"id": "t1"},
                ],
                "instances": [],
            }]
        }
        assert fix_timing_references(sd) == 0

    def test_falls_back_to_first_instance(self):
        sd = {
            "scheduleTimelines": [{
                "timings": [
                    {"id": "t1", "relativeFromScheduledInstanceId": "inst_1"},
                ],
                "instances": [{"id": "first_inst"}],
            }]
        }
        fixed = fix_timing_references(sd)
        assert fixed == 1
        assert sd["scheduleTimelines"][0]["timings"][0]["relativeToScheduledInstanceId"] == "first_inst"

    def test_no_timelines(self):
        assert fix_timing_references({"scheduleTimelines": []}) == 0
