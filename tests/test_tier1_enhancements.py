"""
Tests for Tier 1 Platform Enhancements.

OBJ-1: Resolve estimand → intervention ID links
OBJ-2: Resolve estimand → population ID links (existing, verify robustness)
DES-1: TransitionRule extraction
DES-3: Duration extraction as ISO 8601
(more added as enhancements are implemented)
"""

import pytest
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.integrations import (
    reconcile_estimand_intervention_refs,
    reconcile_estimand_population_refs,
    reconcile_estimand_endpoint_refs,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _uid():
    return str(uuid.uuid4())


def _make_intervention(name, role_decode="Experimental Intervention", label=None, admins=None):
    si = {
        "id": _uid(),
        "name": name,
        "role": {"code": "C174266", "decode": role_decode, "instanceType": "Code"},
        "instanceType": "StudyIntervention",
    }
    if label:
        si["label"] = label
    if admins:
        si["administrations"] = admins
    return si


def _make_estimand(name, treatment_text=None, intervention_ids=None, pop_text=None, var_text=None):
    return {
        "id": _uid(),
        "name": name,
        "treatment": treatment_text or "",
        "interventionIds": intervention_ids or [f"placeholder_{_uid()[:8]}"],
        "analysisPopulationId": f"placeholder_{_uid()[:8]}",
        "analysisPopulation": pop_text or "Intent-to-treat population",
        "populationSummary": pop_text or "ITT",
        "variableOfInterestId": f"placeholder_{_uid()[:8]}",
        "variableOfInterest": var_text or "Primary endpoint",
        "intercurrentEvents": [],
        "instanceType": "Estimand",
    }


def _make_population(name, label=None, pop_type="Analysis"):
    return {
        "id": _uid(),
        "name": name,
        "label": label or name,
        "populationType": pop_type,
        "text": name,
        "instanceType": "AnalysisPopulation",
    }


def _make_endpoint(name, level_decode="Primary"):
    return {
        "id": _uid(),
        "name": name,
        "text": name,
        "level": {"code": "C98772", "decode": level_decode, "instanceType": "Code"},
        "instanceType": "Endpoint",
    }


# ─────────────────────────────────────────────────────────────
# OBJ-1: Estimand → Intervention ID Resolution
# ─────────────────────────────────────────────────────────────

class TestOBJ1InterventionReconciliation:

    def test_exact_name_match(self):
        si = _make_intervention("Drug A 200mg")
        est = _make_estimand("Primary Estimand", treatment_text="Drug A 200mg")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert est["interventionIds"] == [si["id"]]

    def test_case_insensitive_match(self):
        si = _make_intervention("Pembrolizumab")
        est = _make_estimand("Primary", treatment_text="pembrolizumab")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert est["interventionIds"] == [si["id"]]

    def test_substring_match(self):
        si = _make_intervention("Drug A")
        est = _make_estimand("Primary", treatment_text="Drug A 200mg once daily vs placebo")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert si["id"] in est["interventionIds"]

    def test_word_overlap_match(self):
        si = _make_intervention("Trastuzumab emtansine (T-DM1)")
        est = _make_estimand("Primary", treatment_text="trastuzumab emtansine treatment arm")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert si["id"] in est["interventionIds"]

    def test_already_valid_ids_skipped(self):
        si = _make_intervention("Drug A")
        est = _make_estimand("Primary", intervention_ids=[si["id"]])
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert est["interventionIds"] == [si["id"]]

    def test_fallback_to_investigational(self):
        si_imp = _make_intervention("Drug A", role_decode="Experimental Intervention")
        si_placebo = _make_intervention("Placebo", role_decode="Placebo")
        est = _make_estimand("Primary", treatment_text="completely unrelated text xyz")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si_imp, si_placebo]}
        reconcile_estimand_intervention_refs(sd, sv)
        # Should fall back to investigational intervention
        assert si_imp["id"] in est["interventionIds"]

    def test_no_estimands_noop(self):
        sd = {"estimands": []}
        sv = {"studyInterventions": [_make_intervention("Drug A")]}
        reconcile_estimand_intervention_refs(sd, sv)
        # No error

    def test_no_interventions_noop(self):
        est = _make_estimand("Primary", treatment_text="Drug A")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": []}
        reconcile_estimand_intervention_refs(sd, sv)
        # interventionIds unchanged (still placeholder)
        assert "placeholder" in est["interventionIds"][0]

    def test_multiple_estimands(self):
        si_a = _make_intervention("Drug A")
        si_b = _make_intervention("Drug B")
        est1 = _make_estimand("Primary", treatment_text="Drug A arm")
        est2 = _make_estimand("Secondary", treatment_text="Drug B arm")
        sd = {"estimands": [est1, est2]}
        sv = {"studyInterventions": [si_a, si_b]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert si_a["id"] in est1["interventionIds"]
        assert si_b["id"] in est2["interventionIds"]

    def test_administration_name_match(self):
        si = _make_intervention(
            "Study Drug",
            admins=[{"name": "Nivolumab 240mg IV Q2W"}],
        )
        est = _make_estimand("Primary", treatment_text="nivolumab")
        sd = {"estimands": [est]}
        sv = {"studyInterventions": [si]}
        reconcile_estimand_intervention_refs(sd, sv)
        assert si["id"] in est["interventionIds"]


# ─────────────────────────────────────────────────────────────
# OBJ-2: Estimand → Population ID Resolution (robustness)
# ─────────────────────────────────────────────────────────────

class TestOBJ2PopulationReconciliation:

    def test_exact_name_match(self):
        pop = _make_population("Intent-to-Treat Population")
        est = _make_estimand("Primary", pop_text="Intent-to-Treat Population")
        sd = {"estimands": [est], "analysisPopulations": [pop]}
        reconcile_estimand_population_refs(sd)
        assert est["analysisPopulationId"] == pop["id"]

    def test_itt_fas_alias(self):
        pop = _make_population("Full Analysis Set")
        est = _make_estimand("Primary", pop_text="Intent-to-treat population")
        sd = {"estimands": [est], "analysisPopulations": [pop]}
        reconcile_estimand_population_refs(sd)
        assert est["analysisPopulationId"] == pop["id"]

    def test_safety_alias(self):
        pop = _make_population("Safety Set")
        est = _make_estimand("Safety", pop_text="Safety population")
        sd = {"estimands": [est], "analysisPopulations": [pop]}
        reconcile_estimand_population_refs(sd)
        assert est["analysisPopulationId"] == pop["id"]

    def test_creates_population_when_missing(self):
        est = _make_estimand("Primary", pop_text="Modified ITT population")
        sd = {"estimands": [est], "analysisPopulations": []}
        reconcile_estimand_population_refs(sd)
        # Should have created a new AnalysisPopulation
        assert len(sd["analysisPopulations"]) >= 1
        assert est["analysisPopulationId"] == sd["analysisPopulations"][0]["id"]

    def test_already_valid_skipped(self):
        pop = _make_population("ITT")
        est = _make_estimand("Primary", pop_text="ITT")
        est["analysisPopulationId"] = pop["id"]  # Already correct
        sd = {"estimands": [est], "analysisPopulations": [pop]}
        reconcile_estimand_population_refs(sd)
        assert est["analysisPopulationId"] == pop["id"]

    def test_word_overlap_match(self):
        pop = _make_population("Per-Protocol Analysis Population")
        est = _make_estimand("Secondary", pop_text="Per protocol population as defined in the SAP")
        sd = {"estimands": [est], "analysisPopulations": [pop]}
        reconcile_estimand_population_refs(sd)
        assert est["analysisPopulationId"] == pop["id"]


# ─────────────────────────────────────────────────────────────
# OBJ Endpoint Reconciliation (verify existing)
# ─────────────────────────────────────────────────────────────

class TestEndpointReconciliation:

    def test_exact_name_match(self):
        ep = _make_endpoint("Overall Survival")
        est = _make_estimand("Primary", var_text="Overall Survival")
        sd = {
            "estimands": [est],
            "objectives": [{"id": _uid(), "endpoints": [ep]}],
        }
        reconcile_estimand_endpoint_refs(sd)
        assert est["variableOfInterestId"] == ep["id"]

    def test_level_based_match(self):
        ep_primary = _make_endpoint("OS", level_decode="Primary")
        ep_secondary = _make_endpoint("PFS", level_decode="Secondary")
        est = _make_estimand("Primary", var_text="unmatched text")
        est["level"] = {"decode": "Primary"}
        sd = {
            "estimands": [est],
            "objectives": [{"id": _uid(), "endpoints": [ep_primary, ep_secondary]}],
        }
        reconcile_estimand_endpoint_refs(sd)
        assert est["variableOfInterestId"] == ep_primary["id"]


# ─────────────────────────────────────────────────────────────
# DES-1: TransitionRule on StudyElement
# ─────────────────────────────────────────────────────────────

from pipeline.post_processing import (
    promote_transition_rules_to_elements,
    _order_by_chain,
    _get_state_machine_transitions,
    _find_sm_rule,
)


def _make_combined_with_elements(epochs, elements, cells, sm_transitions=None):
    """Build minimal combined dict for DES-1 tests."""
    sd = {
        "epochs": epochs,
        "studyElements": elements,
        "studyCells": cells,
        "extensionAttributes": [],
    }
    if sm_transitions:
        sd["extensionAttributes"].append({
            "url": "https://protocol2usdm.io/extensions/x-executionModel-stateMachine",
            "valueObject": {"transitions": sm_transitions},
        })
    return {
        "study": {
            "versions": [{
                "studyDesigns": [sd],
            }],
        },
    }


class TestDES1TransitionRules:

    def test_creates_rules_for_elements(self):
        ep1 = {"id": "ep1", "name": "Screening", "type": {"decode": "Screening"}}
        ep2 = {"id": "ep2", "name": "Treatment", "type": {"decode": "Treatment Period"}}
        el1 = {"id": "el1", "name": "Screening Element"}
        el2 = {"id": "el2", "name": "Treatment Element"}
        cells = [
            {"epochId": "ep1", "elementIds": ["el1"]},
            {"epochId": "ep2", "elementIds": ["el2"]},
        ]
        combined = _make_combined_with_elements([ep1, ep2], [el1, el2], cells)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        for el in sd["studyElements"]:
            assert "transitionStartRule" in el
            assert "transitionEndRule" in el
            assert el["transitionStartRule"]["instanceType"] == "TransitionRule"
            assert el["transitionEndRule"]["instanceType"] == "TransitionRule"

    def test_screening_epoch_uses_element_name(self):
        ep = {"id": "ep1", "name": "Screening Period", "type": {"decode": "Screening"}}
        el = {"id": "el1", "name": "Screening"}
        cells = [{"epochId": "ep1", "elementIds": ["el1"]}]
        combined = _make_combined_with_elements([ep], [el], cells)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        el_out = sd["studyElements"][0]
        assert "Screening" in el_out["transitionStartRule"]["text"]

    def test_treatment_epoch_uses_element_name(self):
        ep = {"id": "ep1", "name": "Treatment", "type": {"decode": "Treatment"}}
        el = {"id": "el1", "name": "Treatment"}
        cells = [{"epochId": "ep1", "elementIds": ["el1"]}]
        combined = _make_combined_with_elements([ep], [el], cells)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        el_out = sd["studyElements"][0]
        assert "Treatment" in el_out["transitionStartRule"]["text"]

    def test_follow_up_epoch_uses_element_name(self):
        ep = {"id": "ep1", "name": "Follow-up", "type": {"decode": "Follow-up"}}
        el = {"id": "el1", "name": "Follow-up"}
        cells = [{"epochId": "ep1", "elementIds": ["el1"]}]
        combined = _make_combined_with_elements([ep], [el], cells)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        el_out = sd["studyElements"][0]
        assert "Follow-up" in el_out["transitionStartRule"]["text"]

    def test_state_machine_enrichment(self):
        ep = {"id": "ep1", "name": "Treatment", "type": {"decode": "Treatment"}}
        el = {"id": "el1", "name": "Treatment Element"}
        cells = [{"epochId": "ep1", "elementIds": ["el1"]}]
        sm_transitions = [
            {"fromState": "Screening", "toState": "Treatment", "trigger": "Randomization visit completed"},
        ]
        combined = _make_combined_with_elements([ep], [el], cells, sm_transitions)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        el_out = sd["studyElements"][0]
        assert "Randomization visit completed" in el_out["transitionStartRule"]["text"]

    def test_preserves_existing_rules(self):
        ep = {"id": "ep1", "name": "Treatment", "type": {"decode": "Treatment"}}
        existing_rule = {"id": "existing", "name": "Custom", "text": "Custom rule", "instanceType": "TransitionRule"}
        el = {"id": "el1", "name": "Treatment", "transitionStartRule": existing_rule}
        cells = [{"epochId": "ep1", "elementIds": ["el1"]}]
        combined = _make_combined_with_elements([ep], [el], cells)
        promote_transition_rules_to_elements(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        el_out = sd["studyElements"][0]
        assert el_out["transitionStartRule"]["text"] == "Custom rule"
        assert "transitionEndRule" in el_out  # End rule should still be created

    def test_no_elements_noop(self):
        combined = _make_combined_with_elements(
            [{"id": "ep1", "name": "Treatment"}], [], []
        )
        result = promote_transition_rules_to_elements(combined)
        assert result is not None  # No error

    def test_no_epochs_noop(self):
        combined = _make_combined_with_elements(
            [], [{"id": "el1", "name": "Element"}], []
        )
        result = promote_transition_rules_to_elements(combined)
        assert result is not None


class TestOrderByChain:

    def test_ordered_chain(self):
        epochs = [
            {"id": "ep1", "name": "Screening", "nextId": "ep2"},
            {"id": "ep2", "name": "Treatment", "previousId": "ep1", "nextId": "ep3"},
            {"id": "ep3", "name": "Follow-up", "previousId": "ep2"},
        ]
        result = _order_by_chain(epochs)
        assert result == ["ep1", "ep2", "ep3"]

    def test_empty(self):
        assert _order_by_chain([]) == []

    def test_single_epoch(self):
        result = _order_by_chain([{"id": "ep1", "name": "Treatment"}])
        assert result == ["ep1"]


class TestStateMachineHelpers:

    def test_get_transitions(self):
        sd = {
            "extensionAttributes": [{
                "url": "https://protocol2usdm.io/extensions/x-executionModel-stateMachine",
                "valueObject": {"transitions": [{"fromState": "A", "toState": "B", "trigger": "Go"}]},
            }],
        }
        result = _get_state_machine_transitions(sd)
        assert len(result) == 1
        assert result[0]["trigger"] == "Go"

    def test_no_sm(self):
        assert _get_state_machine_transitions({"extensionAttributes": []}) == []

    def test_find_sm_rule_start(self):
        transitions = [
            {"fromState": "Screening", "toState": "Treatment", "trigger": "Randomized"},
        ]
        epoch = {"name": "Treatment"}
        assert _find_sm_rule(transitions, epoch, "start") == "Randomized"

    def test_find_sm_rule_end(self):
        transitions = [
            {"fromState": "Treatment", "toState": "Follow-up", "trigger": "Last dose given"},
        ]
        epoch = {"name": "Treatment"}
        assert _find_sm_rule(transitions, epoch, "end") == "Last dose given"

    def test_find_sm_rule_with_guard(self):
        transitions = [
            {"fromState": "Screening", "toState": "Treatment", "trigger": "Eligible", "guardCondition": "All criteria met"},
        ]
        epoch = {"name": "Treatment"}
        result = _find_sm_rule(transitions, epoch, "start")
        assert "Eligible" in result
        assert "All criteria met" in result

    def test_find_sm_rule_no_match(self):
        transitions = [
            {"fromState": "A", "toState": "B", "trigger": "Go"},
        ]
        epoch = {"name": "Treatment"}
        assert _find_sm_rule(transitions, epoch, "start") == ""


# ─────────────────────────────────────────────────────────────
# DES-3: Duration Extraction as ISO 8601
# ─────────────────────────────────────────────────────────────

from pipeline.post_processing import (
    normalize_durations_to_iso8601,
    _parse_duration_text,
    _iso_to_days,
    _make_duration_entity,
    _iso_unit_decode,
)


class TestParseDurationText:

    def test_days(self):
        assert _parse_duration_text("28-day screening period") == "P28D"

    def test_weeks(self):
        assert _parse_duration_text("12 weeks treatment") == "P12W"

    def test_months(self):
        assert _parse_duration_text("6 months follow-up") == "P6M"

    def test_years(self):
        assert _parse_duration_text("2 year extension study") == "P2Y"

    def test_hours(self):
        assert _parse_duration_text("2 hours infusion") == "PT2H"

    def test_minutes(self):
        assert _parse_duration_text("30 minutes observation") == "PT30M"

    def test_already_iso(self):
        assert _parse_duration_text("P14D") == "P14D"

    def test_empty(self):
        assert _parse_duration_text("") == ""

    def test_no_match(self):
        assert _parse_duration_text("some random text") == ""

    def test_abbreviation_wk(self):
        assert _parse_duration_text("4 wk washout") == "P4W"


class TestIsoToDays:

    def test_days(self):
        assert _iso_to_days("P28D") == 28

    def test_weeks(self):
        assert _iso_to_days("P4W") == 28

    def test_months(self):
        assert _iso_to_days("P6M") == 180

    def test_years(self):
        assert _iso_to_days("P1Y") == 365

    def test_hours(self):
        assert _iso_to_days("PT2H") == 1

    def test_empty(self):
        assert _iso_to_days("") == 0


class TestNormalizeDurations:

    def test_epoch_duration_extraction(self):
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "epochs": [
                    {"id": "ep1", "name": "28-day Screening Period"},
                    {"id": "ep2", "name": "12-week Treatment Period"},
                ],
                "scheduleTimelines": [{"id": "tl1"}],
            }]}]},
        }
        normalize_durations_to_iso8601(combined)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        assert sd["epochs"][0].get("_duration_iso") == "P28D"
        assert sd["epochs"][1].get("_duration_iso") == "P12W"

    def test_timeline_planned_duration(self):
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "epochs": [
                    {"id": "ep1", "name": "28-day Screening"},
                    {"id": "ep2", "name": "84-day Treatment"},
                ],
                "scheduleTimelines": [{"id": "tl1"}],
            }]}]},
        }
        normalize_durations_to_iso8601(combined)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        tl = sd["scheduleTimelines"][0]
        assert "plannedDuration" in tl
        assert tl["plannedDuration"]["instanceType"] == "Duration"
        # 28 + 84 = 112 days
        assert "112" in tl["plannedDuration"]["text"]

    def test_timing_window_normalization(self):
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "epochs": [],
                "scheduleTimelines": [{
                    "id": "tl1",
                    "timings": [
                        {"id": "t1", "windowLower": "2 days", "windowUpper": "3 days"},
                    ],
                }],
            }]}]},
        }
        normalize_durations_to_iso8601(combined)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        t = sd["scheduleTimelines"][0]["timings"][0]
        assert t["windowLower"] == "P2D"
        assert t["windowUpper"] == "P3D"

    def test_preserves_existing_planned_duration(self):
        existing = {"id": "dur1", "text": "Already set", "instanceType": "Duration"}
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "epochs": [{"id": "ep1", "name": "28-day Screening"}],
                "scheduleTimelines": [{"id": "tl1", "plannedDuration": existing}],
            }]}]},
        }
        normalize_durations_to_iso8601(combined)
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        assert sd["scheduleTimelines"][0]["plannedDuration"]["text"] == "Already set"

    def test_noop_on_empty(self):
        combined = {"study": {"versions": [{"studyDesigns": [{"epochs": [], "scheduleTimelines": []}]}]}}
        result = normalize_durations_to_iso8601(combined)
        assert result is not None


class TestDurationHelpers:

    def test_make_duration_entity(self):
        dur = _make_duration_entity("P28D", "28 days", "tl1")
        assert dur["instanceType"] == "Duration"
        assert dur["text"] == "28 days"
        assert dur["quantity"]["maxValue"] == 28.0
        # EVS-verified C-code for Day
        assert dur["quantity"]["unit"]["code"] == "C25301"
        assert dur["quantity"]["unit"]["decode"] == "Day"

    def test_make_duration_entity_week(self):
        dur = _make_duration_entity("P12W", "12 weeks", "tl2")
        assert dur["quantity"]["unit"]["code"] == "C29844"
        assert dur["quantity"]["unit"]["decode"] == "Week"

    def test_make_duration_entity_year(self):
        dur = _make_duration_entity("P2Y", "2 years", "tl3")
        assert dur["quantity"]["unit"]["code"] == "C29848"
        assert dur["quantity"]["unit"]["decode"] == "Year"

    def test_iso_unit_decode(self):
        assert _iso_unit_decode("P28D") == "Day"
        assert _iso_unit_decode("P12W") == "Week"
        assert _iso_unit_decode("P6M") == "Month"
        assert _iso_unit_decode("P1Y") == "Year"
        assert _iso_unit_decode("PT2H") == "Hour"


# ─────────────────────────────────────────────────────────────
# VAL-1 + VAL-4: Referential Integrity & Cross-Phase Coherence
# ─────────────────────────────────────────────────────────────

from pipeline.integrity import (
    check_semantic_rules,
    check_integrity,
    Severity,
)


def _make_usdm(
    arms=None, epochs=None, cells=None, estimands=None,
    objectives=None, encounters=None, interventions=None,
    activities=None, timelines=None, analysis_pops=None,
    extensions=None,
):
    """Build minimal USDM dict for integrity tests."""
    sd = {
        "arms": arms or [],
        "epochs": epochs or [],
        "studyCells": cells or [],
        "estimands": estimands or [],
        "objectives": objectives or [],
        "encounters": encounters or [],
        "activities": activities or [],
        "scheduleTimelines": timelines or [],
        "analysisPopulations": analysis_pops or [],
        "extensionAttributes": extensions or [],
    }
    return {
        "study": {
            "versions": [{
                "studyDesigns": [sd],
                "studyInterventions": interventions or [],
            }],
        },
    }


class TestVAL4CrossPhaseCoherence:

    def test_s9_encounter_epoch_mismatch(self):
        enc = {"id": "enc1", "name": "Visit 1", "epochId": "nonexistent"}
        epoch = {"id": "ep1", "name": "Treatment"}
        usdm = _make_usdm(epochs=[epoch], encounters=[enc])
        findings = check_semantic_rules(usdm)
        s9 = [f for f in findings if f.rule == "encounter_epoch_mismatch"]
        assert len(s9) == 1
        assert s9[0].severity == Severity.ERROR

    def test_s9_valid_encounter_epoch(self):
        enc = {"id": "enc1", "name": "Visit 1", "epochId": "ep1"}
        epoch = {"id": "ep1", "name": "Treatment"}
        usdm = _make_usdm(epochs=[epoch], encounters=[enc])
        findings = check_semantic_rules(usdm)
        s9 = [f for f in findings if f.rule == "encounter_epoch_mismatch"]
        assert len(s9) == 0

    def test_s10_estimand_intervention_mismatch(self):
        si = {"id": "si1", "name": "Drug A"}
        est = {"id": "est1", "name": "Primary", "interventionIds": ["nonexistent"]}
        usdm = _make_usdm(estimands=[est], interventions=[si])
        findings = check_semantic_rules(usdm)
        s10 = [f for f in findings if f.rule == "estimand_intervention_mismatch"]
        assert len(s10) == 1

    def test_s10_valid_intervention_ref(self):
        si = {"id": "si1", "name": "Drug A"}
        est = {"id": "est1", "name": "Primary", "interventionIds": ["si1"]}
        usdm = _make_usdm(estimands=[est], interventions=[si])
        findings = check_semantic_rules(usdm)
        s10 = [f for f in findings if f.rule == "estimand_intervention_mismatch"]
        assert len(s10) == 0

    def test_s11_empty_required_array(self):
        obj = {"id": "obj1", "name": "Primary Objective", "endpoints": []}
        usdm = _make_usdm(objectives=[obj])
        findings = check_semantic_rules(usdm)
        s11 = [f for f in findings if f.rule == "empty_required_array"]
        assert any("endpoints" in f.details.get("field", "") for f in s11)

    def test_s11_non_empty_passes(self):
        ep = {"id": "ep1", "name": "OS"}
        obj = {"id": "obj1", "name": "Primary", "endpoints": [ep]}
        usdm = _make_usdm(objectives=[obj])
        findings = check_semantic_rules(usdm)
        s11_ep = [f for f in findings if f.rule == "empty_required_array" and f.details.get("field") == "endpoints"]
        assert len(s11_ep) == 0

    def test_s12_instance_encounter_mismatch(self):
        enc = {"id": "enc1", "name": "Visit 1"}
        inst = {"id": "inst1", "encounterId": "nonexistent", "activityIds": []}
        tl = {"id": "tl1", "instances": [inst]}
        usdm = _make_usdm(encounters=[enc], timelines=[tl])
        findings = check_semantic_rules(usdm)
        s12 = [f for f in findings if f.rule == "instance_encounter_mismatch"]
        assert len(s12) == 1

    def test_s12_instance_activity_mismatch(self):
        act = {"id": "act1", "name": "Vital Signs"}
        inst = {"id": "inst1", "activityIds": ["nonexistent"]}
        tl = {"id": "tl1", "instances": [inst]}
        usdm = _make_usdm(activities=[act], timelines=[tl])
        findings = check_semantic_rules(usdm)
        s12 = [f for f in findings if f.rule == "instance_activity_mismatch"]
        assert len(s12) == 1

    def test_s13_sap_endpoint_mismatch(self):
        ep = {"id": "ep1", "name": "Overall Survival"}
        obj = {"id": "obj1", "endpoints": [ep]}
        methods = [{"name": "ANCOVA", "endpointName": "Completely Different Endpoint"}]
        ext = {
            "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
            "valueObject": methods,
        }
        usdm = _make_usdm(objectives=[obj], extensions=[ext])
        findings = check_semantic_rules(usdm)
        s13 = [f for f in findings if f.rule == "sap_endpoint_mismatch"]
        assert len(s13) == 1

    def test_s13_sap_endpoint_matches(self):
        ep = {"id": "ep1", "name": "Overall Survival"}
        obj = {"id": "obj1", "endpoints": [ep]}
        methods = [{"name": "ANCOVA", "endpointName": "Overall Survival"}]
        ext = {
            "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
            "valueObject": methods,
        }
        usdm = _make_usdm(objectives=[obj], extensions=[ext])
        findings = check_semantic_rules(usdm)
        s13 = [f for f in findings if f.rule == "sap_endpoint_mismatch"]
        assert len(s13) == 0

    def test_s14_unnamed_population(self):
        pop = {"id": "pop1"}
        usdm = _make_usdm(analysis_pops=[pop])
        findings = check_semantic_rules(usdm)
        s14 = [f for f in findings if f.rule == "unnamed_population"]
        assert len(s14) == 1

    def test_full_integrity_check_runs(self):
        """Verify check_integrity runs without error on a minimal USDM."""
        usdm = _make_usdm(
            arms=[{"id": "arm1", "name": "Drug A"}],
            epochs=[{"id": "ep1", "name": "Treatment"}],
            cells=[{"id": "cell1", "armId": "arm1", "epochId": "ep1", "elementIds": []}],
        )
        report = check_integrity(usdm)
        assert report is not None
        assert isinstance(report.error_count, int)


# ─────────────────────────────────────────────────────────────
# M11-1: §4.3 Blinding Procedures Rendering
# ─────────────────────────────────────────────────────────────

from rendering.composers import _compose_blinding_procedures, _find_narrative_about


class TestM11BlindingProcedures:

    def _make_usdm_blinding(self, blind_schema, masking_roles=None, masking_entity=None):
        sd = {"blindingSchema": blind_schema}
        if masking_roles is not None:
            sd["maskingRoles"] = masking_roles
        if masking_entity is not None:
            sd["masking"] = masking_entity
        return {"study": {"versions": [{"studyDesigns": [sd]}]}}

    def test_double_blind_renders(self):
        usdm = self._make_usdm_blinding({"decode": "Double Blind"})
        result = _compose_blinding_procedures(usdm)
        assert "double blind" in result.lower()
        assert "4.3 Blinding" in result

    def test_open_label_short_circuit(self):
        usdm = self._make_usdm_blinding({"decode": "Open Label"})
        result = _compose_blinding_procedures(usdm)
        assert "open label" in result.lower()
        assert "No blinding" in result

    def test_masked_roles_rendered(self):
        roles = [
            {"role": "Subject", "isMasked": True},
            {"role": "Investigator", "isMasked": True},
            {"role": "Pharmacist", "isMasked": False},
        ]
        usdm = self._make_usdm_blinding({"decode": "Double Blind"}, masking_roles=roles)
        result = _compose_blinding_procedures(usdm)
        assert "Subject" in result
        assert "Investigator" in result
        assert "Pharmacist" in result
        assert "not be blinded" in result

    def test_masking_entity_roles(self):
        masking = {"role": [{"decode": "Outcome Assessor"}]}
        usdm = self._make_usdm_blinding({"decode": "Single Blind"}, masking_entity=masking)
        result = _compose_blinding_procedures(usdm)
        assert "Outcome Assessor" in result

    def test_no_fabricated_content_without_narrative(self):
        usdm = self._make_usdm_blinding({"decode": "Double Blind"})
        result = _compose_blinding_procedures(usdm)
        # Without narrative source data, no emergency unblinding section is rendered
        assert "Emergency Unblinding" not in result
        # No fabricated blinding measures boilerplate
        assert "matching study drug" not in result

    def test_no_blinding_schema_returns_empty(self):
        usdm = self._make_usdm_blinding({})
        result = _compose_blinding_procedures(usdm)
        assert result == ''

    def test_string_blinding_schema(self):
        usdm = self._make_usdm_blinding("Triple Blind")
        result = _compose_blinding_procedures(usdm)
        assert "triple blind" in result.lower()


class TestFindNarrativeAbout:

    def test_finds_matching_content(self):
        version = {
            "documentedBy": {
                "versions": [{
                    "contents": [{
                        "contentItems": [{
                            "text": "In case of emergency unblinding, the investigator should contact the sponsor immediately via the 24-hour emergency hotline."
                        }]
                    }]
                }]
            }
        }
        result = _find_narrative_about(version, "unblind")
        assert "emergency" in result.lower()

    def test_returns_empty_when_no_match(self):
        version = {"documentedBy": {"versions": [{"contents": []}]}}
        assert _find_narrative_about(version, "unblind") == ""


# ─────────────────────────────────────────────────────────────
# SOA-2: ConditionAssignment from Footnotes
# ─────────────────────────────────────────────────────────────

from pipeline.post_processing import promote_footnotes_to_conditions, _store_condition_assignments


def _make_combined_with_footnotes(footnotes, activities, encounters, timelines=None):
    """Build minimal combined dict for SOA-2 tests."""
    import json
    sd = {
        "activities": activities,
        "encounters": encounters,
        "scheduleTimelines": timelines or [],
        "extensionAttributes": [{
            "url": "https://protocol2usdm.io/extensions/soaFootnotes",
            "valueString": json.dumps(footnotes),
        }],
    }
    return {
        "study": {
            "versions": [{
                "studyDesigns": [sd],
                "conditions": [],
            }],
        },
    }


class TestSOA2ConditionAssignment:

    def test_creates_condition_from_footnote(self):
        fn = [{"id": "fn1", "text": "Only at screening visit"}]
        acts = [{"id": "act1", "name": "ECG"}]
        encs = [{"id": "enc1", "name": "screening visit"}]
        combined = _make_combined_with_footnotes(fn, acts, encs)
        promote_footnotes_to_conditions(combined)

        sv = combined["study"]["versions"][0]
        conditions = sv.get("conditions", [])
        assert len(conditions) >= 1
        assert any("screening" in c.get("text", "").lower() for c in conditions)

    def test_creates_condition_assignments(self):
        fn = [{"id": "fn1", "text": "Vital signs only at screening visit and day 1"}]
        acts = [{"id": "act1", "name": "vital signs"}]
        encs = [
            {"id": "enc1", "name": "screening visit"},
            {"id": "enc2", "name": "day 1"},
        ]
        tl = [{
            "id": "tl1",
            "instances": [
                {"id": "sai1", "instanceType": "ScheduledActivityInstance",
                 "activityIds": ["act1"], "encounterId": "enc1"},
                {"id": "sai2", "instanceType": "ScheduledActivityInstance",
                 "activityIds": ["act1"], "encounterId": "enc2"},
            ],
        }]
        combined = _make_combined_with_footnotes(fn, acts, encs, tl)
        promote_footnotes_to_conditions(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        # Check extension was created
        fn_ext = next(
            (e for e in sd.get("extensionAttributes", [])
             if "footnoteConditionAssignments" in e.get("url", "")),
            None,
        )
        assert fn_ext is not None
        cas = fn_ext["valueObject"]
        assert len(cas) >= 1
        assert all(ca["instanceType"] == "ConditionAssignment" for ca in cas)

    def test_sdi_nodes_inserted(self):
        fn = [{"id": "fn1", "text": "Physical exam only at screening visit"}]
        acts = [{"id": "act1", "name": "physical exam"}]
        encs = [{"id": "enc1", "name": "screening visit"}]
        tl = [{
            "id": "tl1",
            "instances": [
                {"id": "sai1", "instanceType": "ScheduledActivityInstance",
                 "activityIds": ["act1"], "encounterId": "enc1", "epochId": "ep1"},
            ],
        }]
        combined = _make_combined_with_footnotes(fn, acts, encs, tl)
        promote_footnotes_to_conditions(combined)

        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        instances = sd["scheduleTimelines"][0]["instances"]
        sdis = [i for i in instances if i.get("instanceType") == "ScheduledDecisionInstance"]
        assert len(sdis) >= 1
        assert sdis[0].get("conditionAssignments")

    def test_no_footnotes_noop(self):
        combined = {
            "study": {"versions": [{"studyDesigns": [{"extensionAttributes": []}]}]},
        }
        result = promote_footnotes_to_conditions(combined)
        assert result is not None

    def test_non_conditional_footnote_skipped(self):
        fn = [{"id": "fn1", "text": "See protocol section 8.2 for details"}]
        acts = [{"id": "act1", "name": "Labs"}]
        encs = []
        combined = _make_combined_with_footnotes(fn, acts, encs)
        promote_footnotes_to_conditions(combined)

        sv = combined["study"]["versions"][0]
        conditions = sv.get("conditions", [])
        assert len(conditions) == 0


class TestStoreConditionAssignments:

    def test_stores_extension(self):
        sd = {"extensionAttributes": [], "scheduleTimelines": []}
        assignments = [{
            "id": "ca1",
            "conditionId": "cond1",
            "conditionTargetId": "act1",
            "conditionText": "Only at screening",
            "instanceType": "ConditionAssignment",
        }]
        _store_condition_assignments(sd, assignments)

        ext = next(
            (e for e in sd["extensionAttributes"]
             if "footnoteConditionAssignments" in e.get("url", "")),
            None,
        )
        assert ext is not None
        assert len(ext["valueObject"]) == 1

    def test_replaces_old_extension(self):
        sd = {
            "extensionAttributes": [{
                "url": "https://protocol2usdm.io/extensions/x-footnoteConditionAssignments",
                "valueObject": [{"old": True}],
            }],
            "scheduleTimelines": [],
        }
        assignments = [{"id": "ca1", "conditionId": "c1", "conditionTargetId": "a1",
                        "conditionText": "test", "instanceType": "ConditionAssignment"}]
        _store_condition_assignments(sd, assignments)

        matching = [e for e in sd["extensionAttributes"]
                    if "footnoteConditionAssignments" in e.get("url", "")]
        assert len(matching) == 1
        assert matching[0]["valueObject"][0]["id"] == "ca1"


# ─────────────────────────────────────────────────────────────
# SAP-1: Method→Estimand Binding
# ─────────────────────────────────────────────────────────────

from pipeline.integrations import reconcile_method_estimand_refs


def _make_sd_with_methods(estimands, objectives, methods):
    """Build minimal study_design dict for SAP-1 tests."""
    return {
        "estimands": estimands,
        "objectives": objectives,
        "extensionAttributes": [{
            "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
            "valueObject": methods,
        }],
    }


class TestSAP1MethodEstimandBinding:

    def test_exact_endpoint_name_match(self):
        ep = {"id": "ep1", "name": "Overall Survival"}
        obj = {"id": "obj1", "endpoints": [ep]}
        est = {"id": "est1", "name": "Primary", "variableOfInterestId": "ep1"}
        method = {"id": "m1", "name": "ANCOVA", "endpointName": "Overall Survival"}
        sd = _make_sd_with_methods([est], [obj], [method])
        reconcile_method_estimand_refs(sd)
        assert method.get("estimandIds") == ["est1"]

    def test_substring_endpoint_match(self):
        ep = {"id": "ep1", "name": "Change from baseline in Overall Survival"}
        obj = {"id": "obj1", "endpoints": [ep]}
        est = {"id": "est1", "name": "Primary", "variableOfInterestId": "ep1"}
        method = {"id": "m1", "name": "MMRM", "endpointName": "overall survival"}
        sd = _make_sd_with_methods([est], [obj], [method])
        reconcile_method_estimand_refs(sd)
        assert method.get("estimandIds") == ["est1"]

    def test_level_based_match(self):
        ep = {"id": "ep1", "name": "PFS"}
        obj = {"id": "obj1", "endpoints": [ep]}
        est = {"id": "est1", "name": "Primary Estimand",
               "variableOfInterestId": "ep1",
               "level": {"decode": "Primary"}}
        method = {"id": "m1", "name": "Log-rank", "level": "Primary endpoint analysis"}
        sd = _make_sd_with_methods([est], [obj], [method])
        reconcile_method_estimand_refs(sd)
        assert method.get("estimandIds") == ["est1"]

    def test_no_estimands_noop(self):
        method = {"id": "m1", "name": "ANCOVA", "endpointName": "OS"}
        sd = _make_sd_with_methods([], [], [method])
        reconcile_method_estimand_refs(sd)
        assert "estimandIds" not in method

    def test_no_methods_noop(self):
        est = {"id": "est1", "name": "Primary"}
        sd = {"estimands": [est], "extensionAttributes": []}
        reconcile_method_estimand_refs(sd)
        # No error, no change

    def test_multiple_methods_to_different_estimands(self):
        ep1 = {"id": "ep1", "name": "Overall Survival"}
        ep2 = {"id": "ep2", "name": "Progression Free Survival"}
        obj = {"id": "obj1", "endpoints": [ep1, ep2]}
        est1 = {"id": "est1", "name": "Primary", "variableOfInterestId": "ep1"}
        est2 = {"id": "est2", "name": "Secondary", "variableOfInterestId": "ep2"}
        m1 = {"id": "m1", "name": "ANCOVA", "endpointName": "Overall Survival"}
        m2 = {"id": "m2", "name": "Log-rank", "endpointName": "Progression Free Survival"}
        sd = _make_sd_with_methods([est1, est2], [obj], [m1, m2])
        reconcile_method_estimand_refs(sd)
        assert m1.get("estimandIds") == ["est1"]
        assert m2.get("estimandIds") == ["est2"]

    def test_method_ids_stored_on_estimand(self):
        ep = {"id": "ep1", "name": "HbA1c"}
        obj = {"id": "obj1", "endpoints": [ep]}
        est = {"id": "est1", "name": "Primary", "variableOfInterestId": "ep1"}
        method = {"id": "m1", "name": "ANCOVA", "endpointName": "HbA1c"}
        sd = _make_sd_with_methods([est], [obj], [method])
        reconcile_method_estimand_refs(sd)
        assert "m1" in est.get("_methodIds", [])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
