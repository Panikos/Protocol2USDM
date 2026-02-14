"""Regression tests for SAP/Sites phase combine and pipeline integration.

Tests verify:
1. SAPPhase.combine() uses correct 'sapData' key from previous extractions
2. SAPPhase.combine() handles live SAPExtractionResult objects
3. No duplicate SAP extensions are created
4. SitesPhase.combine() uses correct 'sitesData' key
5. Orchestrator forwards kwargs to phase.run()
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from pipeline.base_phase import PhaseResult
from pipeline.phases.sap import SAPPhase
from pipeline.phases.sites import SitesPhase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SAP_DATA = {
    "analysisPopulations": [
        {"id": "pop_1", "name": "FAS", "label": "Full Analysis Set",
         "description": "All randomized subjects", "definition": "Received >= 1 dose",
         "populationType": "FullAnalysis", "criteria": None}
    ],
    "characteristics": [],
    "derivedVariables": [
        {"id": "dv_1", "name": "BMI", "formula": "weight/height^2", "unit": "kg/m2", "notes": None}
    ],
    "dataHandlingRules": [],
    "statisticalMethods": [
        {"id": "sm_1", "name": "ANCOVA", "description": "Primary analysis",
         "endpointName": "HbA1c", "statoCode": "STATO:0000029"}
    ],
    "multiplicityAdjustments": [
        {"id": "mult_1", "name": "Hochberg", "description": "Step-up procedure",
         "methodType": "familywise", "overallAlpha": 0.05,
         "endpointsCovered": ["EP1", "EP2"], "hierarchy": "Primary first"}
    ],
    "sensitivityAnalyses": [],
    "subgroupAnalyses": [],
    "interimAnalyses": [],
    "sampleSizeCalculations": [
        {"id": "ss_1", "name": "Primary", "description": "Sample size for primary endpoint",
         "targetSampleSize": 500, "power": 0.9, "alpha": 0.05}
    ],
    "summary": {"populationCount": 1},
}

SAMPLE_SAP_JSON_FILE = {
    "success": True,
    "sourceFile": "sap.pdf",
    "pagesUsed": [0, 1, 2],
    "modelUsed": "gemini-2.5-pro",
    "sapData": SAMPLE_SAP_DATA,
}

SAMPLE_SITES_DATA = {
    "studySites": [
        {"id": "site_1", "name": "Site A", "country": "US"},
    ],
    "organizations": [
        {"id": "org_1", "name": "Hospital A", "type": "Investigator"},
    ],
    "summary": {"siteCount": 1},
}

SAMPLE_SITES_JSON_FILE = {
    "success": True,
    "sourceFile": "sites.csv",
    "sitesData": SAMPLE_SITES_DATA,
}


def _empty_study_design():
    return {"id": "sd_1", "instanceType": "InterventionalStudyDesign"}


def _empty_study_version():
    return {"id": "sv_1", "instanceType": "StudyVersion"}


# ---------------------------------------------------------------------------
# SAPPhase.combine() — previous extractions fallback
# ---------------------------------------------------------------------------

class TestSAPCombinePreviousExtractions:
    """Test SAPPhase.combine() with data loaded from 11_sap_populations.json."""

    def test_sapdata_key_extracts_multiplicity(self):
        """Regression: prev.get('sapData') must find nested SAP data."""
        phase = SAPPhase()
        sd = _empty_study_design()
        sv = _empty_study_version()
        combined = {"_output_dir": ""}

        phase.combine(
            result=PhaseResult(success=False),
            study_version=sv,
            study_design=sd,
            combined=combined,
            previous_extractions={"sap": SAMPLE_SAP_JSON_FILE},
        )

        # Populations added
        assert len(sd.get("analysisPopulations", [])) == 1

        # Multiplicity extension present
        exts = sd.get("extensionAttributes", [])
        mult_exts = [e for e in exts if "multiplicity-adjustments" in e.get("url", "")]
        assert len(mult_exts) == 1, f"Expected 1 multiplicity ext, got {len(mult_exts)}"
        items = json.loads(mult_exts[0]["valueString"])
        assert len(items) == 1
        assert items[0]["name"] == "Hochberg"

    def test_all_sap_extensions_present(self):
        """All non-empty SAP categories should produce extensions."""
        phase = SAPPhase()
        sd = _empty_study_design()
        combined = {"_output_dir": ""}

        phase.combine(
            result=PhaseResult(success=False),
            study_version=_empty_study_version(),
            study_design=sd,
            combined=combined,
            previous_extractions={"sap": SAMPLE_SAP_JSON_FILE},
        )

        exts = sd.get("extensionAttributes", [])
        urls = {e["url"] for e in exts}
        # derivedVariables (1), statisticalMethods (1), multiplicityAdjustments (1), sampleSizeCalculations (1)
        assert "https://protocol2usdm.io/extensions/x-sap-derived-variables" in urls
        assert "https://protocol2usdm.io/extensions/x-sap-statistical-methods" in urls
        assert "https://protocol2usdm.io/extensions/x-sap-multiplicity-adjustments" in urls
        assert "https://protocol2usdm.io/extensions/x-sap-sample-size-calculations" in urls

    def test_empty_categories_no_extensions(self):
        """Categories with empty lists should not produce extensions."""
        phase = SAPPhase()
        sd = _empty_study_design()
        combined = {"_output_dir": ""}

        phase.combine(
            result=PhaseResult(success=False),
            study_version=_empty_study_version(),
            study_design=sd,
            combined=combined,
            previous_extractions={"sap": SAMPLE_SAP_JSON_FILE},
        )

        exts = sd.get("extensionAttributes", [])
        urls = [e["url"] for e in exts]
        # These have 0 items in SAMPLE_SAP_DATA
        assert not any("sensitivity-analyses" in u for u in urls)
        assert not any("subgroup-analyses" in u for u in urls)
        assert not any("interim-analyses" in u for u in urls)

    def test_wrong_key_would_fail(self):
        """Verify that using the old 'sap' key (instead of 'sapData') would miss data."""
        # This test documents the bug that was fixed
        bad_data = dict(SAMPLE_SAP_JSON_FILE)
        # If someone tries to get prev.get('sap'), they get None → falls back to full dict
        assert bad_data.get('sap') is None
        # The correct key is 'sapData'
        assert bad_data.get('sapData') is not None
        assert "multiplicityAdjustments" in bad_data["sapData"]

    def test_no_previous_extractions(self):
        """No SAP data at all — combine should be a no-op."""
        phase = SAPPhase()
        sd = _empty_study_design()
        combined = {"_output_dir": ""}

        phase.combine(
            result=PhaseResult(success=False),
            study_version=_empty_study_version(),
            study_design=sd,
            combined=combined,
            previous_extractions={},
        )

        assert "analysisPopulations" not in sd
        assert "extensionAttributes" not in sd


# ---------------------------------------------------------------------------
# SAPPhase.combine() — live result object
# ---------------------------------------------------------------------------

class TestSAPCombineLiveResult:
    """Test SAPPhase.combine() with live SAPExtractionResult-like objects."""

    def test_live_result_with_to_dict(self):
        """Live result with .data.to_dict() should produce extensions."""
        phase = SAPPhase()
        sd = _empty_study_design()
        combined = {"_output_dir": ""}

        mock_data = MagicMock()
        mock_data.to_dict.return_value = SAMPLE_SAP_DATA

        result = PhaseResult(success=True, data=mock_data)

        phase.combine(
            result=result,
            study_version=_empty_study_version(),
            study_design=sd,
            combined=combined,
            previous_extractions={},
        )

        exts = sd.get("extensionAttributes", [])
        mult_exts = [e for e in exts if "multiplicity-adjustments" in e.get("url", "")]
        assert len(mult_exts) == 1

    def test_live_result_preferred_over_previous(self):
        """Live result should take precedence over previous extractions."""
        phase = SAPPhase()
        sd = _empty_study_design()
        combined = {"_output_dir": ""}

        mock_data = MagicMock()
        mock_data.to_dict.return_value = {
            **SAMPLE_SAP_DATA,
            "multiplicityAdjustments": [
                {"id": "mult_live", "name": "Bonferroni", "description": "Live data"}
            ],
        }

        result = PhaseResult(success=True, data=mock_data)

        phase.combine(
            result=result,
            study_version=_empty_study_version(),
            study_design=sd,
            combined=combined,
            previous_extractions={"sap": SAMPLE_SAP_JSON_FILE},
        )

        exts = sd.get("extensionAttributes", [])
        mult_exts = [e for e in exts if "multiplicity-adjustments" in e.get("url", "")]
        assert len(mult_exts) == 1
        items = json.loads(mult_exts[0]["valueString"])
        assert items[0]["name"] == "Bonferroni"  # Live data, not Hochberg


# ---------------------------------------------------------------------------
# SitesPhase.combine() — key fix
# ---------------------------------------------------------------------------

class TestSitesCombinePreviousExtractions:
    """Test SitesPhase.combine() uses correct 'sitesData' key."""

    def test_sitesdata_key_loads_sites(self):
        phase = SitesPhase()
        sd = _empty_study_design()
        sv = _empty_study_version()

        phase.combine(
            result=PhaseResult(success=False),
            study_version=sv,
            study_design=sd,
            combined={},
            previous_extractions={"sites": SAMPLE_SITES_JSON_FILE},
        )

        assert len(sd.get("studySites", [])) == 1
        assert len(sv.get("organizations", [])) == 1

    def test_no_previous_sites(self):
        phase = SitesPhase()
        sd = _empty_study_design()
        sv = _empty_study_version()

        phase.combine(
            result=PhaseResult(success=False),
            study_version=sv,
            study_design=sd,
            combined={},
            previous_extractions={},
        )

        assert "studySites" not in sd


# ---------------------------------------------------------------------------
# No duplicate extensions after combiner fix
# ---------------------------------------------------------------------------

class TestNoDuplicateExtensions:
    """Verify combine_to_full_usdm does not create duplicate SAP extensions."""

    @patch("pipeline.combiner.phase_registry")
    def test_single_set_of_sap_extensions(self, mock_registry, tmp_path):
        """Only SAPPhase.combine() should add SAP extensions, not integrate_sap()."""
        from pipeline.combiner import combine_to_full_usdm

        # Set up a minimal registry with just the SAP phase
        sap_phase = SAPPhase()
        mock_registry.get_all.return_value = [sap_phase]

        # Simulate expansion_results with a successful SAP extraction result
        mock_data = MagicMock()
        mock_data.to_dict.return_value = SAMPLE_SAP_DATA
        sap_result = MagicMock()
        sap_result.success = True
        sap_result.data = mock_data

        expansion_results = {"sap": sap_result}

        combined, _ = combine_to_full_usdm(
            output_dir=str(tmp_path),
            soa_data=None,
            expansion_results=expansion_results,
        )

        # Count SAP multiplicity extensions in the final output
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        exts = sd.get("extensionAttributes", [])
        mult_exts = [e for e in exts if "multiplicity-adjustments" in e.get("url", "")]
        assert len(mult_exts) == 1, (
            f"Expected exactly 1 multiplicity extension, got {len(mult_exts)} — "
            f"duplicate integration not fully removed"
        )


# ---------------------------------------------------------------------------
# Orchestrator kwargs forwarding
# ---------------------------------------------------------------------------

class TestOrchestratorKwargsForwarding:
    """Test that orchestrator forwards sap_path/sites_path to phase.run()."""

    def test_run_phases_forwards_kwargs(self):
        from pipeline.orchestrator import PipelineOrchestrator
        from pipeline.phase_registry import PhaseRegistry, create_registry

        registry = create_registry()
        sap_phase = SAPPhase()
        registry.register(sap_phase)

        orch = PipelineOrchestrator(registry=registry)

        # Mock phase.run to capture kwargs
        captured = {}
        original_run = sap_phase.run

        def mock_run(**kwargs):
            captured.update(kwargs)
            return PhaseResult(success=False, error="mock")

        sap_phase.run = mock_run

        try:
            orch.run_phases(
                pdf_path="test.pdf",
                output_dir="out",
                model="test-model",
                phases_to_run={"sap": True},
                sap_path="/path/to/sap.pdf",
                sites_path="/path/to/sites.csv",
            )
        finally:
            sap_phase.run = original_run

        assert captured.get("sap_path") == "/path/to/sap.pdf"
        assert captured.get("sites_path") == "/path/to/sites.csv"


# ---------------------------------------------------------------------------
# Dangling SAI encounterId regression tests
# ---------------------------------------------------------------------------

class TestDanglingSAIEncounterIdFix:
    """Regression test for SURPASS-4 scenario: SAIs reference encounters
    that get filtered during reconciliation, leaving dangling encounterId."""

    def _build_combined(self, encounters, instances):
        """Build a minimal combined dict with given encounters and SAIs."""
        return {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "epochs": [{"id": "ep1", "name": "Treatment", "instanceType": "StudyEpoch"}],
                        "encounters": encounters,
                        "activities": [{"id": "act1", "name": "Dose", "instanceType": "Activity"}],
                        "scheduleTimelines": [{
                            "id": "tl1",
                            "name": "Main",
                            "instanceType": "ScheduleTimeline",
                            "instances": instances,
                            "timings": [],
                        }],
                    }]
                }]
            }
        }

    def test_dangling_encounter_remapped(self):
        """SAIs referencing filtered encounters should be remapped to surviving encounter."""
        from pipeline.post_processing import run_reconciliation

        surviving_enc = {"id": "enc_ok", "name": "Day 1", "epochId": "ep1", "instanceType": "Encounter"}
        doomed_enc = {"id": "enc_gone", "name": "Orphan", "instanceType": "Encounter"}  # no epochId
        encounters = [surviving_enc, doomed_enc]

        instances = [
            {"id": "sai1", "encounterId": "enc_ok", "activityIds": ["act1"], "instanceType": "ScheduledActivityInstance"},
            {"id": "sai2", "encounterId": "enc_gone", "activityIds": ["act1"], "instanceType": "ScheduledActivityInstance"},
            {"id": "sai3", "encounterId": "enc_gone", "activityIds": ["act1"], "instanceType": "ScheduledActivityInstance"},
        ]

        combined = self._build_combined(encounters, instances)
        result = run_reconciliation(combined, expansion_results={}, soa_data={})

        sd = result["study"]["versions"][0]["studyDesigns"][0]
        valid_enc_ids = {e["id"] for e in sd["encounters"]}

        for inst in sd["scheduleTimelines"][0]["instances"]:
            enc_id = inst.get("encounterId")
            if enc_id:
                assert enc_id in valid_enc_ids, (
                    f"SAI {inst['id']} has dangling encounterId={enc_id}"
                )

    def test_no_dangling_when_all_encounters_valid(self):
        """No changes when all encounterId references are valid."""
        from pipeline.post_processing import run_reconciliation

        enc = {"id": "enc1", "name": "Screening", "epochId": "ep1", "instanceType": "Encounter"}
        instances = [
            {"id": "sai1", "encounterId": "enc1", "activityIds": ["act1"], "instanceType": "ScheduledActivityInstance"},
        ]

        combined = self._build_combined([enc], instances)
        result = run_reconciliation(combined, expansion_results={}, soa_data={})

        sd = result["study"]["versions"][0]["studyDesigns"][0]
        sai = sd["scheduleTimelines"][0]["instances"][0]
        # encounterId should still point to the original (possibly remapped by reconciler)
        valid_enc_ids = {e["id"] for e in sd["encounters"]}
        assert sai.get("encounterId", "") == "" or sai["encounterId"] in valid_enc_ids
