"""
Tests for unscheduled encounter detection and tagging.
"""
import pytest
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.reconciliation.encounter_reconciler import (
    is_unscheduled_encounter,
    EncounterReconciler,
    reconcile_encounters_from_pipeline,
)
from pipeline.post_processing import tag_unscheduled_encounters


class TestIsUnscheduledEncounter:
    """Test the name-based unscheduled visit detection."""

    @pytest.mark.parametrize("name", [
        "UNS",
        "Unscheduled",
        "Unscheduled Visit",
        "UNSCHEDULED VISIT",
        "Visit UNS",
        "UNS Visit",
        "Unplanned Visit",
        "Ad Hoc Visit",
        "Ad hoc",
        "PRN Visit",
        "As Needed",
        "Event-Driven Visit",
        "Event Driven",
    ])
    def test_detects_unscheduled(self, name):
        assert is_unscheduled_encounter(name), f"Expected '{name}' to be detected as unscheduled"

    @pytest.mark.parametrize("name", [
        "Visit 1",
        "Screening",
        "Baseline",
        "Day 1",
        "Week 4",
        "End of Study",
        "Early Termination",
        "Follow-Up Visit",
        "Randomization",
    ])
    def test_does_not_detect_scheduled(self, name):
        assert not is_unscheduled_encounter(name), f"Expected '{name}' to NOT be detected as unscheduled"


class TestEncounterReconcilerUnscheduled:
    """Test that the reconciler propagates the unscheduled flag."""

    def test_unscheduled_from_name(self):
        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
            {"id": "enc2", "name": "UNS", "epochId": "ep1"},
        ]
        reconciler = EncounterReconciler(match_threshold=1.0)
        reconciler.contribute("soa", encounters, priority=10)
        reconciled = reconciler.reconcile()

        by_name = {e.name: e for e in reconciled}
        assert not by_name["Visit 1"].is_unscheduled
        assert by_name["UNS"].is_unscheduled

    def test_unscheduled_from_explicit_flag(self):
        encounters = [
            {"id": "enc1", "name": "Special Visit", "epochId": "ep1", "isUnscheduled": True},
        ]
        reconciler = EncounterReconciler(match_threshold=1.0)
        reconciler.contribute("soa", encounters, priority=10)
        reconciled = reconciler.reconcile()

        assert reconciled[0].is_unscheduled

    def test_unscheduled_extension_in_usdm_dict(self):
        encounters = [
            {"id": "enc1", "name": "Unscheduled Visit", "epochId": "ep1"},
        ]
        reconciler = EncounterReconciler(match_threshold=1.0)
        reconciler.contribute("soa", encounters, priority=10)
        reconciled = reconciler.reconcile()

        usdm = reconciled[0].to_usdm_dict()
        exts = usdm.get("extensionAttributes", [])
        uns_ext = [e for e in exts if "encounterUnscheduled" in e.get("url", "")]
        assert len(uns_ext) == 1
        assert uns_ext[0]["valueBoolean"] is True

    def test_scheduled_no_extension(self):
        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
        ]
        reconciler = EncounterReconciler(match_threshold=1.0)
        reconciler.contribute("soa", encounters, priority=10)
        reconciled = reconciler.reconcile()

        usdm = reconciled[0].to_usdm_dict()
        exts = usdm.get("extensionAttributes", [])
        uns_ext = [e for e in exts if "encounterUnscheduled" in e.get("url", "")]
        assert len(uns_ext) == 0


class TestTagUnscheduledEncounters:
    """Test the post-processing safety net."""

    def _make_combined(self, encounters):
        return {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "encounters": encounters,
                    }]
                }]
            }
        }

    def test_tags_uns_encounter(self):
        combined = self._make_combined([
            {"name": "Visit 1"},
            {"name": "UNS"},
        ])
        result = tag_unscheduled_encounters(combined)
        encounters = result["study"]["versions"][0]["studyDesigns"][0]["encounters"]

        # Visit 1 should not be tagged
        assert not any(
            "encounterUnscheduled" in e.get("url", "")
            for e in encounters[0].get("extensionAttributes", [])
        )

        # UNS should be tagged
        uns_exts = [
            e for e in encounters[1].get("extensionAttributes", [])
            if "encounterUnscheduled" in e.get("url", "")
        ]
        assert len(uns_exts) == 1
        assert uns_exts[0]["valueBoolean"] is True

    def test_does_not_double_tag(self):
        combined = self._make_combined([
            {
                "name": "UNS",
                "extensionAttributes": [{
                    "id": str(uuid.uuid4()),
                    "url": "https://protocol2usdm.io/extensions/x-encounterUnscheduled",
                    "instanceType": "ExtensionAttribute",
                    "valueBoolean": True,
                }],
            },
        ])
        result = tag_unscheduled_encounters(combined)
        encounters = result["study"]["versions"][0]["studyDesigns"][0]["encounters"]

        uns_exts = [
            e for e in encounters[0].get("extensionAttributes", [])
            if "encounterUnscheduled" in e.get("url", "")
        ]
        assert len(uns_exts) == 1  # Should not add a second one


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
