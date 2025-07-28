import os
import json
import tempfile
from p2u_constants import USDM_VERSION

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from soa_postprocess_consolidated import consolidate_and_fix_soa


def test_provenance_file_written(tmp_path):
    """The post-processor should write a paired *_provenance.json file even if the
    input contains no provenance metadata (empty dict written)."""
    # Arrange – create minimal input file
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.json"

    minimal = {
        "study": {
            "versions": [
                {
                    "timeline": {
                        "activities": [{"activityId": "ACT1"}],
                        "plannedTimepoints": [{"plannedTimepointId": "TP1"}],
                        "activityTimepoints": [
                            {"activityId": "ACT1", "plannedTimepointId": "TP1"}
                        ],
                    }
                }
            ]
        },
        "usdmVersion": USDM_VERSION,
    }
    input_path.write_text(json.dumps(minimal), encoding="utf-8")

    # Act
    consolidate_and_fix_soa(str(input_path), str(output_path))

    # Assert – main output exists
    assert output_path.exists()
    # The provenance file should be sibling with _provenance suffix
    prov_path = output_path.with_name(output_path.stem + "_provenance.json")
    assert prov_path.exists(), "Provenance file not written"
    # Should contain a JSON object (empty or not)
    prov_data = json.loads(prov_path.read_text(encoding="utf-8"))
    assert isinstance(prov_data, dict)
