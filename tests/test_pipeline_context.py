"""
Unit tests for extraction.pipeline_context.PipelineContext.

Covers: initialization, update_from_* methods, query methods,
snapshot/merge_from (thread isolation), to_dict serialization,
and the merge field mapping contract.
"""

import copy
import json
import threading
import pytest

from extraction.pipeline_context import (
    PipelineContext, create_pipeline_context, PHASE_FIELD_OWNERSHIP,
    SoAContext, MetadataContext, DesignContext, InterventionContext, SchedulingContext,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EPOCHS = [
    {"id": "epoch_1", "name": "Screening"},
    {"id": "epoch_2", "name": "Treatment"},
    {"id": "epoch_3", "name": "Follow-up"},
]

SAMPLE_ENCOUNTERS = [
    {"id": "enc_1", "name": "Visit 1", "epochId": "epoch_1"},
    {"id": "enc_2", "name": "Visit 2", "epochId": "epoch_2"},
]

SAMPLE_ACTIVITIES = [
    {"id": "act_1", "name": "Vital Signs"},
    {"id": "act_2", "name": "Blood Draw"},
]

SAMPLE_ARMS = [
    {"id": "arm_1", "name": "WTX101 15mg"},
    {"id": "arm_2", "name": "Placebo"},
]

SAMPLE_SOA_DATA = {
    "epochs": SAMPLE_EPOCHS,
    "encounters": SAMPLE_ENCOUNTERS,
    "activities": SAMPLE_ACTIVITIES,
    "arms": SAMPLE_ARMS,
    "studyCells": [{"id": "cell_1", "armId": "arm_1", "epochId": "epoch_1"}],
}

SAMPLE_SOA_NESTED = {
    "study": {
        "versions": [{
            "studyDesigns": [{
                "epochs": SAMPLE_EPOCHS,
                "encounters": SAMPLE_ENCOUNTERS,
                "activities": SAMPLE_ACTIVITIES,
                "arms": SAMPLE_ARMS,
                "studyCells": [],
            }]
        }]
    }
}


# ============================================================================
# Initialization
# ============================================================================

class TestPipelineContextInit:
    """Test PipelineContext creation and defaults."""

    def test_empty_context(self):
        ctx = PipelineContext()
        assert ctx.epochs == []
        assert ctx.encounters == []
        assert ctx.activities == []
        assert ctx.arms == []
        assert ctx.study_title == ""
        assert ctx.indication == ""

    def test_create_pipeline_context_no_soa(self):
        ctx = create_pipeline_context()
        assert isinstance(ctx, PipelineContext)
        assert ctx.epochs == []

    def test_create_pipeline_context_with_soa(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        assert len(ctx.epochs) == 3
        assert len(ctx.encounters) == 2
        assert len(ctx.activities) == 2
        assert len(ctx.arms) == 2

    def test_create_pipeline_context_with_nested_soa(self):
        ctx = create_pipeline_context(SAMPLE_SOA_NESTED)
        assert len(ctx.epochs) == 3
        assert len(ctx.encounters) == 2


# ============================================================================
# Update Methods
# ============================================================================

class TestUpdateFromSoA:
    """Test update_from_soa with various data shapes."""

    def test_update_from_flat_soa(self):
        ctx = PipelineContext()
        ctx.update_from_soa(SAMPLE_SOA_DATA)
        assert len(ctx.epochs) == 3
        assert len(ctx.encounters) == 2
        assert len(ctx.arms) == 2
        assert len(ctx.study_cells) == 1

    def test_update_from_nested_soa(self):
        ctx = PipelineContext()
        ctx.update_from_soa(SAMPLE_SOA_NESTED)
        assert len(ctx.epochs) == 3

    def test_update_from_empty_soa(self):
        ctx = PipelineContext()
        ctx.update_from_soa({})
        assert ctx.epochs == []

    def test_update_from_none_soa(self):
        ctx = PipelineContext()
        ctx.update_from_soa(None)
        assert ctx.epochs == []


class TestUpdateFromMetadata:
    """Test update_from_metadata with dict and object inputs."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_metadata({
            "studyTitle": "Wilson Disease Study",
            "studyId": "NCT04573309",
            "sponsor": "Alexion",
            "indication": "Wilson Disease",
            "phase": "Phase 3",
            "studyType": "Interventional",
        })
        assert ctx.study_title == "Wilson Disease Study"
        assert ctx.study_id == "NCT04573309"
        assert ctx.sponsor == "Alexion"
        assert ctx.indication == "Wilson Disease"
        assert ctx.phase == "Phase 3"
        assert ctx.study_type == "Interventional"

    def test_update_from_dict_snake_case(self):
        ctx = PipelineContext()
        ctx.update_from_metadata({
            "study_title": "Test Study",
            "study_id": "TEST-001",
            "study_type": "Observational",
        })
        assert ctx.study_title == "Test Study"
        assert ctx.study_id == "TEST-001"

    def test_update_from_object_with_to_dict(self):
        class MockMetadata:
            def to_dict(self):
                return {"studyTitle": "From Object", "indication": "Cancer"}
        ctx = PipelineContext()
        ctx.update_from_metadata(MockMetadata())
        assert ctx.study_title == "From Object"
        assert ctx.indication == "Cancer"

    def test_update_from_none(self):
        ctx = PipelineContext()
        ctx.study_title = "Original"
        ctx.update_from_metadata(None)
        assert ctx.study_title == "Original"


class TestUpdateFromEligibility:
    """Test update_from_eligibility."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_eligibility({
            "inclusionCriteria": [{"text": "Age ≥18"}],
            "exclusionCriteria": [{"text": "Pregnant"}],
        })
        assert len(ctx.inclusion_criteria) == 1
        assert len(ctx.exclusion_criteria) == 1

    def test_update_from_none(self):
        ctx = PipelineContext()
        ctx.update_from_eligibility(None)
        assert ctx.inclusion_criteria == []


class TestUpdateFromObjectives:
    """Test update_from_objectives."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_objectives({
            "objectives": [{"id": "obj_1", "text": "Primary"}],
            "endpoints": [{"id": "ep_1", "text": "NCC change"}],
        })
        assert len(ctx.objectives) == 1
        assert len(ctx.endpoints) == 1


class TestUpdateFromStudyDesign:
    """Test update_from_studydesign."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_studydesign({
            "arms": SAMPLE_ARMS,
            "cohorts": [{"id": "coh_1", "name": "Cohort A"}],
        })
        assert len(ctx.arms) == 2
        assert len(ctx.cohorts) == 1
        # Lookup maps should be rebuilt
        assert ctx._arm_by_id.get("arm_1") is not None


class TestUpdateFromInterventions:
    """Test update_from_interventions."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_interventions({
            "interventions": [{"id": "int_1", "name": "WTX101"}],
            "products": [{"id": "prod_1", "name": "WTX101 tablet"}],
        })
        assert len(ctx.interventions) == 1
        assert len(ctx.products) == 1
        assert ctx._intervention_by_id.get("int_1") is not None


class TestUpdateFromProcedures:
    """Test update_from_procedures."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_procedures({
            "procedures": [{"id": "proc_1", "name": "ECG"}],
            "devices": [{"id": "dev_1", "name": "ECG Machine"}],
        })
        assert len(ctx.procedures) == 1
        assert len(ctx.devices) == 1


class TestUpdateFromScheduling:
    """Test update_from_scheduling."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_scheduling({
            "timings": [{"id": "t_1", "type": "FIXED"}],
            "rules": [{"id": "r_1"}],
        })
        assert len(ctx.timings) == 1
        assert len(ctx.scheduling_rules) == 1


class TestUpdateFromExecutionModel:
    """Test update_from_execution_model."""

    def test_update_from_dict(self):
        ctx = PipelineContext()
        ctx.update_from_execution_model({
            "timeAnchors": [{"id": "ta_1"}],
            "repetitions": [{"id": "rep_1"}],
            "traversalConstraints": [{"id": "tc_1"}],
            "footnoteConditions": [{"id": "fc_1"}],
        })
        assert len(ctx.time_anchors) == 1
        assert len(ctx.repetitions) == 1
        assert len(ctx.traversal_constraints) == 1
        assert len(ctx.footnote_conditions) == 1


# ============================================================================
# Query Methods
# ============================================================================

class TestQueryMethods:
    """Test has_*, get_*, find_* query methods."""

    def test_has_methods_empty(self):
        ctx = PipelineContext()
        assert not ctx.has_epochs()
        assert not ctx.has_encounters()
        assert not ctx.has_activities()
        assert not ctx.has_arms()
        assert not ctx.has_interventions()
        assert not ctx.has_objectives()

    def test_has_methods_populated(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        assert ctx.has_epochs()
        assert ctx.has_encounters()
        assert ctx.has_activities()
        assert ctx.has_arms()

    def test_get_epoch_ids(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        ids = ctx.get_epoch_ids()
        assert ids == ["epoch_1", "epoch_2", "epoch_3"]

    def test_get_epoch_names(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        names = ctx.get_epoch_names()
        assert names == ["Screening", "Treatment", "Follow-up"]

    def test_get_activity_names(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        names = ctx.get_activity_names()
        assert names == ["Vital Signs", "Blood Draw"]

    def test_get_intervention_names(self):
        ctx = PipelineContext()
        ctx.update_from_interventions({
            "interventions": [{"id": "i1", "name": "Drug A"}, {"id": "i2", "name": "Drug B"}],
        })
        assert ctx.get_intervention_names() == ["Drug A", "Drug B"]

    def test_find_epoch_by_name(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        epoch = ctx.find_epoch_by_name("Treatment")
        assert epoch is not None
        assert epoch["id"] == "epoch_2"
        # Case insensitive
        assert ctx.find_epoch_by_name("TREATMENT") is not None
        assert ctx.find_epoch_by_name("nonexistent") is None

    def test_find_epoch_by_id(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        assert ctx.find_epoch_by_id("epoch_1")["name"] == "Screening"
        assert ctx.find_epoch_by_id("nonexistent") is None

    def test_find_activity_by_name(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        act = ctx.find_activity_by_name("vital signs")
        assert act is not None
        assert act["id"] == "act_1"

    def test_find_intervention_by_id(self):
        ctx = PipelineContext()
        ctx.update_from_interventions({
            "interventions": [{"id": "int_1", "name": "WTX101"}],
        })
        assert ctx.find_intervention_by_id("int_1")["name"] == "WTX101"
        assert ctx.find_intervention_by_id("nonexistent") is None


# ============================================================================
# Snapshot & Merge (Thread Isolation)
# ============================================================================

class TestSnapshotAndMerge:
    """Test snapshot() creates independent copy and merge_from() integrates results."""

    def test_snapshot_is_independent(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        snap = ctx.snapshot()

        # Mutate snapshot
        snap.epochs.append({"id": "epoch_new", "name": "New Epoch"})
        snap.study_title = "Modified Title"

        # Original should be unchanged
        assert len(ctx.epochs) == 3
        assert ctx.study_title == ""

    def test_snapshot_deep_copies_nested(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        snap = ctx.snapshot()

        # Mutate a nested dict in the snapshot
        snap.epochs[0]["name"] = "MUTATED"

        # Original should be unchanged
        assert ctx.epochs[0]["name"] == "Screening"

    def test_merge_from_metadata(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.study_title = "Merged Title"
        snap.indication = "Wilson Disease"
        snap.phase = "Phase 3"

        ctx.merge_from("metadata", snap)
        assert ctx.study_title == "Merged Title"
        assert ctx.indication == "Wilson Disease"
        assert ctx.phase == "Phase 3"

    def test_merge_from_eligibility(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.inclusion_criteria = [{"text": "Age ≥18"}]
        snap.exclusion_criteria = [{"text": "Pregnant"}]

        ctx.merge_from("eligibility", snap)
        assert len(ctx.inclusion_criteria) == 1
        assert len(ctx.exclusion_criteria) == 1

    def test_merge_from_objectives(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.objectives = [{"id": "obj_1"}]
        snap.endpoints = [{"id": "ep_1"}]

        ctx.merge_from("objectives", snap)
        assert len(ctx.objectives) == 1
        assert len(ctx.endpoints) == 1

    def test_merge_from_studydesign(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.arms = SAMPLE_ARMS
        snap.cohorts = [{"id": "coh_1"}]

        ctx.merge_from("studydesign", snap)
        assert len(ctx.arms) == 2
        assert len(ctx.cohorts) == 1

    def test_merge_from_interventions(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.interventions = [{"id": "int_1", "name": "Drug"}]
        snap.products = [{"id": "prod_1"}]

        ctx.merge_from("interventions", snap)
        assert len(ctx.interventions) == 1
        assert ctx._intervention_by_id.get("int_1") is not None

    def test_merge_from_unknown_phase_is_noop(self):
        ctx = PipelineContext()
        ctx.study_title = "Original"
        snap = ctx.snapshot()
        snap.study_title = "Should Not Merge"

        ctx.merge_from("unknown_phase", snap)
        assert ctx.study_title == "Original"

    def test_merge_does_not_overwrite_with_empty(self):
        ctx = PipelineContext()
        ctx.study_title = "Existing Title"
        snap = ctx.snapshot()
        snap.study_title = ""  # Empty — should not overwrite

        ctx.merge_from("metadata", snap)
        assert ctx.study_title == "Existing Title"

    def test_merge_from_execution(self):
        ctx = PipelineContext()
        snap = ctx.snapshot()
        snap.time_anchors = [{"id": "ta_1"}]
        snap.repetitions = [{"id": "rep_1"}]

        ctx.merge_from("execution", snap)
        assert len(ctx.time_anchors) == 1
        assert len(ctx.repetitions) == 1

    def test_concurrent_snapshots_are_isolated(self):
        """Verify that two parallel snapshots don't interfere."""
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        results = {}

        def worker(name, title):
            snap = ctx.snapshot()
            snap.study_title = title
            snap.arms.append({"id": f"arm_{name}", "name": name})
            results[name] = snap

        t1 = threading.Thread(target=worker, args=("A", "Title A"))
        t2 = threading.Thread(target=worker, args=("B", "Title B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Original unchanged
        assert ctx.study_title == ""
        assert len(ctx.arms) == 2

        # Each snapshot has its own mutation
        assert results["A"].study_title == "Title A"
        assert results["B"].study_title == "Title B"
        assert len(results["A"].arms) == 3  # 2 original + 1 added
        assert len(results["B"].arms) == 3


# ============================================================================
# Serialization
# ============================================================================

class TestSerialization:
    """Test to_dict and get_summary."""

    def test_to_dict_keys(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        d = ctx.to_dict()
        expected_keys = {
            'epochs', 'encounters', 'activities', 'timepoints',
            'arms', 'cohorts', 'study_cells',
            'study_title', 'study_id', 'sponsor', 'indication', 'phase', 'study_type',
            'inclusion_criteria', 'exclusion_criteria',
            'objectives', 'endpoints',
            'interventions', 'products',
            'procedures', 'devices',
            'timings', 'scheduling_rules',
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        d = ctx.to_dict()
        assert len(d['epochs']) == 3
        assert len(d['arms']) == 2

    def test_get_summary_empty(self):
        ctx = PipelineContext()
        assert ctx.get_summary() == "empty"

    def test_get_summary_populated(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        summary = ctx.get_summary()
        assert "3 epochs" in summary
        assert "2 encounters" in summary
        assert "2 activities" in summary
        assert "2 arms" in summary


# ============================================================================
# Merge Field Mapping Contract
# ============================================================================

class TestMergeFieldMapping:
    """Verify the PHASE_FIELD_OWNERSHIP constant stays in sync with PipelineContext."""

    def test_all_phases_have_merge_mapping(self):
        """Every phase that writes to context must have a merge_from mapping."""
        ctx = PipelineContext()
        snap = ctx.snapshot()

        for phase_name, fields in PHASE_FIELD_OWNERSHIP.items():
            # Set a sentinel value on each field
            for f in fields:
                current = getattr(snap, f)
                if isinstance(current, list):
                    setattr(snap, f, [{"sentinel": True}])
                elif isinstance(current, str):
                    setattr(snap, f, "sentinel")

            # Merge and verify
            ctx.merge_from(phase_name, snap)
            for f in fields:
                val = getattr(ctx, f)
                if isinstance(val, list):
                    assert len(val) > 0, f"merge_from('{phase_name}') did not merge field '{f}'"
                elif isinstance(val, str):
                    assert val == "sentinel", f"merge_from('{phase_name}') did not merge field '{f}'"

    def test_merge_fields_are_valid_attributes(self):
        """All fields in PHASE_FIELD_OWNERSHIP must exist on PipelineContext."""
        ctx = PipelineContext()
        for phase_name, fields in PHASE_FIELD_OWNERSHIP.items():
            for f in fields:
                assert hasattr(ctx, f), f"Field '{f}' in PHASE_FIELD_OWNERSHIP['{phase_name}'] not found on PipelineContext"

    def test_ownership_covers_expected_phases(self):
        """PHASE_FIELD_OWNERSHIP should cover all data-producing phases."""
        expected_phases = {'metadata', 'eligibility', 'objectives', 'studydesign',
                          'interventions', 'procedures', 'scheduling', 'narrative',
                          'execution'}
        assert set(PHASE_FIELD_OWNERSHIP.keys()) == expected_phases


# ============================================================================
# Sub-Context Decomposition (W-HIGH-2)
# ============================================================================

class TestSubContextDecomposition:
    """Verify W-HIGH-2 sub-context structure and backward compatibility."""

    def test_sub_contexts_exist(self):
        ctx = PipelineContext()
        assert isinstance(ctx.soa, SoAContext)
        assert isinstance(ctx.metadata, MetadataContext)
        assert isinstance(ctx.design, DesignContext)
        assert isinstance(ctx.intervention, InterventionContext)
        assert isinstance(ctx.scheduling, SchedulingContext)

    def test_property_delegates_to_soa(self):
        ctx = PipelineContext()
        ctx.epochs = SAMPLE_EPOCHS
        assert ctx.soa.epochs is SAMPLE_EPOCHS
        ctx.encounters = SAMPLE_ENCOUNTERS
        assert ctx.soa.encounters is SAMPLE_ENCOUNTERS
        ctx.activities = SAMPLE_ACTIVITIES
        assert ctx.soa.activities is SAMPLE_ACTIVITIES

    def test_property_delegates_to_metadata(self):
        ctx = PipelineContext()
        ctx.study_title = "Test"
        assert ctx.metadata.study_title == "Test"
        ctx.sponsor = "Acme"
        assert ctx.metadata.sponsor == "Acme"

    def test_property_delegates_to_design(self):
        ctx = PipelineContext()
        ctx.arms = SAMPLE_ARMS
        assert ctx.design.arms is SAMPLE_ARMS
        ctx.inclusion_criteria = [{"text": "Age ≥18"}]
        assert ctx.design.inclusion_criteria == [{"text": "Age ≥18"}]

    def test_property_delegates_to_intervention(self):
        ctx = PipelineContext()
        ctx.interventions = [{"id": "i1"}]
        assert ctx.intervention.interventions == [{"id": "i1"}]
        ctx.procedures = [{"id": "p1"}]
        assert ctx.intervention.procedures == [{"id": "p1"}]

    def test_property_delegates_to_scheduling(self):
        ctx = PipelineContext()
        ctx.timings = [{"id": "t1"}]
        assert ctx.scheduling.timings == [{"id": "t1"}]
        ctx.time_anchors = [{"id": "ta1"}]
        assert ctx.scheduling.time_anchors == [{"id": "ta1"}]

    def test_lookup_maps_delegate(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        assert ctx._epoch_by_id is ctx.soa._epoch_by_id
        assert ctx._arm_by_id is ctx.design._arm_by_id

    def test_snapshot_preserves_sub_contexts(self):
        ctx = create_pipeline_context(SAMPLE_SOA_DATA)
        ctx.study_title = "Original"
        snap = ctx.snapshot()
        # Sub-contexts exist on snapshot
        assert isinstance(snap.soa, SoAContext)
        assert isinstance(snap.metadata, MetadataContext)
        # Data is deep-copied
        snap.soa.epochs.append({"id": "new"})
        assert len(ctx.soa.epochs) == 3
        snap.metadata.study_title = "Changed"
        assert ctx.metadata.study_title == "Original"

    def test_sub_context_rebuild_maps(self):
        soa = SoAContext(epochs=[{"id": "e1", "name": "Screening"}])
        soa.rebuild_maps()
        assert soa._epoch_by_id["e1"]["name"] == "Screening"
        assert soa._epoch_by_name["screening"]["id"] == "e1"

    def test_design_context_rebuild_maps(self):
        dc = DesignContext(arms=[{"id": "a1", "name": "Active"}])
        dc.rebuild_maps()
        assert dc._arm_by_id["a1"]["name"] == "Active"

    def test_intervention_context_rebuild_maps(self):
        ic = InterventionContext(interventions=[{"id": "i1", "name": "Drug A"}])
        ic.rebuild_maps()
        assert ic._intervention_by_id["i1"]["name"] == "Drug A"
