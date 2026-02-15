"""Regression tests for pipeline.post_processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.post_processing import filter_enrichment_epochs


def test_filter_enrichment_epochs_removes_cells_for_removed_epochs():
    combined = {
        "study": {
            "versions": [
                {
                    "studyDesigns": [
                        {
                            "epochs": [
                                {"id": "ep_screen", "name": "Screening"},
                                {"id": "ep_treat", "name": "Treatment"},
                                {"id": "ep_extra", "name": "Follow-up"},
                            ],
                            "studyCells": [
                                {"id": "cell_1", "epochId": "ep_screen", "armId": "arm_1"},
                                {"id": "cell_2", "epochId": "ep_treat", "armId": "arm_1"},
                                {"id": "cell_3", "epochId": "ep_extra", "armId": "arm_1"},
                            ],
                            "scheduleTimelines": [
                                {
                                    "instances": [
                                        {"id": "inst_1", "epochId": "ep_screen"},
                                        {"id": "inst_2", "epochId": "ep_extra"},
                                        {
                                            "id": "inst_anchor",
                                            "epochId": "ep_extra",
                                            "extensionAttributes": [
                                                {"url": "https://protocol2usdm.io/extensions/x-anchorClassification"}
                                            ],
                                        },
                                    ]
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    }

    soa_data = {
        "study": {
            "versions": [
                {
                    "studyDesigns": [
                        {
                            "epochs": [
                                {"id": "soa_ep_1", "name": "Screening"},
                                {"id": "soa_ep_2", "name": "Treatment"},
                            ]
                        }
                    ]
                }
            ]
        }
    }

    result = filter_enrichment_epochs(combined, soa_data)
    design = result["study"]["versions"][0]["studyDesigns"][0]

    # Removed epoch should be gone
    epoch_ids = {e["id"] for e in design["epochs"]}
    assert epoch_ids == {"ep_screen", "ep_treat"}

    # StudyCells should no longer contain dangling epoch references
    assert {c["id"] for c in design["studyCells"]} == {"cell_1", "cell_2"}

    # Non-anchor instance on removed epoch is dropped; anchor instance is retained and re-assigned
    instances = design["scheduleTimelines"][0]["instances"]
    instance_ids = {i["id"] for i in instances}
    assert "inst_2" not in instance_ids
    anchor = next(i for i in instances if i["id"] == "inst_anchor")
    assert anchor["epochId"] in {"ep_screen", "ep_treat"}
