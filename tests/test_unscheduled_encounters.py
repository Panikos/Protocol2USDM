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


class TestPromoteUnscheduledToDecisions:
    """Test Phase 2: UNS encounter → ScheduledDecisionInstance promotion."""

    def _make_combined(self, encounters, timeline_instances=None):
        return {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "encounters": encounters,
                        "scheduleTimelines": [{
                            "id": "tl1",
                            "name": "Main Timeline",
                            "instances": timeline_instances or [],
                        }],
                    }]
                }]
            }
        }

    def _tag_uns(self, enc):
        """Add x-encounterUnscheduled extension to an encounter dict."""
        if "extensionAttributes" not in enc:
            enc["extensionAttributes"] = []
        enc["extensionAttributes"].append({
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/x-encounterUnscheduled",
            "instanceType": "ExtensionAttribute",
            "valueBoolean": True,
        })
        return enc

    def test_promotes_uns_to_sdi(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
            self._tag_uns({"id": "enc2", "name": "UNS", "epochId": "ep1"}),
            {"id": "enc3", "name": "Visit 2", "epochId": "ep1"},
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        tl = result["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdis = [i for i in tl["instances"] if i["instanceType"] == "ScheduledDecisionInstance"]
        assert len(sdis) == 1

        sdi = sdis[0]
        assert sdi["id"] == "sdi-uns-enc2"
        assert sdi["epochId"] == "ep1"
        assert len(sdi["conditionAssignments"]) == 2

        # Branch 1 targets the UNS encounter
        ca_event = sdi["conditionAssignments"][0]
        assert ca_event["conditionTargetId"] == "enc2"

        # Branch 2 (default) targets next scheduled encounter
        ca_default = sdi["conditionAssignments"][1]
        assert ca_default["conditionTargetId"] == "enc3"

        # defaultConditionId points to next scheduled encounter
        assert sdi["defaultConditionId"] == "enc3"

    def test_creates_condition_on_version(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            self._tag_uns({"id": "enc1", "name": "Unscheduled Visit", "epochId": "ep1"}),
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        conditions = result["study"]["versions"][0].get("conditions", [])
        assert len(conditions) == 1
        assert conditions[0]["id"] == "cond-uns-enc1"
        assert conditions[0]["instanceType"] == "Condition"
        assert "Unscheduled Visit" in conditions[0]["text"]

    def test_sdi_has_uns_extension(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            self._tag_uns({"id": "enc1", "name": "UNS", "epochId": "ep1"}),
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        tl = result["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdi = tl["instances"][0]
        ext = [e for e in sdi.get("extensionAttributes", [])
               if "unsDecisionInstance" in e.get("url", "")]
        assert len(ext) == 1
        assert ext[0]["valueString"] == "enc1"

    def test_does_not_double_promote(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            self._tag_uns({"id": "enc1", "name": "UNS", "epochId": "ep1"}),
        ]
        combined = self._make_combined(encounters)
        combined = promote_unscheduled_to_decisions(combined)
        combined = promote_unscheduled_to_decisions(combined)  # Run twice

        tl = combined["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdis = [i for i in tl["instances"] if i["instanceType"] == "ScheduledDecisionInstance"]
        assert len(sdis) == 1  # Should not create a duplicate

    def test_skips_scheduled_encounters(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
            {"id": "enc2", "name": "Visit 2", "epochId": "ep1"},
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        tl = result["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdis = [i for i in tl["instances"] if i["instanceType"] == "ScheduledDecisionInstance"]
        assert len(sdis) == 0

    def test_multiple_uns_encounters(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
            self._tag_uns({"id": "enc2", "name": "UNS 1", "epochId": "ep1"}),
            self._tag_uns({"id": "enc3", "name": "UNS 2", "epochId": "ep2"}),
            {"id": "enc4", "name": "Visit 3", "epochId": "ep2"},
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        tl = result["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdis = [i for i in tl["instances"] if i["instanceType"] == "ScheduledDecisionInstance"]
        assert len(sdis) == 2

        # First UNS → default branch should skip UNS 2 and land on Visit 3
        sdi1 = next(s for s in sdis if s["id"] == "sdi-uns-enc2")
        assert sdi1["defaultConditionId"] == "enc4"

    def test_uns_last_in_list_backward_walk(self):
        """When UNS is the last encounter, default branch should walk backward
        to find the preceding non-UNS encounter."""
        from pipeline.post_processing import promote_unscheduled_to_decisions

        encounters = [
            {"id": "enc1", "name": "Visit 1", "epochId": "ep1"},
            {"id": "enc2", "name": "Visit 2", "epochId": "ep1"},
            {"id": "enc3", "name": "EOS", "epochId": "ep2"},
            self._tag_uns({"id": "enc4", "name": "Unscheduled Visit", "epochId": "ep3"}),
        ]
        combined = self._make_combined(encounters)
        result = promote_unscheduled_to_decisions(combined)

        tl = result["study"]["versions"][0]["studyDesigns"][0]["scheduleTimelines"][0]
        sdis = [i for i in tl["instances"] if i["instanceType"] == "ScheduledDecisionInstance"]
        assert len(sdis) == 1

        sdi = sdis[0]
        # Default branch should point to enc3 (EOS), NOT enc4 (UNS itself)
        assert sdi["defaultConditionId"] == "enc3"
        ca_default = next(
            ca for ca in sdi["conditionAssignments"]
            if ca["condition"] == "No unscheduled event"
        )
        assert ca_default["conditionTargetId"] == "enc3"
        # Event branch should point to enc4 (the UNS encounter)
        ca_event = next(
            ca for ca in sdi["conditionAssignments"]
            if ca["condition"] != "No unscheduled event"
        )
        assert ca_event["conditionTargetId"] == "enc4"

    def test_no_timelines_graceful(self):
        from pipeline.post_processing import promote_unscheduled_to_decisions

        combined = {
            "study": {
                "versions": [{
                    "studyDesigns": [{
                        "encounters": [
                            self._tag_uns({"id": "enc1", "name": "UNS", "epochId": "ep1"}),
                        ],
                        "scheduleTimelines": [],
                    }]
                }]
            }
        }
        # Should not crash
        result = promote_unscheduled_to_decisions(combined)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
