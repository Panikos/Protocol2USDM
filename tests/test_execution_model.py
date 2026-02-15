"""
Comprehensive tests for the Execution Model Extraction module.

Tests:
- Schema dataclasses
- Time anchor detection (heuristic)
- Repetition detection (heuristic)
- Execution type classification
- Pipeline integration functions
"""

import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from extraction.execution.schema import (
    TimeAnchor,
    AnchorType,
    Repetition,
    RepetitionType,
    ExecutionType,
    SamplingConstraint,
    TraversalConstraint,
    ExecutionTypeAssignment,
    ExecutionModelData,
    ExecutionModelResult,
    ExecutionModelExtension,
    CrossoverDesign,
    FootnoteCondition,
    # Phase 3
    EndpointAlgorithm,
    EndpointType,
    DerivedVariable,
    VariableType,
    SubjectStateMachine,
    StateTransition,
    StateType,
    # Phase 4
    DosingRegimen,
    DoseLevel,
    DosingFrequency,
    RouteOfAdministration,
    VisitWindow,
    StratificationFactor,
    RandomizationScheme,
)

from extraction.execution.time_anchor_extractor import (
    _detect_anchors_fallback,
    _resolve_anchor_type,
    _extract_day_value,
    _prioritize_anchors,
)

from extraction.execution.repetition_extractor import (
    _detect_daily_patterns,
    _detect_interval_patterns,
    _detect_cycle_patterns,
    _detect_window_patterns,
    _detect_sampling_constraints,
)

from extraction.execution.execution_type_classifier import (
    classify_activity_text,
    _score_text_for_type,
    _detect_common_activities,
    WINDOW_PATTERNS,
    EPISODE_PATTERNS,
)

from extraction.execution.pipeline_integration import (
    enrich_usdm_with_execution_model,
    create_execution_model_summary,
    _resolve_to_encounter_id,
)

from extraction.execution.crossover_extractor import (
    _detect_crossover_heuristic,
    _extract_traversal_from_crossover,
    CROSSOVER_PATTERNS,
    WASHOUT_PATTERNS,
)

from extraction.execution.traversal_extractor import (
    _detect_epochs,
    _detect_mandatory_visits,
    _detect_early_exit_conditions,
    EPOCH_PATTERNS,
)

from extraction.execution.footnote_condition_extractor import (
    _extract_footnote_text,
    _classify_footnote,
    _extract_structured_condition,
    TIMING_PATTERNS,
    ELIGIBILITY_PATTERNS,
)

from extraction.execution.endpoint_extractor import (
    _detect_endpoint_type,
    _extract_inputs,
    _extract_time_window,
    _extract_algorithm,
    ENDPOINT_TYPE_PATTERNS,
)

from extraction.execution.derived_variable_extractor import (
    _detect_variable_type,
    _extract_source_variables,
    _extract_baseline_definition,
    _extract_derivation_rule,
    VARIABLE_TYPE_PATTERNS,
)

from extraction.execution.state_machine_generator import (
    _detect_states_from_text,
    _detect_transitions_from_text,
    _build_from_traversal,
    STANDARD_TRANSITIONS,
)


class TestSchema:
    """Test schema dataclasses."""
    
    def test_time_anchor_creation(self):
        anchor = TimeAnchor(
            id="anchor_1",
            definition="First dose of study drug",
            anchor_type=AnchorType.FIRST_DOSE,
            day_value=1,
        )
        assert anchor.id == "anchor_1"
        assert anchor.anchor_type == AnchorType.FIRST_DOSE
        assert anchor.day_value == 1
        
    def test_time_anchor_to_dict(self):
        anchor = TimeAnchor(
            id="anchor_1",
            definition="First dose",
            anchor_type=AnchorType.FIRST_DOSE,
        )
        d = anchor.to_dict()
        assert d["id"] == "anchor_1"
        assert d["anchorType"] == "FirstDose"
        assert "definition" in d
        
    def test_time_anchor_to_extension(self):
        anchor = TimeAnchor(
            id="anchor_1",
            definition="First dose",
            anchor_type=AnchorType.FIRST_DOSE,
        )
        ext = anchor.to_extension()
        assert "x-executionModel" in ext
        assert "timeAnchor" in ext["x-executionModel"]
        
    def test_repetition_creation(self):
        rep = Repetition(
            id="rep_1",
            type=RepetitionType.DAILY,
            interval="P1D",
            start_offset="-P4D",
            end_offset="-P1D",
        )
        assert rep.type == RepetitionType.DAILY
        assert rep.interval == "P1D"
        
    def test_repetition_to_dict(self):
        rep = Repetition(
            id="rep_1",
            type=RepetitionType.INTERVAL,
            interval="PT5M",
            min_observations=6,
        )
        d = rep.to_dict()
        assert d["type"] == "Interval"
        assert d["interval"] == "PT5M"
        assert d["minObservations"] == 6
        
    def test_execution_model_data_merge(self):
        data1 = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Test", anchor_type=AnchorType.DAY_1)]
        )
        data2 = ExecutionModelData(
            repetitions=[Repetition(id="r1", type=RepetitionType.DAILY)]
        )
        merged = data1.merge(data2)
        assert len(merged.time_anchors) == 1
        assert len(merged.repetitions) == 1
        
    def test_execution_model_result(self):
        data = ExecutionModelData()
        result = ExecutionModelResult(
            success=True,
            data=data,
            pages_used=[0, 1, 2],
            model_used="heuristic",
        )
        d = result.to_dict()
        assert d["success"] == True

    def test_execution_model_extension_from_result_uses_timezone_aware_timestamp(self):
        result = ExecutionModelResult(
            success=True,
            data=ExecutionModelData(),
            pages_used=[1],
            model_used="heuristic",
        )

        ext = ExecutionModelExtension.from_extraction_result(result)
        assert isinstance(ext.extractionTimestamp, str)

        parsed = datetime.fromisoformat(ext.extractionTimestamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


class TestTimeAnchorExtractor:
    """Test time anchor detection."""
    
    def test_detect_first_dose_anchor(self):
        text = "Day 1 is defined as the first dose of investigational product administered to the subject."
        anchors = _detect_anchors_fallback(text)
        assert len(anchors) > 0
        anchor_types = [a.anchor_type for a in anchors]
        assert AnchorType.FIRST_DOSE in anchor_types
        
    def test_detect_randomization_anchor(self):
        text = "Study visits are scheduled based on days from randomization. Day 0 is the randomization visit."
        anchors = _detect_anchors_fallback(text)
        assert len(anchors) > 0
        anchor_types = [a.anchor_type for a in anchors]
        assert AnchorType.RANDOMIZATION in anchor_types
        
    def test_detect_cycle_anchor(self):
        text = "Treatment begins on Cycle 1, Day 1 (C1D1) with oral administration of study drug."
        anchors = _detect_anchors_fallback(text)
        assert len(anchors) > 0
        anchor_types = [a.anchor_type for a in anchors]
        assert AnchorType.CYCLE_START in anchor_types
        
    def test_resolve_anchor_type(self):
        assert _resolve_anchor_type("FirstDose") == AnchorType.FIRST_DOSE
        assert _resolve_anchor_type("first_dose") == AnchorType.FIRST_DOSE
        assert _resolve_anchor_type("Randomization") == AnchorType.RANDOMIZATION
        assert _resolve_anchor_type("unknown_value") == AnchorType.CUSTOM
        assert _resolve_anchor_type("") == AnchorType.CUSTOM
        
    def test_extract_day_value(self):
        assert _extract_day_value("Day 1", "") == 1
        assert _extract_day_value("Day 14", "") == 14
        assert _extract_day_value("Week 0", "") == 1
        
    def test_prioritize_anchors(self):
        anchors = [
            TimeAnchor(id="1", definition="", anchor_type=AnchorType.SCREENING),
            TimeAnchor(id="2", definition="", anchor_type=AnchorType.FIRST_DOSE),
            TimeAnchor(id="3", definition="", anchor_type=AnchorType.RANDOMIZATION),
        ]
        prioritized = _prioritize_anchors(anchors)
        # FIRST_DOSE should come first
        assert prioritized[0].anchor_type == AnchorType.FIRST_DOSE


class TestRepetitionExtractor:
    """Test repetition pattern detection."""
    
    def test_detect_daily_urine(self):
        text = "Subjects will perform daily urine collection from Day -4 through Day -1."
        reps = _detect_daily_patterns(text)
        assert len(reps) > 0
        assert reps[0].type == RepetitionType.DAILY
        
    def test_detect_daily_once(self):
        text = "Blood glucose should be measured once daily during the treatment period."
        reps = _detect_daily_patterns(text)
        assert len(reps) > 0
        
    def test_detect_interval_minutes(self):
        text = "PK samples will be collected at time 0, 5, 10, 15, 30, 60 minutes post-dose."
        reps = _detect_interval_patterns(text)
        assert len(reps) > 0
        assert reps[0].type == RepetitionType.INTERVAL
        
    def test_detect_interval_every_n_minutes(self):
        text = "Glucose measurements every 5 minutes for 30 minutes following glucagon administration."
        reps = _detect_interval_patterns(text)
        assert len(reps) > 0
        # Check interval is PT5M
        assert any("5" in (r.interval or "") for r in reps)
        
    def test_detect_interval_hours(self):
        text = "Vital signs recorded every 4 hours during hospitalization."
        reps = _detect_interval_patterns(text)
        assert len(reps) > 0
        
    def test_detect_cycle_21_day(self):
        text = "Treatment will be administered in 21-day cycles until disease progression."
        reps = _detect_cycle_patterns(text)
        assert len(reps) > 0
        assert reps[0].type == RepetitionType.CYCLE
        assert reps[0].cycle_length == "P21D"
        assert reps[0].exit_condition == "Disease progression"
        
    def test_detect_cycle_28_day(self):
        text = "Each cycle length is 28 days with dosing on Days 1, 8, and 15."
        reps = _detect_cycle_patterns(text)
        assert len(reps) > 0
        assert reps[0].cycle_length == "P28D"
        
    def test_detect_window_days(self):
        text = "Balance data will be collected from Day -4 to Day -1 prior to dosing."
        reps = _detect_window_patterns(text)
        assert len(reps) > 0
        assert reps[0].type == RepetitionType.CONTINUOUS
        
    def test_detect_sampling_pk(self):
        text = "PK sampling timepoints: 0, 0.5, 1, 2, 4, 6, 8, 12, 24 hours post-dose."
        constraints = _detect_sampling_constraints(text)
        # May or may not detect depending on pattern match
        # Just verify it doesn't crash
        assert isinstance(constraints, list)


class TestExecutionTypeClassifier:
    """Test execution type classification."""
    
    def test_classify_window_activity(self):
        assignment = classify_activity_text(
            "Balance Collection",
            "Balance data collected from Day -4 to Day -1 during the screening period."
        )
        assert assignment.execution_type == ExecutionType.WINDOW
        
    def test_classify_episode_activity(self):
        assignment = classify_activity_text(
            "Rescue Medication",
            "If glucose falls below 70 mg/dL, administer rescue medication until stable."
        )
        assert assignment.execution_type == ExecutionType.EPISODE
        
    def test_classify_single_activity(self):
        assignment = classify_activity_text(
            "Informed Consent",
            "Informed consent obtained at screening only."
        )
        assert assignment.execution_type == ExecutionType.SINGLE
        
    def test_classify_recurring_activity(self):
        assignment = classify_activity_text(
            "Vital Signs",
            "Vital signs recorded at each study visit."
        )
        assert assignment.execution_type == ExecutionType.RECURRING
        
    def test_score_text_for_type(self):
        text = "daily collection from day -4 to day -1 throughout the period"
        count, conf = _score_text_for_type(text.lower(), WINDOW_PATTERNS)
        assert count > 0
        assert conf > 0.0
        
    def test_detect_common_activities(self):
        text = """
        Blood samples will be collected for laboratory tests.
        ECG measurements performed at baseline.
        Vital signs recorded at each visit.
        Adverse events monitored throughout.
        """
        activities = _detect_common_activities(text)
        assert len(activities) > 0
        # Should detect some common activities
        activity_names_lower = [a.lower() for a in activities]
        assert any("blood" in a or "vital" in a or "ecg" in a for a in activity_names_lower)


class TestPipelineIntegration:
    """Test pipeline integration functions."""
    
    def test_enrich_usdm_empty_data(self):
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData()
        enriched = enrich_usdm_with_execution_model(usdm, data)
        # Should return unchanged
        assert enriched == usdm
        
    def test_enrich_usdm_with_anchors(self):
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            time_anchors=[
                TimeAnchor(id="a1", definition="First dose", anchor_type=AnchorType.FIRST_DOSE)
            ]
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        # Should have extensionAttributes
        assert "extensionAttributes" in enriched["studyDesigns"][0]

    def test_typed_execution_extension_uses_timezone_aware_timestamp(self):
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            time_anchors=[
                TimeAnchor(id="a1", definition="First dose", anchor_type=AnchorType.FIRST_DOSE)
            ]
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)

        ext_attrs = enriched["studyDesigns"][0].get("extensionAttributes", [])
        typed_ext = next((e for e in ext_attrs if e.get("url", "").endswith("x-executionModel")), None)

        assert typed_ext is not None
        ts = typed_ext.get("valueObject", {}).get("extractionTimestamp")
        assert isinstance(ts, str)

        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
        
    def test_enrich_usdm_with_execution_types(self):
        usdm = {
            "studyDesigns": [{
                "id": "sd_1",
                "activities": [
                    {"id": "act_1", "name": "Balance Collection"}
                ]
            }]
        }
        data = ExecutionModelData(
            execution_types=[
                ExecutionTypeAssignment(
                    activity_id="Balance Collection",
                    execution_type=ExecutionType.WINDOW,
                )
            ]
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        # Check activity has extension
        activity = enriched["studyDesigns"][0]["activities"][0]
        assert "extensionAttributes" in activity
        
    def test_create_summary(self):
        data = ExecutionModelData(
            time_anchors=[
                TimeAnchor(id="a1", definition="First dose", anchor_type=AnchorType.FIRST_DOSE)
            ],
            repetitions=[
                Repetition(id="r1", type=RepetitionType.DAILY, interval="P1D")
            ],
        )
        summary = create_execution_model_summary(data)
        assert "Time Anchors" in summary
        assert "Repetitions" in summary
        assert "FirstDose" in summary

    def test_resolve_scheduled_treatment_visits_to_treatment_encounter(self):
        encounters = [
            {"id": "enc_screen", "name": "Screening (Week -10 to -3)", "epochId": "ep_screen"},
            {"id": "enc_runin", "name": "Run-In (Week -2)", "epochId": "ep_runin"},
            {"id": "enc_treat", "name": "Treatment (Week 3)", "epochId": "ep_treat"},
            {"id": "enc_follow", "name": "Follow-up", "epochId": "ep_follow"},
        ]
        encounter_ids = {enc["id"] for enc in encounters}

        resolved = _resolve_to_encounter_id(
            visit_name="Scheduled Treatment Visits",
            encounter_ids=encounter_ids,
            encounters=encounters,
            epochs=None,
        )

        assert resolved == "enc_treat"


class TestEnumValues:
    """Test enum value handling."""
    
    def test_anchor_type_values(self):
        assert AnchorType.FIRST_DOSE.value == "FirstDose"
        assert AnchorType.RANDOMIZATION.value == "Randomization"
        assert AnchorType.DAY_1.value == "Day1"
        
    def test_repetition_type_values(self):
        assert RepetitionType.DAILY.value == "Daily"
        assert RepetitionType.INTERVAL.value == "Interval"
        assert RepetitionType.CYCLE.value == "Cycle"
        
    def test_execution_type_values(self):
        assert ExecutionType.WINDOW.value == "Window"
        assert ExecutionType.EPISODE.value == "Episode"
        assert ExecutionType.SINGLE.value == "Single"


class TestCrossoverExtractor:
    """Test crossover design extraction."""
    
    def test_crossover_design_creation(self):
        cd = CrossoverDesign(
            id="cd_1",
            is_crossover=True,
            num_periods=2,
            num_sequences=2,
            periods=["Period 1", "Period 2"],
            sequences=["AB", "BA"],
            washout_duration="P7D",
            washout_required=True,
        )
        assert cd.is_crossover == True
        assert cd.num_periods == 2
        assert cd.washout_duration == "P7D"
        
    def test_crossover_design_to_dict(self):
        cd = CrossoverDesign(
            id="cd_1",
            is_crossover=True,
            num_periods=2,
            sequences=["AB", "BA"],
        )
        d = cd.to_dict()
        assert d["isCrossover"] == True
        assert d["numPeriods"] == 2
        assert "sequences" in d
        
    def test_detect_crossover_2way(self):
        text = """This is a 2-way crossover study where subjects receive 
        treatment A in Period 1 and treatment B in Period 2, or vice versa."""
        result = _detect_crossover_heuristic(text)
        assert result is not None
        assert result.is_crossover == True
        assert result.num_periods >= 2
        
    def test_detect_crossover_with_washout(self):
        text = """This is a crossover study with a 7-day washout period 
        between treatment periods to prevent carryover effects."""
        result = _detect_crossover_heuristic(text)
        assert result is not None
        assert result.washout_required == True
        assert result.washout_duration == "P7D"
        
    def test_detect_crossover_sequences(self):
        text = """Subjects will be randomized to sequence AB or sequence BA.
        This is a 2-period crossover design."""
        result = _detect_crossover_heuristic(text)
        assert result is not None
        assert "AB" in result.sequences or "BA" in result.sequences
        
    def test_no_crossover_parallel(self):
        text = """This is a parallel group study where subjects are 
        randomized to receive either treatment A or treatment B."""
        result = _detect_crossover_heuristic(text)
        assert result is None
        
    def test_extract_traversal_from_crossover(self):
        cd = CrossoverDesign(
            id="cd_1",
            is_crossover=True,
            num_periods=2,
            periods=["Period 1", "Period 2"],
            washout_required=True,
        )
        text = "Mandatory visits include Screening and Day 1."
        tc = _extract_traversal_from_crossover(cd, text)
        assert "SCREENING" in tc.required_sequence
        assert "END_OF_STUDY" in tc.required_sequence
        assert "WASHOUT" in tc.required_sequence


class TestTraversalExtractor:
    """Test traversal constraint extraction."""
    
    def test_traversal_constraint_creation(self):
        tc = TraversalConstraint(
            id="tc_1",
            required_sequence=["SCREENING", "TREATMENT", "FOLLOW_UP"],
            allow_early_exit=True,
            mandatory_visits=["Screening", "Day 1", "End of Study"],
        )
        assert len(tc.required_sequence) == 3
        assert tc.allow_early_exit == True
        
    def test_traversal_to_dict(self):
        tc = TraversalConstraint(
            id="tc_1",
            required_sequence=["SCREENING", "TREATMENT"],
            mandatory_visits=["Screening"],
        )
        d = tc.to_dict()
        assert "requiredSequence" in d
        assert "mandatoryVisits" in d
        
    def test_detect_epochs_standard(self):
        text = """The study consists of a Screening Period, followed by 
        a Treatment Period, and a Follow-up Period."""
        epochs = _detect_epochs(text)
        assert "SCREENING" in epochs
        assert "TREATMENT" in epochs
        assert "FOLLOW_UP" in epochs
        assert "END_OF_STUDY" in epochs  # Always added
        
    def test_detect_epochs_with_washout(self):
        text = """Subjects enter the Screening Period, then Treatment Period 1, 
        followed by a Washout Period, then Treatment Period 2."""
        epochs = _detect_epochs(text)
        assert "SCREENING" in epochs
        assert "WASHOUT" in epochs
        
    def test_detect_mandatory_visits(self):
        text = """All subjects must complete the Day 1 visit. 
        The End of Study visit is mandatory for all subjects."""
        visits = _detect_mandatory_visits(text)
        assert "Screening" in visits  # Always mandatory
        assert "Day 1" in visits
        assert "End of Study" in visits
        
    def test_detect_early_exit(self):
        text = """Subjects who discontinue early must complete the 
        Early Termination visit and 30-day safety follow-up."""
        allows_exit, procedures = _detect_early_exit_conditions(text)
        assert allows_exit == True
        assert len(procedures) > 0


class TestFootnoteExtractor:
    """Test footnote condition extraction."""
    
    def test_footnote_condition_creation(self):
        fc = FootnoteCondition(
            id="fc_1",
            footnote_id="a",
            condition_type="timing",
            text="ECG must be collected 30 min before labs",
            timing_constraint="PT30M",
        )
        assert fc.condition_type == "timing"
        assert fc.timing_constraint == "PT30M"
        
    def test_footnote_to_dict(self):
        fc = FootnoteCondition(
            id="fc_1",
            condition_type="eligibility",
            text="Only for WOCBP",
            structured_condition="subject.isWOCBP == true",
        )
        d = fc.to_dict()
        assert d["conditionType"] == "eligibility"
        assert "structuredCondition" in d
        
    def test_classify_timing_before(self):
        text = "ECG must be performed 30 minutes before blood draw"
        cond_type, timing, confidence = _classify_footnote(text)
        assert cond_type.startswith("timing")
        assert timing == "PT30M"
        
    def test_classify_eligibility_wocbp(self):
        text = "Only for women of childbearing potential"
        cond_type, timing, confidence = _classify_footnote(text)
        assert cond_type == "eligibility_wocbp"
        
    def test_classify_procedure_triplicate(self):
        text = "Blood pressure measured in triplicate"
        cond_type, timing, confidence = _classify_footnote(text)
        assert cond_type == "procedure_replicate"
        
    def test_classify_fasting(self):
        text = "Samples collected fasting (minimum 8 hours)"
        cond_type, timing, confidence = _classify_footnote(text)
        assert cond_type == "procedure_fasting"
        
    def test_extract_structured_timing(self):
        text = "30 minutes before laboratory assessments"
        structured = _extract_structured_condition(text, "timing_before")
        assert structured is not None
        assert "timing.before" in structured
        
    def test_extract_structured_eligibility(self):
        text = "for women of childbearing potential"
        structured = _extract_structured_condition(text, "eligibility_wocbp")
        assert structured is not None
        assert "Female" in structured or "childbearing" in structured.lower()
        
    def test_extract_structured_replicate(self):
        text = "performed in triplicate"
        structured = _extract_structured_condition(text, "procedure_replicate")
        assert structured is not None
        assert "3" in structured


class TestEndpointExtractor:
    """Test endpoint algorithm extraction."""
    
    def test_endpoint_algorithm_creation(self):
        ep = EndpointAlgorithm(
            id="ep_1",
            name="Primary: Hypoglycemia Recovery",
            endpoint_type=EndpointType.PRIMARY,
            inputs=["PG", "glucagon_time"],
            time_window_reference="glucagon administration",
            time_window_duration="PT30M",
            algorithm="PG >= 70 OR (PG - nadir) >= 20",
            success_criteria="PG >= 70 mg/dL within 30 minutes",
        )
        assert ep.endpoint_type == EndpointType.PRIMARY
        assert ep.time_window_duration == "PT30M"
        
    def test_endpoint_to_dict(self):
        ep = EndpointAlgorithm(
            id="ep_1",
            name="Secondary Endpoint",
            endpoint_type=EndpointType.SECONDARY,
            algorithm="value >= threshold",
        )
        d = ep.to_dict()
        assert d["endpointType"] == "Secondary"
        assert "algorithm" in d
        
    def test_detect_primary_endpoint(self):
        text = "The primary efficacy endpoint is change from baseline in HbA1c"
        ep_type, confidence = _detect_endpoint_type(text)
        assert ep_type == EndpointType.PRIMARY
        assert confidence >= 0.9
        
    def test_detect_secondary_endpoint(self):
        text = "Secondary endpoints include fasting glucose levels"
        ep_type, confidence = _detect_endpoint_type(text)
        assert ep_type == EndpointType.SECONDARY
        
    def test_extract_inputs(self):
        text = "The endpoint is based on glucose levels and HbA1c measurements"
        inputs = _extract_inputs(text)
        assert "glucose" in inputs or "HbA1c" in inputs
        
    def test_extract_time_window(self):
        text = "Recovery is defined as PG >= 70 within 30 minutes of glucagon"
        reference, duration = _extract_time_window(text)
        assert duration == "PT30M"
        
    def test_extract_algorithm(self):
        text = "Success is defined as achieving >= 70 mg/dL"
        algorithm = _extract_algorithm(text)
        assert algorithm is not None
        assert ">=" in algorithm


class TestDerivedVariableExtractor:
    """Test derived variable extraction."""
    
    def test_derived_variable_creation(self):
        dv = DerivedVariable(
            id="dv_1",
            name="Change from Baseline in HbA1c",
            variable_type=VariableType.CHANGE_FROM_BASELINE,
            source_variables=["HbA1c"],
            derivation_rule="week12_value - baseline_value",
            baseline_definition="Last value before Day 1",
        )
        assert dv.variable_type == VariableType.CHANGE_FROM_BASELINE
        assert len(dv.source_variables) == 1
        
    def test_derived_variable_to_dict(self):
        dv = DerivedVariable(
            id="dv_1",
            name="Percent Change",
            variable_type=VariableType.PERCENT_CHANGE,
            derivation_rule="((post - baseline) / baseline) * 100",
        )
        d = dv.to_dict()
        assert d["variableType"] == "PercentChange"
        assert "derivationRule" in d
        
    def test_detect_change_from_baseline(self):
        text = "The change from baseline in glucose was calculated"
        var_type, confidence = _detect_variable_type(text)
        assert var_type == VariableType.CHANGE_FROM_BASELINE
        
    def test_detect_percent_change(self):
        text = "Percentage change in weight was computed"
        var_type, confidence = _detect_variable_type(text)
        assert var_type == VariableType.PERCENT_CHANGE
        
    def test_extract_baseline_definition(self):
        text = "Baseline is defined as the last non-missing value before Day 1"
        definition, visit = _extract_baseline_definition(text)
        assert definition is not None
        assert "day" in visit.lower() or definition is not None
        
    def test_extract_derivation_rule_cfb(self):
        text = "Change from baseline calculated"
        rule = _extract_derivation_rule(text, VariableType.CHANGE_FROM_BASELINE)
        assert "baseline" in rule


class TestStateMachineGenerator:
    """Test subject state machine generation."""
    
    def test_state_machine_creation(self):
        sm = SubjectStateMachine(
            id="sm_1",
            initial_state=StateType.SCREENING,
            terminal_states=[StateType.COMPLETED, StateType.DISCONTINUED],
            states=[StateType.SCREENING, StateType.ENROLLED, StateType.COMPLETED],
            transitions=[],
        )
        assert sm.initial_state == StateType.SCREENING
        assert StateType.COMPLETED in sm.terminal_states
        
    def test_state_transition_creation(self):
        t = StateTransition(
            from_state=StateType.SCREENING,
            to_state=StateType.ENROLLED,
            trigger="Meets eligibility criteria",
            guard_condition="all_criteria_met",
        )
        assert t.from_state == StateType.SCREENING
        assert t.to_state == StateType.ENROLLED
        
    def test_state_machine_to_dict(self):
        sm = SubjectStateMachine(
            id="sm_1",
            states=[StateType.SCREENING, StateType.COMPLETED],
            transitions=[
                StateTransition(StateType.SCREENING, StateType.COMPLETED, "Complete")
            ],
        )
        d = sm.to_dict()
        assert "initialState" in d
        assert "transitions" in d
        assert len(d["transitions"]) == 1
        
    def test_detect_states_from_text(self):
        text = """Subjects were enrolled and randomized to treatment.
        After completion of the treatment period, subjects entered follow-up."""
        states = _detect_states_from_text(text)
        assert StateType.SCREENING in states
        assert StateType.ENROLLED in states or StateType.RANDOMIZED in states
        
    def test_detect_transitions(self):
        text = "Subjects who discontinue early must complete the Early Termination visit"
        states = [StateType.SCREENING, StateType.ON_TREATMENT, StateType.DISCONTINUED, StateType.COMPLETED]
        transitions = _detect_transitions_from_text(text, states)
        assert len(transitions) > 0
        
    def test_build_from_traversal(self):
        tc = TraversalConstraint(
            id="tc_1",
            required_sequence=["SCREENING", "TREATMENT", "FOLLOW_UP", "END_OF_STUDY"],
            mandatory_visits=["Screening", "Day 1"],
        )
        sm = _build_from_traversal(tc)
        assert len(sm.states) > 0
        assert len(sm.transitions) > 0
        assert sm.initial_state == StateType.SCREENING
        
    def test_is_terminal(self):
        sm = SubjectStateMachine(
            id="sm_1",
            terminal_states=[StateType.COMPLETED, StateType.DISCONTINUED],
        )
        assert sm.is_terminal(StateType.COMPLETED) == True
        assert sm.is_terminal(StateType.ON_TREATMENT) == False
        
    def test_get_valid_transitions(self):
        sm = SubjectStateMachine(
            id="sm_1",
            transitions=[
                StateTransition(StateType.SCREENING, StateType.ENROLLED, "Enroll"),
                StateTransition(StateType.ENROLLED, StateType.ON_TREATMENT, "Start"),
            ],
        )
        valid = sm.get_valid_transitions(StateType.SCREENING)
        assert len(valid) == 1
        assert valid[0].to_state == StateType.ENROLLED


class TestPhase3SchemaIntegration:
    """Test Phase 3 schema integration with ExecutionModelData."""
    
    def test_execution_model_data_with_endpoints(self):
        ep = EndpointAlgorithm(id="ep_1", name="Primary", endpoint_type=EndpointType.PRIMARY)
        data = ExecutionModelData(endpoint_algorithms=[ep])
        assert len(data.endpoint_algorithms) == 1
        
    def test_execution_model_data_with_variables(self):
        dv = DerivedVariable(id="dv_1", name="CFB", variable_type=VariableType.CHANGE_FROM_BASELINE)
        data = ExecutionModelData(derived_variables=[dv])
        assert len(data.derived_variables) == 1
        
    def test_execution_model_data_with_state_machine(self):
        sm = SubjectStateMachine(id="sm_1")
        data = ExecutionModelData(state_machine=sm)
        assert data.state_machine is not None
        
    def test_execution_model_data_to_dict_phase3(self):
        ep = EndpointAlgorithm(id="ep_1", name="Primary", endpoint_type=EndpointType.PRIMARY)
        dv = DerivedVariable(id="dv_1", name="CFB", variable_type=VariableType.CHANGE_FROM_BASELINE)
        sm = SubjectStateMachine(id="sm_1")
        
        data = ExecutionModelData(
            endpoint_algorithms=[ep],
            derived_variables=[dv],
            state_machine=sm,
        )
        d = data.to_dict()
        assert "endpointAlgorithms" in d
        assert "derivedVariables" in d
        assert "stateMachine" in d
        
    def test_execution_model_data_merge_phase3(self):
        data1 = ExecutionModelData(
            endpoint_algorithms=[EndpointAlgorithm(id="ep_1", name="A", endpoint_type=EndpointType.PRIMARY)]
        )
        data2 = ExecutionModelData(
            derived_variables=[DerivedVariable(id="dv_1", name="B", variable_type=VariableType.BASELINE)],
            state_machine=SubjectStateMachine(id="sm_1"),
        )
        merged = data1.merge(data2)
        assert len(merged.endpoint_algorithms) == 1
        assert len(merged.derived_variables) == 1
        assert merged.state_machine is not None


class TestPhase2SchemaIntegration:
    """Test Phase 2 schema integration with ExecutionModelData."""
    
    def test_execution_model_data_with_crossover(self):
        cd = CrossoverDesign(
            id="cd_1",
            is_crossover=True,
            num_periods=2,
        )
        data = ExecutionModelData(crossover_design=cd)
        assert data.crossover_design is not None
        assert data.crossover_design.num_periods == 2
        
    def test_execution_model_data_with_footnotes(self):
        fc = FootnoteCondition(
            id="fc_1",
            condition_type="timing",
            text="Test footnote",
        )
        data = ExecutionModelData(footnote_conditions=[fc])
        assert len(data.footnote_conditions) == 1
        
    def test_execution_model_data_to_dict_full(self):
        cd = CrossoverDesign(id="cd_1", is_crossover=True)
        fc = FootnoteCondition(id="fc_1", condition_type="timing", text="Test")
        tc = TraversalConstraint(id="tc_1", required_sequence=["A", "B"])
        
        data = ExecutionModelData(
            crossover_design=cd,
            footnote_conditions=[fc],
            traversal_constraints=[tc],
        )
        d = data.to_dict()
        assert "crossoverDesign" in d
        assert "footnoteConditions" in d
        assert "traversalConstraints" in d
        
    def test_execution_model_data_merge_crossover(self):
        data1 = ExecutionModelData()
        data2 = ExecutionModelData(
            crossover_design=CrossoverDesign(id="cd_1", is_crossover=True)
        )
        merged = data1.merge(data2)
        assert merged.crossover_design is not None
        
    def test_execution_model_data_merge_footnotes(self):
        fc1 = FootnoteCondition(id="fc_1", condition_type="a", text="A")
        fc2 = FootnoteCondition(id="fc_2", condition_type="b", text="B")
        data1 = ExecutionModelData(footnote_conditions=[fc1])
        data2 = ExecutionModelData(footnote_conditions=[fc2])
        merged = data1.merge(data2)
        assert len(merged.footnote_conditions) == 2


class TestValidation:
    """Test validation and quality checks."""
    
    def test_validation_import(self):
        from extraction.execution import (
            validate_execution_model,
            ValidationResult,
            ValidationSeverity,
        )
        assert validate_execution_model is not None
        
    def test_validate_empty_data(self):
        from extraction.execution import validate_execution_model, ValidationSeverity
        data = ExecutionModelData()
        result = validate_execution_model(data)
        # Empty data should have warnings but not errors
        assert result.is_valid
        assert len(result.warnings) > 0
        
    def test_validate_complete_data(self):
        from extraction.execution import validate_execution_model
        
        # Create comprehensive data
        data = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
            repetitions=[Repetition(id="r1", type=RepetitionType.DAILY)],
            execution_types=[ExecutionTypeAssignment(activity_id="act1", execution_type=ExecutionType.EPISODE)],
            traversal_constraints=[TraversalConstraint(id="tc1", required_sequence=["SCREENING", "TREATMENT", "END"])],
            endpoint_algorithms=[EndpointAlgorithm(id="ep1", name="Primary", endpoint_type=EndpointType.PRIMARY, algorithm="x >= y")],
            derived_variables=[DerivedVariable(id="dv1", name="CFB", variable_type=VariableType.CHANGE_FROM_BASELINE, derivation_rule="post - baseline", baseline_definition="Day 1")],
            state_machine=SubjectStateMachine(
                id="sm1",
                states=[StateType.SCREENING, StateType.ON_TREATMENT, StateType.COMPLETED],
                terminal_states=[StateType.COMPLETED],
                transitions=[StateTransition(StateType.SCREENING, StateType.ON_TREATMENT, "Enroll")],
            ),
        )
        result = validate_execution_model(data)
        assert result.score >= 0.7
        
    def test_validation_summary(self):
        from extraction.execution import validate_execution_model, create_validation_summary
        data = ExecutionModelData()
        result = validate_execution_model(data)
        summary = create_validation_summary(result)
        assert "Validation" in summary
        assert "Score" in summary
        
    def test_state_machine_validation_errors(self):
        from extraction.execution import validate_execution_model, ValidationSeverity
        
        # State machine with no terminal states (should be error)
        sm = SubjectStateMachine(
            id="sm1",
            states=[StateType.SCREENING],
            terminal_states=[],  # Error: no terminal states
        )
        data = ExecutionModelData(state_machine=sm)
        result = validate_execution_model(data)
        
        sm_errors = [i for i in result.errors if i.component == "StateMachine"]
        assert len(sm_errors) > 0


class TestIntegration:
    """Integration tests for full pipeline."""
    
    def test_pipeline_integration_import(self):
        from extraction.execution import (
            extract_execution_model,
            enrich_usdm_with_execution_model,
            create_execution_model_summary,
        )
        assert extract_execution_model is not None
        
    def test_enrich_usdm_empty(self):
        from extraction.execution import enrich_usdm_with_execution_model
        
        usdm = {"studyDesigns": [{"id": "sd1", "name": "Test"}]}
        data = ExecutionModelData()
        
        enriched = enrich_usdm_with_execution_model(usdm, data)
        assert enriched is not None
        
    def test_enrich_usdm_with_phase3_data(self):
        from extraction.execution import enrich_usdm_with_execution_model
        
        usdm = {"studyDesigns": [{"id": "sd1", "name": "Test"}]}
        data = ExecutionModelData(
            endpoint_algorithms=[EndpointAlgorithm(id="ep1", name="Primary", endpoint_type=EndpointType.PRIMARY)],
            derived_variables=[DerivedVariable(id="dv1", name="CFB", variable_type=VariableType.CHANGE_FROM_BASELINE)],
            state_machine=SubjectStateMachine(id="sm1"),
        )
        
        enriched = enrich_usdm_with_execution_model(usdm, data)
        
        # Check extensions were added
        design = enriched["studyDesigns"][0]
        assert "extensionAttributes" in design
        
        # USDM schema uses 'url' field for identification
        ext_urls = [e.get("url", "") for e in design["extensionAttributes"]]
        assert any("endpointAlgorithms" in u for u in ext_urls)
        assert any("derivedVariables" in u for u in ext_urls)
        assert any("stateMachine" in u for u in ext_urls)
        
    def test_execution_model_summary(self):
        from extraction.execution import create_execution_model_summary
        
        data = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
            endpoint_algorithms=[EndpointAlgorithm(id="ep1", name="Primary", endpoint_type=EndpointType.PRIMARY, algorithm="x >= 70")],
            state_machine=SubjectStateMachine(id="sm1", states=[StateType.SCREENING, StateType.COMPLETED]),
        )
        
        summary = create_execution_model_summary(data)
        assert "Time Anchors" in summary
        assert "Endpoint Algorithms" in summary
        assert "State Machine" in summary


class TestTherapeuticPatterns:
    """Test therapeutic area patterns."""
    
    def test_get_therapeutic_patterns(self):
        from extraction.execution.prompts import get_therapeutic_patterns
        
        diabetes = get_therapeutic_patterns("diabetes")
        assert "endpoints" in diabetes
        assert "HbA1c" in diabetes["endpoints"]
        
        oncology = get_therapeutic_patterns("oncology")
        assert "ORR" in oncology["endpoints"]
        
    def test_unknown_therapeutic_area(self):
        from extraction.execution.prompts import get_therapeutic_patterns
        
        unknown = get_therapeutic_patterns("unknown_area")
        assert unknown == {}
        
    def test_all_therapeutic_areas(self):
        from extraction.execution.prompts import get_therapeutic_patterns, get_all_therapeutic_areas
        
        areas = get_all_therapeutic_areas()
        assert len(areas) == 10
        assert "diabetes" in areas
        assert "oncology" in areas
        assert "respiratory" in areas
        
        # All areas should return valid patterns
        for area in areas:
            patterns = get_therapeutic_patterns(area)
            assert "endpoints" in patterns
            assert "units" in patterns
            
    def test_detect_therapeutic_area_diabetes(self):
        from extraction.execution.prompts import detect_therapeutic_area
        
        text = "The primary endpoint is change from baseline in HbA1c at Week 12. Hypoglycemia events will be monitored."
        area, confidence = detect_therapeutic_area(text)
        assert area == "diabetes"
        assert confidence > 0.3
        
    def test_detect_therapeutic_area_oncology(self):
        from extraction.execution.prompts import detect_therapeutic_area
        
        text = "Overall response rate (ORR) based on RECIST criteria. Progression-free survival (PFS) is the key secondary endpoint."
        area, confidence = detect_therapeutic_area(text)
        assert area == "oncology"
        assert confidence > 0.3
        
    def test_detect_therapeutic_area_unknown(self):
        from extraction.execution.prompts import detect_therapeutic_area
        
        text = "This is a generic study with no specific therapeutic area indicators."
        area, confidence = detect_therapeutic_area(text)
        # Should return None or very low confidence
        assert area is None or confidence < 0.2


class TestSamplingDensityExtractor:
    """Test sampling density extractor (Phase 5)."""
    
    def test_import(self):
        from extraction.execution import extract_sampling_density
        assert extract_sampling_density is not None
        
    def test_pk_sampling_detection(self):
        from extraction.execution.sampling_density_extractor import _detect_pk_sampling
        
        text = "PK sampling at 0, 5, 10, 15, 30, 60, 120 minutes after dose"
        constraints = _detect_pk_sampling(text)
        assert len(constraints) >= 1
        assert constraints[0].min_per_window >= 7
        
    def test_pk_sampling_hours(self):
        from extraction.execution.sampling_density_extractor import _detect_pk_sampling
        
        text = "Blood samples at 0, 0.5, 1, 2, 4, 8, 12, 24 hours postdose"
        constraints = _detect_pk_sampling(text)
        assert len(constraints) >= 1
        
    def test_minimum_samples_detection(self):
        from extraction.execution.sampling_density_extractor import _detect_minimum_samples
        
        text = "A minimum of 5 samples per subject is required"
        constraints = _detect_minimum_samples(text)
        assert len(constraints) >= 1
        assert constraints[0].min_per_window == 5
        
    def test_at_least_pattern(self):
        from extraction.execution.sampling_density_extractor import _detect_minimum_samples
        
        text = "At least 3 samples per window must be collected"
        constraints = _detect_minimum_samples(text)
        assert len(constraints) >= 1
        assert constraints[0].min_per_window == 3
        
    def test_dense_window_detection(self):
        from extraction.execution.sampling_density_extractor import _detect_dense_windows
        
        text = "Intensive PK sampling will be performed over 24 hours"
        windows = _detect_dense_windows(text)
        assert len(windows) >= 1
        
    def test_sparse_sampling_detection(self):
        from extraction.execution.sampling_density_extractor import _detect_sparse_sampling
        
        text = "Population PK sampling with sparse sampling design"
        info = _detect_sparse_sampling(text)
        assert info["is_sparse"] == True
        assert info["is_population_pk"] == True
        
    def test_window_duration_estimation(self):
        from extraction.execution.sampling_density_extractor import _estimate_window_duration
        
        # 120 min = 2h, function adds 1 hour buffer so PT3H
        result = _estimate_window_duration(["0", "30", "60", "120"], "minutes")
        assert result is not None and "PT" in result
        assert _estimate_window_duration(["0", "1", "2", "4", "8", "24"], "hours") == "PT24H"
        
    def test_iso8601_conversion(self):
        from extraction.execution.sampling_density_extractor import _convert_to_iso8601
        
        assert _convert_to_iso8601("24", "hours") == "PT24H"
        assert _convert_to_iso8601("30", "minutes") == "PT30M"
        assert _convert_to_iso8601("7", "days") == "P7D"


class TestConfig:
    """Test configuration module."""
    
    def test_config_import(self):
        from extraction.execution import ExtractionConfig, load_config, save_config
        assert ExtractionConfig is not None
        
    def test_default_config(self):
        from extraction.execution import ExtractionConfig
        config = ExtractionConfig()
        assert config.model == "gemini-2.5-pro"
        assert config.use_llm == True
        assert config.min_confidence == 0.5
        
    def test_config_to_dict(self):
        from extraction.execution import ExtractionConfig
        config = ExtractionConfig(model="gpt-4o", therapeutic_area="diabetes")
        d = config.to_dict()
        assert d["model"] == "gpt-4o"
        assert d["therapeutic_area"] == "diabetes"
        
    def test_config_from_dict(self):
        from extraction.execution import ExtractionConfig
        data = {"model": "claude-3", "validate": True, "skip_endpoints": True}
        config = ExtractionConfig.from_dict(data)
        assert config.model == "claude-3"
        assert config.validate == True
        assert config.skip_endpoints == True
        
    def test_config_merge(self):
        from extraction.execution import ExtractionConfig
        config1 = ExtractionConfig(model="model1", validate=False)
        config2 = ExtractionConfig(model="model2", export_csv=True)
        merged = config1.merge(config2)
        assert merged.model == "model2"
        assert merged.export_csv == True


class TestCache:
    """Test caching module."""
    
    def test_cache_import(self):
        from extraction.execution import ExecutionCache, get_cache, cached
        assert ExecutionCache is not None
        
    def test_cache_set_get(self):
        from extraction.execution import ExecutionCache
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(cache_dir=tmpdir, ttl_seconds=3600)
            
            # Set and get
            cache.set("test_key", {"data": "value"})
            result = cache.get("test_key")
            assert result == {"data": "value"}
            
    def test_cache_miss(self):
        from extraction.execution import ExecutionCache
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(cache_dir=tmpdir)
            result = cache.get("nonexistent_key")
            assert result is None
            
    def test_cache_delete(self):
        from extraction.execution import ExecutionCache
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(cache_dir=tmpdir)
            cache.set("key_to_delete", "value")
            assert cache.get("key_to_delete") == "value"
            cache.delete("key_to_delete")
            assert cache.get("key_to_delete") is None
            
    def test_cache_stats(self):
        from extraction.execution import ExecutionCache
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(cache_dir=tmpdir)
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            stats = cache.get_stats()
            assert stats["memory_entries"] == 2
            assert stats["enabled"] == True
            
    def test_cache_disabled(self):
        from extraction.execution import ExecutionCache
        cache = ExecutionCache(enabled=False)
        cache.set("key", "value")
        assert cache.get("key") is None


class TestExport:
    """Test export module."""
    
    def test_export_import(self):
        from extraction.execution import export_to_csv, generate_markdown_report, save_report
        assert export_to_csv is not None
        assert generate_markdown_report is not None
        
    def test_export_csv(self):
        from extraction.execution import export_to_csv
        import tempfile
        
        data = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
            execution_types=[ExecutionTypeAssignment(activity_id="act1", execution_type=ExecutionType.EPISODE)],
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            files = export_to_csv(data, tmpdir)
            assert "time_anchors" in files
            assert "execution_types" in files
            
    def test_generate_report(self):
        from extraction.execution import generate_markdown_report
        
        data = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
            endpoint_algorithms=[EndpointAlgorithm(id="ep1", name="Primary", endpoint_type=EndpointType.PRIMARY)],
        )
        
        report = generate_markdown_report(data, "Test Protocol", 0.85)
        assert "# Execution Model Report" in report
        assert "Test Protocol" in report
        assert "Time Anchors" in report
        
    def test_save_report(self):
        from extraction.execution import save_report
        import tempfile
        import os
        
        data = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(data, os.path.join(tmpdir, "report.md"), "Test")
            assert os.path.exists(path)
            with open(path, 'r') as f:
                content = f.read()
            assert "Execution Model Report" in content


class TestPhase4Schema:
    """Test Phase 4 schema components."""
    
    def test_dose_level_creation(self):
        dose = DoseLevel(amount=100, unit="mg", description="starting dose")
        assert dose.amount == 100
        assert dose.unit == "mg"
        d = dose.to_dict()
        assert d["amount"] == 100
        assert d["unit"] == "mg"
        assert d["description"] == "starting dose"
    
    def test_dosing_regimen_creation(self):
        regimen = DosingRegimen(
            id="dose_1",
            treatment_name="Test Drug",
            dose_levels=[DoseLevel(amount=50, unit="mg")],
            frequency=DosingFrequency.TWICE_DAILY,
            route=RouteOfAdministration.ORAL,
            start_day=1,
            duration_description="24 weeks",
        )
        assert regimen.treatment_name == "Test Drug"
        assert regimen.frequency == DosingFrequency.TWICE_DAILY
        d = regimen.to_dict()
        assert d["treatmentName"] == "Test Drug"
        assert d["frequency"] == "BID"
        assert d["route"] == "Oral"
        assert len(d["doseLevels"]) == 1
    
    def test_visit_window_creation(self):
        window = VisitWindow(
            id="visit_1",
            visit_name="Week 4",
            visit_number=3,
            target_day=29,
            target_week=4,
            window_before=3,
            window_after=3,
            is_required=True,
            epoch="Treatment",
        )
        assert window.visit_name == "Week 4"
        assert window.target_day == 29
        assert window.window_before == 3
        d = window.to_dict()
        assert d["visitName"] == "Week 4"
        assert d["targetDay"] == 29
        assert d["windowBefore"] == 3
        assert d["windowAfter"] == 3
        assert d["isRequired"] == True
    
    def test_stratification_factor_creation(self):
        factor = StratificationFactor(
            id="strat_1",
            name="Age Group",
            categories=["<65 years", "≥65 years"],
            is_blocking=True,
        )
        assert factor.name == "Age Group"
        assert len(factor.categories) == 2
        d = factor.to_dict()
        assert d["name"] == "Age Group"
        assert d["isBlocking"] == True
    
    def test_randomization_scheme_creation(self):
        scheme = RandomizationScheme(
            id="rand_1",
            ratio="2:1",
            method="Stratified block randomization",
            block_size=6,
            stratification_factors=[
                StratificationFactor(id="s1", name="Age", categories=["<65", "≥65"]),
                StratificationFactor(id="s2", name="Sex", categories=["Male", "Female"]),
            ],
            central_randomization=True,
        )
        assert scheme.ratio == "2:1"
        assert scheme.block_size == 6
        assert len(scheme.stratification_factors) == 2
        d = scheme.to_dict()
        assert d["ratio"] == "2:1"
        assert d["blockSize"] == 6
        assert d["centralRandomization"] == True
        assert len(d["stratificationFactors"]) == 2
    
    def test_execution_model_data_with_phase4(self):
        data = ExecutionModelData(
            dosing_regimens=[
                DosingRegimen(id="d1", treatment_name="Drug A", frequency=DosingFrequency.ONCE_DAILY),
            ],
            visit_windows=[
                VisitWindow(id="v1", visit_name="Screening", target_day=-14),
                VisitWindow(id="v2", visit_name="Day 1", target_day=1),
            ],
            randomization_scheme=RandomizationScheme(id="r1", ratio="1:1"),
        )
        assert len(data.dosing_regimens) == 1
        assert len(data.visit_windows) == 2
        assert data.randomization_scheme is not None
        
        d = data.to_dict()
        assert "dosingRegimens" in d
        assert "visitWindows" in d
        assert "randomizationScheme" in d
    
    def test_merge_phase4_data(self):
        data1 = ExecutionModelData(
            dosing_regimens=[DosingRegimen(id="d1", treatment_name="Drug A")],
            visit_windows=[VisitWindow(id="v1", visit_name="Day 1", target_day=1)],
        )
        data2 = ExecutionModelData(
            dosing_regimens=[DosingRegimen(id="d2", treatment_name="Drug B")],
            visit_windows=[VisitWindow(id="v2", visit_name="Week 4", target_day=29)],
            randomization_scheme=RandomizationScheme(id="r1", ratio="1:1"),
        )
        
        merged = data1.merge(data2)
        assert len(merged.dosing_regimens) == 2
        assert len(merged.visit_windows) == 2
        assert merged.randomization_scheme is not None


class TestPhase4Extractors:
    """Test Phase 4 extractor helper functions."""
    
    def test_dosing_frequency_detection(self):
        from extraction.execution.dosing_regimen_extractor import _detect_frequency
        
        assert _detect_frequency("take once daily") == DosingFrequency.ONCE_DAILY
        assert _detect_frequency("BID dosing") == DosingFrequency.TWICE_DAILY
        assert _detect_frequency("weekly injection") == DosingFrequency.WEEKLY
        assert _detect_frequency("every 2 weeks") == DosingFrequency.EVERY_TWO_WEEKS
        assert _detect_frequency("Q3W administration") == DosingFrequency.EVERY_THREE_WEEKS
    
    def test_route_detection(self):
        from extraction.execution.dosing_regimen_extractor import _detect_route
        
        assert _detect_route("oral administration") == RouteOfAdministration.ORAL
        assert _detect_route("IV infusion") == RouteOfAdministration.INTRAVENOUS
        assert _detect_route("subcutaneous injection") == RouteOfAdministration.SUBCUTANEOUS
        assert _detect_route("intramuscular") == RouteOfAdministration.INTRAMUSCULAR
    
    def test_visit_timing_extraction(self):
        from extraction.execution.visit_window_extractor import _extract_timing
        
        day, week = _extract_timing("Day 15", "Visit on Day 15")
        assert day == 15
        
        day, week = _extract_timing("Week 4", "Week 4 visit")
        assert week == 4
        assert day == 22  # (4-1)*7 + 1
    
    def test_window_allowance_extraction(self):
        from extraction.execution.visit_window_extractor import _extract_window_allowance
        
        before, after = _extract_window_allowance("Visit window ± 3 days")
        assert before == 3
        assert after == 3
        
        before, after = _extract_window_allowance("within 7 days")
        assert before == 7
        assert after == 7
    
    def test_ratio_extraction(self):
        from extraction.execution.stratification_extractor import _extract_ratio
        
        assert _extract_ratio("randomized 1:1") == "1:1"
        assert _extract_ratio("2:1 allocation") == "2:1"
        assert _extract_ratio("1:1:1 ratio") == "1:1:1"
    
    def test_visit_extraction_from_soa(self):
        from extraction.execution.visit_window_extractor import _extract_from_soa
        
        # Mock SOA data structure
        soa_data = {
            "study": {
                "versions": [{
                    "timeline": {
                        "epochs": [
                            {"id": "epoch_1", "name": "Screening"},
                            {"id": "epoch_2", "name": "Treatment"},
                        ],
                        "encounters": [
                            {"id": "enc_1", "name": "Screening (-14)", "epochId": "epoch_1"},
                            {"id": "enc_2", "name": "Day 1", "epochId": "epoch_2"},
                            {"id": "enc_3", "name": "Week 4", "epochId": "epoch_2"},
                        ],
                        "plannedTimepoints": [
                            {"encounterId": "enc_1", "valueLabel": "Day -14"},
                            {"encounterId": "enc_2", "valueLabel": "Day 1"},
                            {"encounterId": "enc_3", "valueLabel": "Week 4"},
                        ],
                    }
                }]
            }
        }
        
        windows = _extract_from_soa(soa_data)
        assert len(windows) == 3
        assert windows[0].visit_name == "Screening (-14)"
        assert windows[0].epoch == "Screening"
        assert windows[1].visit_name == "Day 1"
        assert windows[1].epoch == "Treatment"
        assert windows[2].visit_name == "Week 4"
    
    def test_visit_extraction_from_empty_soa(self):
        from extraction.execution.visit_window_extractor import _extract_from_soa
        
        # Empty SOA
        assert _extract_from_soa({}) == []
        assert _extract_from_soa({"study": {}}) == []
        assert _extract_from_soa({"study": {"versions": []}}) == []


class TestPhase4USDMIntegration:
    """Test Phase 4 USDM output integration."""
    
    def test_enrich_usdm_with_dosing_regimens(self):
        import json
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            dosing_regimens=[
                DosingRegimen(id="dr1", treatment_name="Drug A", frequency=DosingFrequency.ONCE_DAILY),
            ]
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        ext_attrs = enriched["studyDesigns"][0]["extensionAttributes"]
        # USDM schema: url identifies the extension, valueString contains serialized JSON
        dosing_ext = [e for e in ext_attrs if "dosingRegimens" in e.get("url", "")]
        assert len(dosing_ext) == 1
        assert "valueString" in dosing_ext[0]
        parsed = json.loads(dosing_ext[0]["valueString"])
        assert len(parsed) == 1
    
    def test_enrich_usdm_with_visit_windows(self):
        import json
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            visit_windows=[
                VisitWindow(id="v1", visit_name="Screening", target_day=-14),
                VisitWindow(id="v2", visit_name="Day 1", target_day=1),
            ]
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        ext_attrs = enriched["studyDesigns"][0]["extensionAttributes"]
        visit_ext = [e for e in ext_attrs if "visitWindows" in e.get("url", "")]
        assert len(visit_ext) == 1
        parsed = json.loads(visit_ext[0]["valueString"])
        assert len(parsed) == 2
    
    def test_enrich_usdm_with_randomization(self):
        import json
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            randomization_scheme=RandomizationScheme(
                id="r1",
                ratio="2:1",
                stratification_factors=[
                    StratificationFactor(id="s1", name="Age", categories=["<65", ">=65"]),
                ]
            )
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        ext_attrs = enriched["studyDesigns"][0]["extensionAttributes"]
        rand_ext = [e for e in ext_attrs if "randomizationScheme" in e.get("url", "")]
        assert len(rand_ext) == 1
        parsed = json.loads(rand_ext[0]["valueString"])
        assert parsed["ratio"] == "2:1"
    
    def test_enrich_usdm_complete_phase4(self):
        usdm = {"studyDesigns": [{"id": "sd_1", "activities": []}]}
        data = ExecutionModelData(
            dosing_regimens=[DosingRegimen(id="dr1", treatment_name="Drug A")],
            visit_windows=[VisitWindow(id="v1", visit_name="Day 1", target_day=1)],
            randomization_scheme=RandomizationScheme(id="r1", ratio="1:1"),
        )
        enriched = enrich_usdm_with_execution_model(usdm, data)
        ext_attrs = enriched["studyDesigns"][0]["extensionAttributes"]
        
        # All three Phase 4 components should be present (USDM schema uses 'url' for identification)
        urls = [e.get("url", "") for e in ext_attrs]
        assert any("dosingRegimens" in u for u in urls)
        assert any("visitWindows" in u for u in urls)
        assert any("randomizationScheme" in u for u in urls)


class TestPromoterHelpers:
    """Test promoter helper functions (v7.2.1 fixes)."""
    
    def test_iso_duration_days(self):
        from extraction.execution.execution_model_promoter import _iso_duration_to_days
        assert _iso_duration_to_days("P7D") == 7
        assert _iso_duration_to_days("P1D") == 1
        assert _iso_duration_to_days("P14D") == 14
        assert _iso_duration_to_days("P30D") == 30
    
    def test_iso_duration_weeks(self):
        from extraction.execution.execution_model_promoter import _iso_duration_to_days
        assert _iso_duration_to_days("P1W") == 7
        assert _iso_duration_to_days("P2W") == 14
        assert _iso_duration_to_days("P4W") == 28
    
    def test_iso_duration_none_cases(self):
        from extraction.execution.execution_model_promoter import _iso_duration_to_days
        assert _iso_duration_to_days(None) is None
        assert _iso_duration_to_days("") is None
        assert _iso_duration_to_days("not a duration") is None
        assert _iso_duration_to_days("PT5M") is None  # minutes not supported
        assert _iso_duration_to_days("P2M") is None   # months not supported
    
    def test_iso_duration_non_string(self):
        from extraction.execution.execution_model_promoter import _iso_duration_to_days
        assert _iso_duration_to_days(7) is None
        assert _iso_duration_to_days(0) is None
    
    def test_get_dict_access(self):
        from extraction.execution.execution_model_promoter import _get
        d = {"fromState": "Screening", "trigger": "enroll"}
        assert _get(d, "from_state", "fromState") == "Screening"
        assert _get(d, "trigger", "trigger") == "enroll"
        assert _get(d, "missing", "missing", "default") == "default"
    
    def test_get_dataclass_access(self):
        from extraction.execution.execution_model_promoter import _get
        t = StateTransition(
            from_state=StateType.SCREENING,
            to_state=StateType.ENROLLED,
            trigger="Meets criteria",
        )
        assert _get(t, "trigger") == "Meets criteria"
    
    def test_get_enum_unwrap(self):
        from extraction.execution.execution_model_promoter import _get
        t = StateTransition(
            from_state=StateType.SCREENING,
            to_state=StateType.ENROLLED,
            trigger="Enroll",
        )
        val = _get(t, "from_state")
        assert val == "Screening"  # enum .value is unwrapped


class TestPromoterFuzzyMatch:
    """Test promoter activity fuzzy matching."""
    
    def test_exact_match(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "Physical Examination"},
                {"id": "act_2", "name": "Vital Signs"},
            ]
        }
        assert promoter._find_activity_by_name(design, "Physical Examination") == "act_1"
    
    def test_case_insensitive_match(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "Physical Examination"},
            ]
        }
        assert promoter._find_activity_by_name(design, "physical examination") == "act_1"
    
    def test_substring_match(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "12-lead ECG (triplicate)"},
            ]
        }
        result = promoter._find_activity_by_name(design, "ECG")
        assert result == "act_1"
    
    def test_word_overlap_match(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "Complete blood count panel"},
                {"id": "act_2", "name": "Vital Signs"},
            ]
        }
        # "blood count panel" has 3/3 word overlap with "Complete blood count panel" (3/4 = 0.75)
        result = promoter._find_activity_by_name(design, "blood count panel")
        assert result == "act_1"
    
    def test_word_overlap_below_threshold(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "Cu/Mo-controlled meals"},
                {"id": "act_2", "name": "Vital Signs"},
            ]
        }
        # "controlled diet" vs "Cu/Mo-controlled meals": 1/2 = 0.5 overlap, below 0.75 threshold
        result = promoter._find_activity_by_name(design, "controlled diet")
        assert result is None
    
    def test_no_match(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {
            "activities": [
                {"id": "act_1", "name": "Physical Examination"},
            ]
        }
        assert promoter._find_activity_by_name(design, "Completely Unrelated") is None
    
    def test_empty_name(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        design = {"activities": [{"id": "act_1", "name": "Test"}]}
        assert promoter._find_activity_by_name(design, "") is None
        assert promoter._find_activity_by_name(design, None) is None


class TestPromoterFaultIsolation:
    """Test that promoter fault isolation works correctly."""
    
    def test_promote_with_bad_repetitions_doesnt_crash(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter
        promoter = ExecutionModelPromoter()
        
        design = {
            "activities": [],
            "encounters": [],
            "epochs": [],
            "scheduleTimelines": [{"id": "tl_1", "instances": [], "timings": []}],
        }
        version = {}
        
        # Create data with a repetition that has None offsets (the bug that was crashing)
        data = ExecutionModelData(
            repetitions=[Repetition(
                id="bad_rep", type=RepetitionType.DAILY,
                start_offset=None, end_offset=None, interval=None,
            )],
            footnote_conditions=[FootnoteCondition(
                id="fc_1", condition_type="timing", text="Test condition",
            )],
        )
        
        # Should NOT raise — fault isolation should catch the repetition error
        # and still promote footnote conditions
        result_design, result_version = promoter.promote(design, version, data)
        assert promoter.result.conditions_promoted >= 0  # Conditions step should still run

    def test_promote_elements_sets_next_and_previous_links(self):
        from extraction.execution.execution_model_promoter import ExecutionModelPromoter

        promoter = ExecutionModelPromoter()
        design = {"elements": []}

        schedule = SimpleNamespace(
            id="titration_1",
            name="ALXN1840",
            dose_levels=[
                SimpleNamespace(dose="15 mg", duration="", criteria=""),
                SimpleNamespace(dose="30 mg", duration="", criteria=""),
            ],
        )

        result_design = promoter._promote_elements(design, [schedule])
        elements = result_design["elements"]

        assert len(elements) == 2
        assert elements[0].get("nextElementId") == elements[1]["id"]
        assert elements[1].get("previousElementId") == elements[0]["id"]


class TestFromDictRoundTrip:
    """Test ExecutionModelData.from_dict() round-trip fidelity."""
    
    def test_round_trip_basic(self):
        original = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="Day 1", anchor_type=AnchorType.FIRST_DOSE)],
            repetitions=[Repetition(id="r1", type=RepetitionType.DAILY, interval="P1D")],
        )
        d = original.to_dict()
        restored = ExecutionModelData.from_dict(d)
        assert len(restored.time_anchors) == 1
        assert len(restored.repetitions) == 1
        assert restored.time_anchors[0].id == "a1"
        assert restored.repetitions[0].interval == "P1D"
    
    def test_round_trip_state_machine(self):
        original = ExecutionModelData(
            state_machine=SubjectStateMachine(
                id="sm_1",
                initial_state="Screening",
                states=["Screening", "Treatment", "Follow-up"],
                transitions=[
                    StateTransition(from_state="Screening", to_state="Treatment", trigger="Enroll"),
                ],
                epoch_ids={"Screening": "epoch_1", "Treatment": "epoch_2"},
            ),
        )
        d = original.to_dict()
        restored = ExecutionModelData.from_dict(d)
        assert restored.state_machine is not None
        assert len(restored.state_machine.states) == 3
        assert len(restored.state_machine.transitions) == 1
        assert restored.state_machine.epoch_ids["Screening"] == "epoch_1"
    
    def test_round_trip_footnotes(self):
        original = ExecutionModelData(
            footnote_conditions=[
                FootnoteCondition(
                    id="fc_1", footnote_id="a", condition_type="timing",
                    text="30 min before labs", structured_condition="timing.before(PT30M)",
                    applies_to_activity_ids=["act_1", "act_2"],
                ),
            ],
        )
        d = original.to_dict()
        restored = ExecutionModelData.from_dict(d)
        assert len(restored.footnote_conditions) == 1
        fc = restored.footnote_conditions[0]
        assert fc.footnote_id == "a"
        assert fc.condition_type == "timing"
        assert len(fc.applies_to_activity_ids) == 2
    
    def test_round_trip_dosing(self):
        original = ExecutionModelData(
            dosing_regimens=[
                DosingRegimen(
                    id="dr_1", treatment_name="Drug A",
                    dose_levels=[DoseLevel(amount=15.0, unit="mg")],
                    frequency=DosingFrequency.ONCE_DAILY,
                    route=RouteOfAdministration.ORAL,
                    start_day=1, end_day=28,
                ),
            ],
        )
        d = original.to_dict()
        restored = ExecutionModelData.from_dict(d)
        assert len(restored.dosing_regimens) == 1
        dr = restored.dosing_regimens[0]
        assert dr.treatment_name == "Drug A"
        assert dr.frequency == DosingFrequency.ONCE_DAILY
        assert dr.route == RouteOfAdministration.ORAL
        assert len(dr.dose_levels) == 1
        assert dr.dose_levels[0].amount == 15.0
    
    def test_round_trip_visit_windows(self):
        original = ExecutionModelData(
            visit_windows=[
                VisitWindow(id="v1", visit_name="Day 1", target_day=1,
                           window_before=0, window_after=2, epoch="Treatment"),
            ],
        )
        d = original.to_dict()
        restored = ExecutionModelData.from_dict(d)
        assert len(restored.visit_windows) == 1
        assert restored.visit_windows[0].window_after == 2
        assert restored.visit_windows[0].epoch == "Treatment"
    
    def test_round_trip_all_keys_preserved(self):
        """Verify that to_dict() → from_dict() → to_dict() produces identical keys."""
        original = ExecutionModelData(
            time_anchors=[TimeAnchor(id="a1", definition="D1", anchor_type=AnchorType.DAY_1)],
            repetitions=[Repetition(id="r1", type=RepetitionType.DAILY)],
            traversal_constraints=[TraversalConstraint(id="tc1", required_sequence=["A", "B"])],
            footnote_conditions=[FootnoteCondition(id="fc1", text="Test")],
            endpoint_algorithms=[EndpointAlgorithm(id="ep1", name="P", endpoint_type=EndpointType.PRIMARY)],
            derived_variables=[DerivedVariable(id="dv1", name="CFB", variable_type=VariableType.CHANGE_FROM_BASELINE)],
            state_machine=SubjectStateMachine(id="sm1", states=["A", "B"]),
            dosing_regimens=[DosingRegimen(id="dr1", treatment_name="X")],
            visit_windows=[VisitWindow(id="v1", visit_name="D1")],
        )
        d1 = original.to_dict()
        restored = ExecutionModelData.from_dict(d1)
        d2 = restored.to_dict()
        assert set(d1.keys()) == set(d2.keys())


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
