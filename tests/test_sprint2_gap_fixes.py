"""
Regression tests for Sprint 2 gap fixes.

Tests cover:
  C2  – StudyVersion.rationale extracted from metadata
  C3  – InterventionalStudyDesign.rationale extracted from study design
  H1  – Organization.legalAddress (sponsor address)
  H2  – StudyVersion.dateValues (GovernanceDate)
  H4  – StudyDesign.characteristics codes
  H6  – Administration.dose emitted as USDM Quantity
  H7  – Administration.frequency emitted as USDM Code
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# C2: StudyVersion.rationale
# ---------------------------------------------------------------------------

class TestC2StudyVersionRationale:
    """C2: StudyVersion.rationale is extracted from metadata and wired to study_version."""

    def test_metadata_schema_holds_rationale(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            study_rationale="This study evaluates drug X for disease Y.",
        )
        assert md.study_rationale == "This study evaluates drug X for disease Y."

    def test_metadata_to_dict_includes_rationale(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            study_rationale="Rationale text here.",
        )
        d = md.to_dict()
        assert d["studyRationale"] == "Rationale text here."

    def test_metadata_to_dict_omits_rationale_when_none(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(study_name="Test")
        d = md.to_dict()
        assert "studyRationale" not in d

    def test_metadata_phase_combine_sets_rationale(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(
            study_name="Test",
            study_rationale="Drug X targets receptor Y.",
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert sv["rationale"] == "Drug X targets receptor Y."

    def test_metadata_phase_combine_no_rationale_when_absent(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(study_name="Test")
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "rationale" not in sv

    def test_metadata_phase_combine_fallback_rationale(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult

        result = PhaseResult(success=False, data=None)
        sv, sd, combined = {}, {}, {}
        prev = {"metadata": {"metadata": {"studyRationale": "Fallback rationale"}}}
        MetadataPhase().combine(result, sv, sd, combined, prev)
        assert sv["rationale"] == "Fallback rationale"

    def test_parse_metadata_response_extracts_rationale(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [],
            "identifiers": [],
            "studyRationale": "Scientific justification for this trial.",
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        assert md.study_rationale == "Scientific justification for this trial."


# ---------------------------------------------------------------------------
# C3: InterventionalStudyDesign.rationale
# ---------------------------------------------------------------------------

class TestC3DesignRationale:
    """C3: InterventionalStudyDesign.rationale is extracted and wired."""

    def test_schema_holds_rationale(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            rationale="Double-blind chosen to minimize bias.",
        )
        assert sd.rationale == "Double-blind chosen to minimize bias."

    def test_to_dict_includes_rationale(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            rationale="Parallel design for independent comparison.",
        )
        d = sd.to_dict()
        assert d["rationale"] == "Parallel design for independent comparison."

    def test_to_dict_omits_rationale_when_none(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(id="sd_1", name="Design")
        d = sd.to_dict()
        assert "rationale" not in d

    def test_extractor_parses_design_rationale(self):
        from extraction.studydesign.extractor import _parse_design_response
        raw = {
            "studyDesign": {
                "type": "Interventional",
                "designRationale": "Crossover design chosen for within-subject comparison.",
            },
            "arms": [{"name": "Arm A", "type": "Experimental Arm"}],
        }
        data = _parse_design_response(raw)
        assert data is not None
        assert data.study_design.rationale == "Crossover design chosen for within-subject comparison."

    def test_extractor_parses_rationale_key(self):
        from extraction.studydesign.extractor import _parse_design_response
        raw = {
            "studyDesign": {
                "type": "Interventional",
                "rationale": "Adaptive design for dose-finding.",
            },
            "arms": [],
        }
        data = _parse_design_response(raw)
        assert data is not None
        assert data.study_design.rationale == "Adaptive design for dose-finding."

    def test_phase_combine_sets_rationale(self):
        from pipeline.phases.studydesign import StudyDesignPhase
        from pipeline.base_phase import PhaseResult
        from extraction.studydesign.schema import (
            StudyDesignData, InterventionalStudyDesign,
        )

        isd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            rationale="Randomized to reduce selection bias.",
        )
        sd_data = StudyDesignData(study_design=isd)
        result = PhaseResult(success=True, data=sd_data)
        sv, sd, combined = {}, {}, {}
        StudyDesignPhase().combine(result, sv, sd, combined, {})
        assert sd["rationale"] == "Randomized to reduce selection bias."

    def test_phase_combine_fallback_rationale(self):
        from pipeline.phases.studydesign import StudyDesignPhase
        from pipeline.base_phase import PhaseResult

        result = PhaseResult(success=False, data=None)
        sv, sd, combined = {}, {}, {}
        prev = {"studydesign": {"studyDesign": {"rationale": "Fallback design rationale"}}}
        StudyDesignPhase().combine(result, sv, sd, combined, prev)
        assert sd["rationale"] == "Fallback design rationale"


# ---------------------------------------------------------------------------
# H1: Organization.legalAddress
# ---------------------------------------------------------------------------

class TestH1OrganizationLegalAddress:
    """H1: Organization.legalAddress is populated from sponsor address."""

    def test_organization_schema_address_fields(self):
        from extraction.metadata.schema import Organization, OrganizationType
        org = Organization(
            id="org_1", name="Sponsor Inc.",
            type=OrganizationType.PHARMACEUTICAL_COMPANY,
            address_city="Boston",
            address_state="MA",
            address_country="United States",
            address_postal_code="02101",
        )
        d = org.to_dict()
        assert "legalAddress" in d
        addr = d["legalAddress"]
        assert addr["city"] == "Boston"
        assert addr["district"] == "MA"
        assert addr["country"]["decode"] == "United States"
        assert addr["postalCode"] == "02101"
        assert addr["instanceType"] == "Address"

    def test_organization_no_address_when_empty(self):
        from extraction.metadata.schema import Organization, OrganizationType
        org = Organization(
            id="org_1", name="Sponsor Inc.",
            type=OrganizationType.PHARMACEUTICAL_COMPANY,
        )
        d = org.to_dict()
        assert "legalAddress" not in d

    def test_organization_partial_address(self):
        from extraction.metadata.schema import Organization, OrganizationType
        org = Organization(
            id="org_1", name="Sponsor Inc.",
            type=OrganizationType.PHARMACEUTICAL_COMPANY,
            address_country="Germany",
        )
        d = org.to_dict()
        assert "legalAddress" in d
        assert d["legalAddress"]["country"]["decode"] == "Germany"

    def test_parse_metadata_response_sponsor_address(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [
                {"name": "Pharma Corp", "type": "Pharmaceutical Company", "role": "Sponsor"}
            ],
            "identifiers": [],
            "sponsorAddress": {
                "city": "Basel",
                "state": "Basel-Stadt",
                "country": "Switzerland",
                "postalCode": "4056",
            },
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        assert md.organizations[0].address_city == "Basel"
        assert md.organizations[0].address_country == "Switzerland"

    def test_parse_metadata_response_non_sponsor_no_address(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [
                {"name": "CRO Inc", "type": "CRO", "role": "CRO"}
            ],
            "identifiers": [],
            "sponsorAddress": {"city": "Basel"},
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        assert md.organizations[0].address_city is None


# ---------------------------------------------------------------------------
# H2: StudyVersion.dateValues (GovernanceDate)
# ---------------------------------------------------------------------------

class TestH2GovernanceDates:
    """H2: GovernanceDate entities are created from extracted dates."""

    def test_metadata_schema_holds_dates(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            protocol_date="2024-03-15",
            sponsor_approval_date="2024-03-20",
            original_protocol_date="2023-01-10",
        )
        assert md.sponsor_approval_date == "2024-03-20"
        assert md.original_protocol_date == "2023-01-10"

    def test_metadata_to_dict_includes_dates(self):
        from extraction.metadata.schema import StudyMetadata
        md = StudyMetadata(
            study_name="Test",
            sponsor_approval_date="2024-03-20",
        )
        d = md.to_dict()
        assert d["sponsorApprovalDate"] == "2024-03-20"

    def test_phase_combine_creates_governance_dates(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(
            study_name="Test",
            protocol_date="2024-03-15",
            sponsor_approval_date="2024-03-20",
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "dateValues" in sv
        assert len(sv["dateValues"]) == 2
        names = [dv["name"] for dv in sv["dateValues"]]
        assert "Protocol Date" in names
        assert "Sponsor Approval Date" in names

    def test_phase_combine_no_dates_when_absent(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(study_name="Test")
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        assert "dateValues" not in sv

    def test_governance_date_structure(self):
        from pipeline.phases.metadata import MetadataPhase
        from pipeline.base_phase import PhaseResult
        from extraction.metadata.schema import StudyMetadata

        md = StudyMetadata(
            study_name="Test",
            original_protocol_date="2023-01-10",
        )
        result = PhaseResult(success=True, data=md)
        sv, sd, combined = {}, {}, {}
        MetadataPhase().combine(result, sv, sd, combined, {})
        dv = sv["dateValues"][0]
        assert dv["instanceType"] == "GovernanceDate"
        assert dv["dateValue"] == "2023-01-10"
        assert dv["type"]["instanceType"] == "Code"

    def test_parse_metadata_response_extracts_dates(self):
        from extraction.metadata.extractor import _parse_metadata_response
        raw = {
            "titles": [{"text": "Test Study", "type": "Official Study Title"}],
            "organizations": [],
            "identifiers": [],
            "governanceDates": {
                "sponsorApprovalDate": "2024-06-01",
                "originalProtocolDate": "2023-12-15",
            },
        }
        md = _parse_metadata_response(raw)
        assert md is not None
        assert md.sponsor_approval_date == "2024-06-01"
        assert md.original_protocol_date == "2023-12-15"


# ---------------------------------------------------------------------------
# H4: StudyDesign.characteristics
# ---------------------------------------------------------------------------

class TestH4DesignCharacteristics:
    """H4: StudyDesign.characteristics are extracted and emitted as Code objects."""

    def test_schema_holds_characteristics(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            characteristics=["Parallel", "Adaptive"],
        )
        assert sd.characteristics == ["Parallel", "Adaptive"]

    def test_to_dict_emits_coded_characteristics(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            characteristics=["Crossover"],
        )
        d = sd.to_dict()
        assert "characteristics" in d
        assert len(d["characteristics"]) == 1
        char = d["characteristics"][0]
        assert char["decode"] == "Crossover"
        assert char["instanceType"] == "Code"
        assert "id" in char

    def test_to_dict_omits_characteristics_when_empty(self):
        from extraction.studydesign.schema import InterventionalStudyDesign
        sd = InterventionalStudyDesign(id="sd_1", name="Design")
        d = sd.to_dict()
        assert "characteristics" not in d

    def test_extractor_parses_characteristics(self):
        from extraction.studydesign.extractor import _parse_design_response
        raw = {
            "studyDesign": {
                "type": "Interventional",
                "characteristics": ["Parallel", "Multicenter"],
            },
            "arms": [],
        }
        data = _parse_design_response(raw)
        assert data is not None
        assert data.study_design.characteristics == ["Parallel", "Multicenter"]

    def test_extractor_handles_single_string_characteristic(self):
        from extraction.studydesign.extractor import _parse_design_response
        raw = {
            "studyDesign": {
                "type": "Interventional",
                "characteristics": "Factorial",
            },
            "arms": [],
        }
        data = _parse_design_response(raw)
        assert data is not None
        assert data.study_design.characteristics == ["Factorial"]

    def test_phase_combine_sets_characteristics(self):
        from pipeline.phases.studydesign import StudyDesignPhase
        from pipeline.base_phase import PhaseResult
        from extraction.studydesign.schema import (
            StudyDesignData, InterventionalStudyDesign,
        )

        isd = InterventionalStudyDesign(
            id="sd_1", name="Design",
            characteristics=["Parallel"],
        )
        sd_data = StudyDesignData(study_design=isd)
        result = PhaseResult(success=True, data=sd_data)
        sv, sd, combined = {}, {}, {}
        StudyDesignPhase().combine(result, sv, sd, combined, {})
        assert "characteristics" in sd
        assert sd["characteristics"][0]["decode"] == "Parallel"

    def test_phase_combine_fallback_characteristics(self):
        from pipeline.phases.studydesign import StudyDesignPhase
        from pipeline.base_phase import PhaseResult

        result = PhaseResult(success=False, data=None)
        sv, sd, combined = {}, {}, {}
        prev = {"studydesign": {"studyDesign": {
            "characteristics": [{"code": "X", "decode": "Adaptive", "instanceType": "Code"}]
        }}}
        StudyDesignPhase().combine(result, sv, sd, combined, prev)
        assert sd["characteristics"][0]["decode"] == "Adaptive"


# ---------------------------------------------------------------------------
# H6: Administration.dose as USDM Quantity
# ---------------------------------------------------------------------------

class TestH6AdministrationDose:
    """H6: Administration.dose is emitted as a USDM Quantity object."""

    def test_dose_parsed_as_quantity(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug A 100mg", dose="100 mg")
        d = admin.to_dict()
        assert isinstance(d["dose"], dict)
        assert d["dose"]["instanceType"] == "Quantity"
        assert d["dose"]["value"] == 100.0
        assert d["dose"]["unit"]["standardCode"]["decode"] == "mg"

    def test_dose_with_complex_unit(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug B", dose="5 mg/kg")
        d = admin.to_dict()
        assert d["dose"]["value"] == 5.0
        assert d["dose"]["unit"]["standardCode"]["decode"] == "mg/kg"

    def test_dose_with_decimal(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug C", dose="0.5 mL")
        d = admin.to_dict()
        assert d["dose"]["value"] == 0.5
        assert d["dose"]["unit"]["standardCode"]["decode"] == "mL"

    def test_dose_unparseable_fallback(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug D", dose="as directed")
        d = admin.to_dict()
        assert d["dose"]["instanceType"] == "Quantity"
        assert d["dose"]["value"] == 0
        assert d["dose"]["unit"]["standardCode"]["decode"] == "as directed"

    def test_dose_absent(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug E")
        d = admin.to_dict()
        assert "dose" not in d

    def test_dose_with_comma(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug F", dose="1,000 IU")
        d = admin.to_dict()
        assert d["dose"]["value"] == 1000.0
        assert d["dose"]["unit"]["standardCode"]["decode"] == "IU"

    def test_parse_dose_string_helper(self):
        from extraction.interventions.schema import Administration
        assert Administration._parse_dose_string("100 mg") == (100.0, "mg")
        assert Administration._parse_dose_string("0.25 mg/m2") == (0.25, "mg/m2")
        val, unit = Administration._parse_dose_string("unknown")
        assert val is None


# ---------------------------------------------------------------------------
# H7: Administration.frequency as USDM Code
# ---------------------------------------------------------------------------

class TestH7AdministrationFrequency:
    """H7: Administration.frequency is emitted as a USDM Code object."""

    def test_frequency_emitted_as_code(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug A", dose_frequency="once daily")
        d = admin.to_dict()
        assert "frequency" in d
        assert d["frequency"]["instanceType"] == "AliasCode"
        assert d["frequency"]["standardCode"]["decode"] == "once daily"

    def test_frequency_twice_daily(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug B", dose_frequency="twice daily")
        d = admin.to_dict()
        assert d["frequency"]["standardCode"]["decode"] == "twice daily"

    def test_frequency_absent(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug C")
        d = admin.to_dict()
        assert "frequency" not in d

    def test_frequency_every_2_weeks(self):
        from extraction.interventions.schema import Administration
        admin = Administration(id="a1", name="Drug D", dose_frequency="every 2 weeks")
        d = admin.to_dict()
        assert d["frequency"]["standardCode"]["decode"] == "every 2 weeks"
        assert "id" in d["frequency"]


# ---------------------------------------------------------------------------
# Integration: Full Administration to_dict with dose + frequency + route
# ---------------------------------------------------------------------------

class TestAdministrationIntegration:
    """Integration test: Administration emits all H6/H7 fields together."""

    def test_full_administration_dict(self):
        from extraction.interventions.schema import Administration, RouteOfAdministration
        admin = Administration(
            id="admin_1",
            name="Drug X 200mg BID",
            dose="200 mg",
            dose_frequency="twice daily",
            route=RouteOfAdministration.ORAL,
            duration="24 weeks",
            description="Oral administration",
        )
        d = admin.to_dict()
        # H6: dose as Quantity
        assert d["dose"]["instanceType"] == "Quantity"
        assert d["dose"]["value"] == 200.0
        # H7: frequency as AliasCode
        assert d["frequency"]["instanceType"] == "AliasCode"
        assert d["frequency"]["standardCode"]["decode"] == "twice daily"
        # Route as AliasCode (upgraded)
        assert d["route"]["instanceType"] == "AliasCode"
        # Other fields
        assert d["duration"]["instanceType"] == "Duration"
        assert d["duration"]["text"] == "24 weeks"
        assert d["duration"]["durationWillVary"] is True
        assert d["description"] == "Oral administration"

    def test_interventions_data_to_dict_includes_structured_dose(self):
        from extraction.interventions.schema import (
            InterventionsData, StudyIntervention, Administration,
            RouteOfAdministration,
        )
        admin = Administration(
            id="admin_1", name="Drug X 100mg QD",
            dose="100 mg", dose_frequency="once daily",
            route=RouteOfAdministration.ORAL,
        )
        data = InterventionsData(administrations=[admin])
        d = data.to_dict()
        admin_dict = d["administrations"][0]
        assert admin_dict["dose"]["instanceType"] == "Quantity"
        assert admin_dict["frequency"]["instanceType"] == "AliasCode"
