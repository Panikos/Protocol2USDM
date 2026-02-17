"""Tests for P3–P7 reviewer fix functions in pipeline.post_processing."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.post_processing import (
    ensure_eos_study_cell,
    nest_sites_in_organizations,
    wire_document_layer,
    nest_cohorts_in_population,
    promote_footnotes_to_conditions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_combined(extras: dict | None = None) -> dict:
    """Return a minimal valid combined dict."""
    combined = {
        "study": {
            "versions": [
                {
                    "studyDesigns": [
                        {
                            "arms": [{"id": "arm_1", "name": "Treatment"}],
                            "epochs": [
                                {"id": "ep_screen", "name": "Screening"},
                                {"id": "ep_treat", "name": "Treatment"},
                            ],
                            "studyCells": [
                                {"id": "cell_1", "armId": "arm_1", "epochId": "ep_screen"},
                                {"id": "cell_2", "armId": "arm_1", "epochId": "ep_treat"},
                            ],
                            "elements": [],
                            "activities": [],
                            "encounters": [],
                            "population": {
                                "id": "pop_1",
                                "name": "Study Population",
                                "includesHealthySubjects": False,
                                "instanceType": "StudyDesignPopulation",
                            },
                            "extensionAttributes": [],
                        }
                    ],
                    "organizations": [],
                    "conditions": [],
                    "narrativeContentItems": [],
                }
            ],
        }
    }
    if extras:
        combined.update(extras)
    return combined


# ===========================================================================
# P6: ensure_eos_study_cell
# ===========================================================================

class TestP6EnsureEosStudyCell:
    def test_creates_cell_for_uncovered_epoch(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["epochs"].append({"id": "ep_eos", "name": "End of Study"})
        # ep_eos has no cell

        result = ensure_eos_study_cell(combined)
        sd = result["study"]["versions"][0]["studyDesigns"][0]
        epoch_ids_in_cells = {c["epochId"] for c in sd["studyCells"]}
        assert "ep_eos" in epoch_ids_in_cells

    def test_does_not_duplicate_existing_cells(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        original_count = len(sd["studyCells"])

        result = ensure_eos_study_cell(combined)
        sd = result["study"]["versions"][0]["studyDesigns"][0]
        assert len(sd["studyCells"]) == original_count

    def test_creates_element_for_new_cell(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["epochs"].append({"id": "ep_fu", "name": "Follow-up"})

        result = ensure_eos_study_cell(combined)
        sd = result["study"]["versions"][0]["studyDesigns"][0]
        elem_ids = {e["id"] for e in sd["elements"]}
        assert "elem_followup_ep_fu" in elem_ids

    def test_noop_when_no_arms(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["arms"] = []
        sd["epochs"].append({"id": "ep_x", "name": "X"})

        result = ensure_eos_study_cell(combined)
        sd = result["study"]["versions"][0]["studyDesigns"][0]
        assert len(sd["studyCells"]) == 2  # unchanged

    def test_multiple_uncovered_epochs(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["epochs"].extend([
            {"id": "ep_eos", "name": "End of Study"},
            {"id": "ep_et", "name": "Early Termination"},
        ])

        result = ensure_eos_study_cell(combined)
        sd = result["study"]["versions"][0]["studyDesigns"][0]
        epoch_ids_in_cells = {c["epochId"] for c in sd["studyCells"]}
        assert "ep_eos" in epoch_ids_in_cells
        assert "ep_et" in epoch_ids_in_cells


# ===========================================================================
# P3: nest_sites_in_organizations
# ===========================================================================

class TestP3NestSites:
    def test_nests_site_into_matching_org(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["organizations"] = [
            {"id": "org_1", "name": "Site Alpha Hospital"}
        ]
        sd = sv["studyDesigns"][0]
        sd["studySites"] = [
            {"id": "site_1", "name": "Site Alpha Hospital", "country": "US"}
        ]

        result = nest_sites_in_organizations(combined)
        org = result["study"]["versions"][0]["organizations"][0]
        assert len(org.get("managedSites", [])) == 1
        assert org["managedSites"][0]["id"] == "site_1"

    def test_no_sites_is_noop(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["organizations"] = [{"id": "org_1", "name": "Sponsor"}]

        result = nest_sites_in_organizations(combined)
        org = result["study"]["versions"][0]["organizations"][0]
        assert "managedSites" not in org

    def test_unmatched_sites_fall_back_to_site_type_org(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["organizations"] = [
            {"id": "org_1", "name": "Sponsor Corp"},
            {
                "id": "org_site",
                "name": "Site Network",
                "type": {"code": "C188724", "decode": "Clinical Study Site"},
            },
        ]
        sd = sv["studyDesigns"][0]
        sd["studySites"] = [
            {"id": "site_1", "name": "Totally Different Name", "country": "US"}
        ]

        result = nest_sites_in_organizations(combined)
        site_org = next(
            o for o in result["study"]["versions"][0]["organizations"]
            if o["id"] == "org_site"
        )
        assert len(site_org.get("managedSites", [])) == 1

    def test_no_duplicate_nesting(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["organizations"] = [
            {"id": "org_1", "name": "Hospital A", "managedSites": [
                {"id": "site_1", "name": "Hospital A"}
            ]}
        ]
        sd = sv["studyDesigns"][0]
        sd["studySites"] = [{"id": "site_1", "name": "Hospital A", "country": "US"}]

        result = nest_sites_in_organizations(combined)
        org = result["study"]["versions"][0]["organizations"][0]
        assert len(org["managedSites"]) == 1


# ===========================================================================
# P5: wire_document_layer
# ===========================================================================

class TestP5WireDocumentLayer:
    def test_creates_documented_by_from_narrative_items(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["narrativeContentItems"] = [
            {"id": "nci_1", "name": "Section 1", "sectionNumber": "1", "text": "Intro"},
            {"id": "nci_2", "name": "Section 2", "sectionNumber": "2", "text": "Methods"},
        ]

        result = wire_document_layer(combined)
        doc = result["study"].get("documentedBy")
        assert doc is not None
        assert doc["instanceType"] == "StudyDefinitionDocument"
        versions = doc.get("versions", [])
        assert len(versions) == 1
        contents = versions[0].get("contents", [])
        assert len(contents) == 2

    def test_noop_when_no_narrative_items(self):
        combined = _base_combined()
        result = wire_document_layer(combined)
        assert "documentedBy" not in result["study"]

    def test_uses_existing_sdd(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["narrativeContentItems"] = [
            {"id": "nci_1", "name": "S1", "sectionNumber": "1", "text": "T"}
        ]
        combined["studyDefinitionDocument"] = {
            "id": "sdd_existing",
            "name": "My Protocol",
            "instanceType": "StudyDefinitionDocument",
        }

        result = wire_document_layer(combined)
        doc = result["study"]["documentedBy"]
        assert doc["id"] == "sdd_existing"
        assert "studyDefinitionDocument" not in result


# ===========================================================================
# P4: nest_cohorts_in_population
# ===========================================================================

class TestP4NestCohorts:
    def test_nests_cohorts_into_population(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["studyCohorts"] = [
            {"id": "coh_1", "name": "Treatment-Naive"},
            {"id": "coh_2", "name": "Treatment-Experienced"},
        ]

        result = nest_cohorts_in_population(combined)
        pop = result["study"]["versions"][0]["studyDesigns"][0]["population"]
        assert len(pop.get("cohorts", [])) == 2
        assert pop["cohorts"][0]["instanceType"] == "StudyCohort"

    def test_noop_when_no_cohorts(self):
        combined = _base_combined()
        result = nest_cohorts_in_population(combined)
        pop = result["study"]["versions"][0]["studyDesigns"][0]["population"]
        assert "cohorts" not in pop or len(pop.get("cohorts", [])) == 0

    def test_no_duplicate_cohorts(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["studyCohorts"] = [{"id": "coh_1", "name": "Group A"}]
        sd["population"]["cohorts"] = [{"id": "coh_1", "name": "Group A"}]

        result = nest_cohorts_in_population(combined)
        pop = result["study"]["versions"][0]["studyDesigns"][0]["population"]
        assert len(pop["cohorts"]) == 1

    def test_sets_required_fields(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["studyCohorts"] = [{"id": "coh_1", "name": "Group A"}]

        result = nest_cohorts_in_population(combined)
        cohort = result["study"]["versions"][0]["studyDesigns"][0]["population"]["cohorts"][0]
        assert cohort["includesHealthySubjects"] is False
        assert cohort["instanceType"] == "StudyCohort"


# ===========================================================================
# P7: promote_footnotes_to_conditions
# ===========================================================================

class TestP7FootnotesToConditions:
    def test_promotes_conditional_footnotes(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["extensionAttributes"] = [{
            "url": "https://protocol2usdm.io/extensions/x-soaFootnotes",
            "valueString": json.dumps([
                {"id": "fn_1", "text": "At screening only", "marker": "a"},
                {"id": "fn_2", "text": "Standard lab panel description", "marker": "b"},
            ]),
        }]

        result = promote_footnotes_to_conditions(combined)
        conditions = result["study"]["versions"][0]["conditions"]
        # Only "At screening only" should be promoted (contains "only")
        promoted = [c for c in conditions if c["id"].startswith("cond_fn_")]
        assert len(promoted) == 1
        assert "screening" in promoted[0]["text"].lower()

    def test_skips_non_conditional_footnotes(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["extensionAttributes"] = [{
            "url": "https://protocol2usdm.io/extensions/x-soaFootnotes",
            "valueString": json.dumps([
                {"id": "fn_1", "text": "Blood draw volumes are approximate", "marker": "a"},
            ]),
        }]

        result = promote_footnotes_to_conditions(combined)
        conditions = result["study"]["versions"][0]["conditions"]
        promoted = [c for c in conditions if c["id"].startswith("cond_fn_")]
        assert len(promoted) == 0

    def test_no_duplicate_conditions(self):
        combined = _base_combined()
        sv = combined["study"]["versions"][0]
        sv["conditions"] = [{"id": "c1", "text": "For female participants only"}]
        sd = sv["studyDesigns"][0]
        sd["extensionAttributes"] = [{
            "url": "https://protocol2usdm.io/extensions/x-soaFootnotes",
            "valueString": json.dumps([
                {"id": "fn_1", "text": "For female participants only", "marker": "a"},
            ]),
        }]

        result = promote_footnotes_to_conditions(combined)
        conditions = result["study"]["versions"][0]["conditions"]
        assert len(conditions) == 1

    def test_noop_when_no_footnotes(self):
        combined = _base_combined()
        result = promote_footnotes_to_conditions(combined)
        conditions = result["study"]["versions"][0]["conditions"]
        assert len(conditions) == 0

    def test_links_context_encounters(self):
        combined = _base_combined()
        sd = combined["study"]["versions"][0]["studyDesigns"][0]
        sd["encounters"] = [
            {"id": "enc_1", "name": "Screening"},
            {"id": "enc_2", "name": "Day 1"},
        ]
        sd["extensionAttributes"] = [{
            "url": "https://protocol2usdm.io/extensions/x-soaFootnotes",
            "valueString": json.dumps([
                {"id": "fn_1", "text": "At screening only", "marker": "a"},
            ]),
        }]

        result = promote_footnotes_to_conditions(combined)
        conditions = result["study"]["versions"][0]["conditions"]
        promoted = [c for c in conditions if c["id"].startswith("cond_fn_")]
        assert len(promoted) == 1
        assert "enc_1" in promoted[0]["contextIds"]
