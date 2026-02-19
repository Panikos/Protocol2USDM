"""
Regression tests for Sprint 3 (MEDIUM) and Sprint 4 (LOW) gap fixes.

Tests cover:
  M1  – StudyVersion.businessTherapeuticAreas from indications
  M2  – StudyRole.assignedPersons (PI name, medical monitor)
  M3/M9 – Link cohorts to StudyDesignPopulation
  M4  – StudyIntervention.minimumResponseDuration
  M5  – AdministrableProduct.identifiers
  M6  – StudyAmendment.secondaryReasons
  M7  – StudyAmendment.impacts
  M8  – StudyAmendment.changes
  L1  – StudyVersion.referenceIdentifiers
  L3  – StudyArm.notes
  L4  – StudyIntervention.notes
  L5  – AdministrableProduct.properties
  L6  – Procedure.isOrderable
"""

import pytest


# ---------------------------------------------------------------------------
# M1: StudyVersion.businessTherapeuticAreas
# ---------------------------------------------------------------------------

class TestM1BusinessTherapeuticAreas:
    """M1: Map indications to StudyVersion.businessTherapeuticAreas."""

    def test_combiner_maps_indications_to_bta(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata, Indication

        md = StudyMetadata(
            study_name="Test",
            indications=[
                Indication(id="ind_1", name="Type 2 Diabetes Mellitus"),
            ],
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "businessTherapeuticAreas" in sv
        assert len(sv["businessTherapeuticAreas"]) == 1
        assert sv["businessTherapeuticAreas"][0]["decode"] == "Type 2 Diabetes Mellitus"
        assert sv["businessTherapeuticAreas"][0]["instanceType"] == "Code"

    def test_combiner_no_bta_when_no_indications(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(study_name="Test")
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "businessTherapeuticAreas" not in sv

    def test_combiner_multiple_indications(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata, Indication

        md = StudyMetadata(
            study_name="Test",
            indications=[
                Indication(id="ind_1", name="Oncology"),
                Indication(id="ind_2", name="Breast Cancer"),
            ],
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert len(sv["businessTherapeuticAreas"]) == 2


# ---------------------------------------------------------------------------
# M2: StudyRole.assignedPersons
# ---------------------------------------------------------------------------

class TestM2AssignedPersons:
    """M2: StudyRole.assignedPersons (PI name, medical monitor)."""

    def test_study_role_holds_assigned_persons(self):
        from extraction.metadata.schema import StudyRole, StudyRoleCode
        role = StudyRole(
            id="role_1", name="Principal Investigator",
            code=StudyRoleCode.PRINCIPAL_INVESTIGATOR,
            assigned_persons=["Dr. Jane Smith"],
        )
        assert role.assigned_persons == ["Dr. Jane Smith"]

    def test_study_role_to_dict_emits_assigned_persons(self):
        from extraction.metadata.schema import StudyRole, StudyRoleCode
        role = StudyRole(
            id="role_1", name="Sponsor",
            code=StudyRoleCode.SPONSOR,
            assigned_persons=["Dr. Jane Smith", "Dr. John Doe"],
        )
        d = role.to_dict()
        assert "assignedPersons" in d
        assert len(d["assignedPersons"]) == 2
        assert d["assignedPersons"][0]["name"] == "Dr. Jane Smith"
        assert d["assignedPersons"][0]["instanceType"] == "AssignedPerson"

    def test_study_role_to_dict_omits_when_empty(self):
        from extraction.metadata.schema import StudyRole, StudyRoleCode
        role = StudyRole(id="role_1", name="Sponsor", code=StudyRoleCode.SPONSOR)
        d = role.to_dict()
        assert "assignedPersons" not in d

    def test_parse_metadata_response_key_personnel(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [
                {"name": "Pharma Corp", "type": "Pharmaceutical Company", "role": "Sponsor"}
            ],
            "identifiers": [],
            "keyPersonnel": [
                {"name": "Dr. Jane Smith", "role": "Principal Investigator"},
                {"name": "Dr. John Doe", "role": "Medical Monitor"},
            ],
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        # PI should create a standalone role since "principal investigator" != "sponsor"
        pi_roles = [r for r in md.roles if "investigator" in r.name.lower() or r.assigned_persons]
        assert any(r.assigned_persons for r in md.roles)


# ---------------------------------------------------------------------------
# M3/M9: Link cohorts to StudyDesignPopulation
# ---------------------------------------------------------------------------

class TestM3M9CohortPopulationLink:
    """M3/M9: Cohort→Population linkage. link_cohorts_to_population is now a
    no-op (cohortIds is non-USDM). nest_cohorts_in_population handles the
    USDM-compliant inline cohorts[] relationship."""

    def test_link_cohorts_is_noop(self):
        from pipeline.post_processing import link_cohorts_to_population
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "studyCohorts": [
                    {"id": "cohort_1", "name": "Cohort A"},
                    {"id": "cohort_2", "name": "Cohort B"},
                ],
                "population": {"id": "pop_1", "name": "ITT"},
            }]}]},
        }
        result = link_cohorts_to_population(combined)
        pop = result["study"]["versions"][0]["studyDesigns"][0]["population"]
        assert "cohortIds" not in pop  # No longer emitted (non-USDM)

    def test_nest_cohorts_in_population(self):
        from pipeline.post_processing import nest_cohorts_in_population
        combined = {
            "study": {"versions": [{"studyDesigns": [{
                "studyCohorts": [
                    {"id": "cohort_1", "name": "Cohort A"},
                    {"id": "cohort_2", "name": "Cohort B"},
                ],
                "population": {"id": "pop_1", "name": "ITT"},
            }]}]},
        }
        result = nest_cohorts_in_population(combined)
        pop = result["study"]["versions"][0]["studyDesigns"][0]["population"]
        assert len(pop.get("cohorts", [])) == 2  # USDM-compliant inline nesting


# ---------------------------------------------------------------------------
# M4: StudyIntervention.minimumResponseDuration
# ---------------------------------------------------------------------------

class TestM4MinimumResponseDuration:
    """M4: StudyIntervention.minimumResponseDuration."""

    def test_schema_holds_duration(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(
            id="si_1", name="Drug X",
            minimum_response_duration="12 weeks",
        )
        assert si.minimum_response_duration == "12 weeks"

    def test_to_dict_emits_duration(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(
            id="si_1", name="Drug X",
            minimum_response_duration="24 weeks",
        )
        d = si.to_dict()
        assert "minimumResponseDuration" in d
        assert d["minimumResponseDuration"]["text"] == "24 weeks"
        assert d["minimumResponseDuration"]["instanceType"] == "Duration"

    def test_to_dict_omits_when_none(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(id="si_1", name="Drug X")
        d = si.to_dict()
        assert "minimumResponseDuration" not in d


# ---------------------------------------------------------------------------
# M5: AdministrableProduct.identifiers
# ---------------------------------------------------------------------------

class TestM5ProductIdentifiers:
    """M5: AdministrableProduct.identifiers."""

    def test_schema_holds_identifiers(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(
            id="ap_1", name="Drug X Tablets",
            identifiers=[{"text": "NDC-12345"}],
        )
        assert len(ap.identifiers) == 1

    def test_to_dict_emits_identifiers(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(
            id="ap_1", name="Drug X Tablets",
            identifiers=[{"text": "NDC-12345"}, {"text": "MFG-001"}],
        )
        d = ap.to_dict()
        assert "identifiers" in d
        assert len(d["identifiers"]) == 2
        assert d["identifiers"][0]["text"] == "NDC-12345"

    def test_to_dict_omits_when_empty(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(id="ap_1", name="Drug X Tablets")
        d = ap.to_dict()
        assert "identifiers" not in d


# ---------------------------------------------------------------------------
# M6/M7/M8: StudyAmendment.secondaryReasons / impacts / changes
# ---------------------------------------------------------------------------

class TestM6M7M8AmendmentDetails:
    """M6/M7/M8: StudyAmendment secondary reasons, impacts, and changes."""

    def test_schema_holds_secondary_reasons(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            secondary_reasons=["Efficacy", "Safety"],
        )
        assert sa.secondary_reasons == ["Efficacy", "Safety"]

    def test_to_dict_emits_secondary_reasons(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            secondary_reasons=["Regulatory feedback"],
        )
        d = sa.to_dict()
        assert "secondaryReasons" in d
        assert len(d["secondaryReasons"]) == 1
        assert d["secondaryReasons"][0]["otherReason"] == "Regulatory feedback"
        assert d["secondaryReasons"][0]["instanceType"] == "StudyAmendmentReason"

    def test_schema_holds_impacts(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            impacts=[{"section": "5.2", "level": "Minor"}],
        )
        assert len(sa.impacts) == 1

    def test_to_dict_emits_impacts(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            impacts=[{"section": "5.2", "level": "Minor"}],
        )
        d = sa.to_dict()
        assert "impacts" in d

    def test_schema_holds_changes(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            changes=[{"before": "old text", "after": "new text"}],
        )
        assert len(sa.changes) == 1

    def test_to_dict_emits_changes(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(
            id="amend_1", number="2",
            changes=[{"before": "old", "after": "new"}],
        )
        d = sa.to_dict()
        assert "changes" in d

    def test_to_dict_omits_all_when_empty(self):
        from extraction.advanced.schema import StudyAmendment
        sa = StudyAmendment(id="amend_1", number="1")
        d = sa.to_dict()
        assert "secondaryReasons" not in d
        assert "impacts" not in d
        assert "changes" not in d


# ---------------------------------------------------------------------------
# L1: StudyVersion.referenceIdentifiers
# ---------------------------------------------------------------------------

class TestL1ReferenceIdentifiers:
    """L1: StudyVersion.referenceIdentifiers."""

    def test_schema_holds_reference_identifiers(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            reference_identifiers=[{"text": "IB-2024-001", "type": "Investigator Brochure"}],
        )
        assert len(md.reference_identifiers) == 1

    def test_to_dict_includes_reference_identifiers(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            reference_identifiers=[{"text": "IB-001", "type": "IB"}],
        )
        d = md.to_dict()
        assert "referenceIdentifiers" in d

    def test_to_dict_omits_when_empty(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(study_name="Test")
        d = md.to_dict()
        assert "referenceIdentifiers" not in d

    def test_combiner_wires_reference_identifiers(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(
            study_name="Test",
            reference_identifiers=[{"text": "IB-001", "type": "IB"}],
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "referenceIdentifiers" in sv
        assert sv["referenceIdentifiers"][0]["text"] == "IB-001"

    def test_parse_metadata_response_extracts_ref_ids(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [],
            "identifiers": [],
            "referenceIdentifiers": [
                {"text": "IB-2024-001", "type": "Investigator Brochure"},
                {"text": "SPONSOR-SUB-001", "type": "Related Protocol"},
            ],
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        assert len(md.reference_identifiers) == 2
        assert md.reference_identifiers[0]["text"] == "IB-2024-001"


# ---------------------------------------------------------------------------
# L3: StudyArm.notes
# ---------------------------------------------------------------------------

class TestL3ArmNotes:
    """L3: StudyArm.notes."""

    def test_schema_holds_notes(self):
        from extraction.studydesign.schema import StudyArm
        arm = StudyArm(id="arm_1", name="Arm A", notes=["Dose escalation applies"])
        assert arm.notes == ["Dose escalation applies"]

    def test_to_dict_emits_notes(self):
        from extraction.studydesign.schema import StudyArm
        arm = StudyArm(id="arm_1", name="Arm A", notes=["Note 1", "Note 2"])
        d = arm.to_dict()
        assert "notes" in d
        assert len(d["notes"]) == 2
        assert d["notes"][0]["text"] == "Note 1"
        assert d["notes"][0]["instanceType"] == "CommentAnnotation"

    def test_to_dict_omits_when_empty(self):
        from extraction.studydesign.schema import StudyArm
        arm = StudyArm(id="arm_1", name="Arm A")
        d = arm.to_dict()
        assert "notes" not in d


# ---------------------------------------------------------------------------
# L4: StudyIntervention.notes
# ---------------------------------------------------------------------------

class TestL4InterventionNotes:
    """L4: StudyIntervention.notes."""

    def test_schema_holds_notes(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(id="si_1", name="Drug X", notes=["Take with food"])
        assert si.notes == ["Take with food"]

    def test_to_dict_emits_notes(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(id="si_1", name="Drug X", notes=["Note"])
        d = si.to_dict()
        assert "notes" in d
        assert d["notes"][0]["text"] == "Note"
        assert d["notes"][0]["instanceType"] == "CommentAnnotation"

    def test_to_dict_omits_when_empty(self):
        from extraction.interventions.schema import StudyIntervention
        si = StudyIntervention(id="si_1", name="Drug X")
        d = si.to_dict()
        assert "notes" not in d


# ---------------------------------------------------------------------------
# L5: AdministrableProduct.properties
# ---------------------------------------------------------------------------

class TestL5ProductProperties:
    """L5: AdministrableProduct.properties."""

    def test_schema_holds_properties(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(
            id="ap_1", name="Drug X",
            properties=[{"name": "color", "value": "white"}],
        )
        assert len(ap.properties) == 1

    def test_to_dict_emits_properties(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(
            id="ap_1", name="Drug X",
            properties=[{"name": "storage", "value": "2-8°C"}],
        )
        d = ap.to_dict()
        assert "properties" in d
        assert d["properties"][0]["name"] == "storage"
        assert d["properties"][0]["instanceType"] == "AdministrableProductProperty"

    def test_to_dict_omits_when_empty(self):
        from extraction.interventions.schema import AdministrableProduct
        ap = AdministrableProduct(id="ap_1", name="Drug X")
        d = ap.to_dict()
        assert "properties" not in d


# ---------------------------------------------------------------------------
# L6: Procedure.isOrderable
# ---------------------------------------------------------------------------

class TestL6ProcedureIsOrderable:
    """L6: Procedure.isOrderable."""

    def test_schema_holds_is_orderable(self):
        from extraction.procedures.schema import Procedure
        proc = Procedure(id="proc_1", name="CBC", is_orderable=True)
        assert proc.is_orderable is True

    def test_to_dict_emits_is_orderable_true(self):
        from extraction.procedures.schema import Procedure
        proc = Procedure(id="proc_1", name="CBC", is_orderable=True)
        d = proc.to_dict()
        assert d["isOrderable"] is True

    def test_to_dict_emits_is_orderable_false(self):
        from extraction.procedures.schema import Procedure
        proc = Procedure(id="proc_1", name="Physical Exam", is_orderable=False)
        d = proc.to_dict()
        assert d["isOrderable"] is False

    def test_to_dict_omits_when_none(self):
        from extraction.procedures.schema import Procedure
        proc = Procedure(id="proc_1", name="Vital Signs")
        d = proc.to_dict()
        assert "isOrderable" not in d
