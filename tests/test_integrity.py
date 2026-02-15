"""Tests for pipeline.integrity — Referential Integrity Checker."""

import json
import os
import pytest

from pipeline.integrity import (
    IntegrityFinding,
    IntegrityReport,
    Severity,
    check_id_references,
    check_integrity,
    check_orphans,
    check_semantic_rules,
    save_integrity_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_usdm(design_overrides=None, version_overrides=None):
    """Build a minimal valid USDM dict for testing."""
    design = {
        'id': 'sd_1',
        'instanceType': 'InterventionalStudyDesign',
        'arms': [
            {'id': 'arm_1', 'name': 'Treatment', 'instanceType': 'StudyArm'},
            {'id': 'arm_2', 'name': 'Placebo', 'instanceType': 'StudyArm'},
        ],
        'epochs': [
            {'id': 'epoch_1', 'name': 'Screening', 'instanceType': 'StudyEpoch'},
            {'id': 'epoch_2', 'name': 'Treatment', 'instanceType': 'StudyEpoch'},
        ],
        'elements': [
            {'id': 'elem_1', 'name': 'Screening Element', 'instanceType': 'StudyElement'},
        ],
        'studyCells': [
            {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': ['elem_1']},
            {'id': 'cell_2', 'armId': 'arm_2', 'epochId': 'epoch_2', 'elementIds': []},
        ],
        'activities': [
            {'id': 'act_1', 'name': 'Vital Signs', 'instanceType': 'Activity'},
        ],
        'encounters': [
            {'id': 'enc_1', 'name': 'Visit 1', 'instanceType': 'Encounter'},
        ],
        'objectives': [
            {'id': 'obj_1', 'text': 'Primary objective', 'level': {'decode': 'Primary'}},
        ],
        'endpoints': [
            {'id': 'ep_1', 'text': 'Primary endpoint'},
        ],
        'eligibilityCriteria': [
            {'id': 'crit_1', 'text': 'Age >= 18', 'category': {'decode': 'Inclusion'}},
        ],
        'scheduleTimelines': [
            {
                'id': 'tl_1',
                'instances': [
                    {'id': 'sai_1', 'encounterId': 'enc_1', 'epochId': 'epoch_1', 'activityIds': ['act_1']},
                ],
                'timings': [
                    {'id': 'timing_1', 'name': 'Day 1'},
                ],
            },
        ],
    }
    if design_overrides:
        design.update(design_overrides)

    version = {
        'id': 'sv_1',
        'instanceType': 'StudyVersion',
        'studyDesigns': [design],
        'studyInterventions': [
            {'id': 'intv_1', 'name': 'Drug A', 'type': {'decode': 'Drug'}},
        ],
    }
    if version_overrides:
        version.update(version_overrides)

    return {
        'study': {
            'id': 'study_1',
            'versions': [version],
        },
    }


# ---------------------------------------------------------------------------
# Layer 1: ID Reference Tests
# ---------------------------------------------------------------------------

class TestIdReferences:
    def test_valid_references_produce_no_findings(self):
        usdm = _make_usdm()
        findings = check_id_references(usdm)
        assert len(findings) == 0

    def test_dangling_arm_reference_in_cell(self):
        usdm = _make_usdm(design_overrides={
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_MISSING', 'epochId': 'epoch_1', 'elementIds': []},
            ],
        })
        findings = check_id_references(usdm)
        dangling = [f for f in findings if f.rule == 'dangling_reference' and 'arm_MISSING' in f.entity_ids]
        assert len(dangling) == 1
        assert dangling[0].severity == Severity.ERROR

    def test_dangling_epoch_reference_in_cell(self):
        usdm = _make_usdm(design_overrides={
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_MISSING', 'elementIds': []},
            ],
        })
        findings = check_id_references(usdm)
        dangling = [f for f in findings if 'epoch_MISSING' in f.entity_ids]
        assert len(dangling) >= 1

    def test_dangling_encounter_in_instance(self):
        usdm = _make_usdm(design_overrides={
            'scheduleTimelines': [{
                'id': 'tl_1',
                'instances': [
                    {'id': 'sai_1', 'encounterId': 'enc_GONE', 'epochId': 'epoch_1', 'activityIds': ['act_1']},
                ],
                'timings': [],
            }],
        })
        findings = check_id_references(usdm)
        dangling = [f for f in findings if 'enc_GONE' in f.entity_ids]
        assert len(dangling) == 1

    def test_dangling_activity_ids_in_instance(self):
        usdm = _make_usdm(design_overrides={
            'scheduleTimelines': [{
                'id': 'tl_1',
                'instances': [
                    {'id': 'sai_1', 'encounterId': 'enc_1', 'epochId': 'epoch_1', 'activityIds': ['act_MISSING']},
                ],
                'timings': [],
            }],
        })
        findings = check_id_references(usdm)
        dangling = [f for f in findings if 'act_MISSING' in f.entity_ids]
        assert len(dangling) == 1

    def test_dangling_element_ids_in_cell(self):
        usdm = _make_usdm(design_overrides={
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': ['elem_GONE']},
            ],
        })
        findings = check_id_references(usdm)
        dangling = [f for f in findings if 'elem_GONE' in f.entity_ids]
        assert len(dangling) == 1

    def test_no_findings_when_collections_empty(self):
        """If target collection is empty, no dangling refs are reported."""
        usdm = _make_usdm(design_overrides={
            'estimands': [],
            'analysisPopulations': [],
        })
        findings = check_id_references(usdm)
        # Only check for estimand-related findings
        est_findings = [f for f in findings if 'Estimand' in f.message or 'AnalysisPopulation' in f.entity_type]
        assert len(est_findings) == 0


# ---------------------------------------------------------------------------
# Layer 2: Orphan Detection Tests
# ---------------------------------------------------------------------------

class TestOrphanDetection:
    def test_no_orphans_in_valid_usdm(self):
        usdm = _make_usdm()
        findings = check_orphans(usdm)
        # Some orphans may exist in the minimal fixture (e.g., arm_2 not used in instances)
        # but arms are referenced in cells so they shouldn't be orphans
        arm_orphans = [f for f in findings if f.entity_type == 'StudyArm']
        assert len(arm_orphans) == 0

    def test_orphan_activity_detected(self):
        usdm = _make_usdm(design_overrides={
            'activities': [
                {'id': 'act_1', 'name': 'Used Activity'},
                {'id': 'act_orphan', 'name': 'Orphan Activity'},
            ],
        })
        findings = check_orphans(usdm)
        orphan_acts = [f for f in findings if f.entity_type == 'Activity' and 'act_orphan' in f.entity_ids]
        assert len(orphan_acts) == 1
        assert orphan_acts[0].severity == Severity.WARNING

    def test_orphan_encounter_detected(self):
        usdm = _make_usdm(design_overrides={
            'encounters': [
                {'id': 'enc_1', 'name': 'Visit 1'},
                {'id': 'enc_orphan', 'name': 'Orphan Visit'},
            ],
        })
        findings = check_orphans(usdm)
        orphan_encs = [f for f in findings if f.entity_type == 'Encounter' and 'enc_orphan' in f.entity_ids]
        assert len(orphan_encs) == 1

    def test_orphan_analysis_population_is_skipped(self):
        usdm = _make_usdm(design_overrides={
            'analysisPopulations': [
                {'id': 'pop_1', 'name': 'Screened Set', 'instanceType': 'AnalysisPopulation'},
            ],
            'estimands': [],
        })
        findings = check_orphans(usdm)
        pop_orphans = [f for f in findings if f.entity_type == 'AnalysisPopulation' and 'pop_1' in f.entity_ids]
        assert len(pop_orphans) == 0

    def test_titration_element_chain_not_reported_as_orphan(self):
        usdm = _make_usdm(design_overrides={
            'elements': [
                {'id': 'elem_1', 'name': 'Dose Step 1', 'instanceType': 'StudyElement'},
                {
                    'id': 'elem_2',
                    'name': 'Dose Step 2',
                    'instanceType': 'StudyElement',
                    'previousElementId': 'elem_1',
                },
            ],
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': ['elem_1']},
            ],
        })
        findings = check_orphans(usdm)
        element_orphans = [f for f in findings if f.entity_type == 'StudyElement' and 'elem_2' in f.entity_ids]
        assert len(element_orphans) == 0

    def test_soa_sourced_activity_not_reported_as_orphan(self):
        usdm = _make_usdm(design_overrides={
            'activities': [
                {'id': 'act_1', 'name': 'Used Activity', 'instanceType': 'Activity'},
                {
                    'id': 'act_soa_derived',
                    'name': 'Unscheduled SoA Activity',
                    'instanceType': 'Activity',
                    'extensionAttributes': [
                        {
                            'id': 'ext_1',
                            'url': 'https://protocol2usdm.io/extensions/x-activitySources',
                            'valueString': 'soa',
                            'instanceType': 'ExtensionAttribute',
                        },
                    ],
                },
            ],
        })
        findings = check_orphans(usdm)
        activity_orphans = [f for f in findings if f.entity_type == 'Activity' and 'act_soa_derived' in f.entity_ids]
        assert len(activity_orphans) == 0


# ---------------------------------------------------------------------------
# Layer 3: Semantic Rules Tests
# ---------------------------------------------------------------------------

class TestSemanticRules:
    def test_arm_not_in_cell(self):
        usdm = _make_usdm(design_overrides={
            'arms': [
                {'id': 'arm_1', 'name': 'Treatment'},
                {'id': 'arm_3', 'name': 'New Arm'},
            ],
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': []},
            ],
        })
        findings = check_semantic_rules(usdm)
        arm_findings = [f for f in findings if f.rule == 'arm_not_in_cell']
        assert len(arm_findings) == 1
        assert 'arm_3' in arm_findings[0].entity_ids

    def test_epoch_not_in_cell(self):
        usdm = _make_usdm(design_overrides={
            'epochs': [
                {'id': 'epoch_1', 'name': 'Screening'},
                {'id': 'epoch_3', 'name': 'Follow-up'},
            ],
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': []},
            ],
        })
        findings = check_semantic_rules(usdm)
        epoch_findings = [f for f in findings if f.rule == 'epoch_not_in_cell']
        assert len(epoch_findings) == 1

    def test_terminal_epoch_exempt_from_cell_assignment(self):
        usdm = _make_usdm(design_overrides={
            'epochs': [
                {'id': 'epoch_1', 'name': 'Screening'},
                {'id': 'epoch_et', 'name': 'EOS or ET'},
            ],
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_1', 'epochId': 'epoch_1', 'elementIds': []},
            ],
        })
        findings = check_semantic_rules(usdm)
        epoch_findings = [f for f in findings if f.rule == 'epoch_not_in_cell']
        assert len(epoch_findings) == 0

    def test_unnamed_activities(self):
        usdm = _make_usdm(design_overrides={
            'activities': [
                {'id': 'act_1', 'name': 'Named'},
                {'id': 'act_2'},  # No name or label
            ],
        })
        findings = check_semantic_rules(usdm)
        unnamed = [f for f in findings if f.rule == 'unnamed_activities']
        assert len(unnamed) == 1

    def test_uncategorized_criteria(self):
        usdm = _make_usdm(design_overrides={
            'eligibilityCriteria': [
                {'id': 'crit_1', 'text': 'With category', 'category': {'decode': 'Inclusion'}},
                {'id': 'crit_2', 'text': 'Without category'},
            ],
        })
        findings = check_semantic_rules(usdm)
        uncat = [f for f in findings if f.rule == 'uncategorized_criteria']
        assert len(uncat) == 1

    def test_unleveled_objectives(self):
        usdm = _make_usdm(design_overrides={
            'objectives': [
                {'id': 'obj_1', 'text': 'Has level', 'level': {'decode': 'Primary'}},
                {'id': 'obj_2', 'text': 'No level'},
            ],
        })
        findings = check_semantic_rules(usdm)
        unlvl = [f for f in findings if f.rule == 'unleveled_objectives']
        assert len(unlvl) == 1

    def test_duplicate_ids(self):
        usdm = _make_usdm(design_overrides={
            'arms': [{'id': 'dupe_id', 'name': 'Arm'}],
            'epochs': [{'id': 'dupe_id', 'name': 'Epoch'}],
        })
        findings = check_semantic_rules(usdm)
        dupes = [f for f in findings if f.rule == 'duplicate_id']
        assert len(dupes) == 1
        assert 'dupe_id' in dupes[0].entity_ids

    def test_valid_usdm_minimal_findings(self):
        usdm = _make_usdm()
        findings = check_semantic_rules(usdm)
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegrityReport:
    def test_full_check_on_valid_usdm(self):
        usdm = _make_usdm()
        report = check_integrity(usdm)
        assert isinstance(report, IntegrityReport)
        assert report.error_count == 0

    def test_report_to_dict(self):
        report = IntegrityReport(findings=[
            IntegrityFinding(rule='test', severity=Severity.ERROR, message='msg'),
        ])
        d = report.to_dict()
        assert d['summary']['errors'] == 1
        assert len(d['findings']) == 1
        assert d['findings'][0]['severity'] == 'error'

    def test_save_integrity_report(self, tmp_path):
        report = IntegrityReport(findings=[
            IntegrityFinding(rule='test', severity=Severity.WARNING, message='test finding'),
        ])
        path = save_integrity_report(report, str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data['summary']['warnings'] == 1

    def test_multiple_layers_combined(self):
        """A USDM with issues in all three layers."""
        usdm = _make_usdm(design_overrides={
            'studyCells': [
                {'id': 'cell_1', 'armId': 'arm_MISSING', 'epochId': 'epoch_1', 'elementIds': []},
            ],
            'activities': [
                {'id': 'act_1', 'name': 'Used'},
                {'id': 'act_orphan', 'name': 'Orphan'},
            ],
            'objectives': [
                {'id': 'obj_1', 'text': 'No level'},
            ],
        })
        report = check_integrity(usdm)
        assert report.error_count >= 1  # Dangling arm ref
        assert report.warning_count >= 1  # Orphan + semantic


# ---------------------------------------------------------------------------
# Context Builder Tests
# ---------------------------------------------------------------------------

class TestContextBuilders:
    def test_scheduling_context_builder(self):
        from pipeline.phases.scheduling import _build_scheduling_context
        ctx = _build_scheduling_context(
            epochs=[{'name': 'Screening'}, {'name': 'Treatment'}],
            encounters=[{'name': 'Visit 1'}, {'name': 'Visit 2'}],
            arms=[{'name': 'Active'}, {'name': 'Placebo'}],
        )
        assert 'Screening' in ctx
        assert 'Visit 1' in ctx
        assert 'Active' in ctx

    def test_scheduling_context_empty(self):
        from pipeline.phases.scheduling import _build_scheduling_context
        ctx = _build_scheduling_context()
        assert ctx == ''

    def test_advanced_context_builder(self):
        from pipeline.phases.advanced import _build_advanced_context
        ctx = _build_advanced_context(
            objectives=[{'text': 'Test primary objective', 'level': {'decode': 'Primary'}}],
            endpoints=[{'text': 'Primary endpoint measure'}],
            interventions=[{'name': 'Drug A'}],
        )
        assert 'Primary' in ctx
        assert 'Drug A' in ctx
        assert 'Primary endpoint' in ctx

    def test_advanced_context_empty(self):
        from pipeline.phases.advanced import _build_advanced_context
        ctx = _build_advanced_context()
        assert ctx == ''


# ---------------------------------------------------------------------------
# Dependency Tests
# ---------------------------------------------------------------------------

class TestDependencyChanges:
    def test_scheduling_depends_on_studydesign(self):
        from pipeline.orchestrator import PHASE_DEPENDENCIES
        assert 'studydesign' in PHASE_DEPENDENCIES.get('scheduling', set())

    def test_advanced_depends_on_objectives(self):
        from pipeline.orchestrator import PHASE_DEPENDENCIES
        deps = PHASE_DEPENDENCIES.get('advanced', set())
        assert 'objectives' in deps
        assert 'eligibility' in deps
        assert 'interventions' in deps

    def test_execution_still_depends_on_scheduling(self):
        from pipeline.orchestrator import PHASE_DEPENDENCIES
        deps = PHASE_DEPENDENCIES.get('execution', set())
        assert 'scheduling' in deps
        assert 'metadata' in deps
