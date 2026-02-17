"""Tests for the regression gate entity count comparison."""
import json
import os
import tempfile

import pytest

from pipeline.regression_gate import (
    check_regression,
    count_entities,
    count_key_entities,
    load_entity_stats,
    save_entity_stats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_USDM = {
    "study": {
        "versions": [{
            "studyDesigns": [{
                "epochs": [
                    {"id": "e1", "name": "Screening", "instanceType": "StudyEpoch"},
                    {"id": "e2", "name": "Treatment", "instanceType": "StudyEpoch"},
                ],
                "encounters": [
                    {"id": "enc1", "name": "V1", "instanceType": "Encounter"},
                ],
                "activities": [
                    {"id": "a1", "name": "Vital Signs", "instanceType": "Activity"},
                    {"id": "a2", "name": "ECG", "instanceType": "Activity"},
                    {"id": "a3", "name": "Labs", "instanceType": "Activity"},
                ],
                "arms": [],
                "studyCells": [],
                "objectives": [
                    {"id": "o1", "instanceType": "Objective"},
                ],
                "endpoints": [],
                "estimands": [],
                "indications": [],
                "analysisPopulations": [],
                "population": {"criteria": [{"id": "c1"}, {"id": "c2"}]},
                "scheduleTimelines": [
                    {"instances": [{"id": "i1"}], "timings": [{"id": "t1"}]},
                ],
                "instanceType": "StudyDesign",
            }],
            "studyInterventions": [{"id": "si1", "instanceType": "StudyIntervention"}],
            "amendments": [],
            "narrativeContentItems": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
            "abbreviations": [],
            "instanceType": "StudyVersion",
        }],
        "instanceType": "Study",
    }
}


# ---------------------------------------------------------------------------
# Tests: count_entities
# ---------------------------------------------------------------------------

class TestCountEntities:
    def test_counts_by_instance_type(self):
        counts = count_entities(MINIMAL_USDM)
        assert counts["StudyEpoch"] == 2
        assert counts["Activity"] == 3
        assert counts["Encounter"] == 1
        assert counts["Study"] == 1

    def test_empty_data(self):
        counts = count_entities({})
        assert counts == {}


# ---------------------------------------------------------------------------
# Tests: count_key_entities
# ---------------------------------------------------------------------------

class TestCountKeyEntities:
    def test_counts_structural_paths(self):
        counts = count_key_entities(MINIMAL_USDM)
        assert counts["epochs"] == 2
        assert counts["encounters"] == 1
        assert counts["activities"] == 3
        assert counts["objectives"] == 1
        assert counts["eligibilityCriteria"] == 2
        assert counts["scheduledInstances"] == 1
        assert counts["timings"] == 1
        assert counts["narrativeContentItems"] == 3

    def test_empty_data(self):
        counts = count_key_entities({})
        assert isinstance(counts, dict)


# ---------------------------------------------------------------------------
# Tests: save / load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_round_trip(self, tmp_path):
        stats = save_entity_stats(MINIMAL_USDM, str(tmp_path))
        loaded = load_entity_stats(str(tmp_path))
        assert loaded is not None
        assert loaded["keyEntities"]["epochs"] == 2
        assert loaded["keyEntities"]["activities"] == 3

    def test_load_missing(self, tmp_path):
        assert load_entity_stats(str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Tests: check_regression
# ---------------------------------------------------------------------------

class TestCheckRegression:
    def _write_baseline(self, dir_path, key_entities):
        stats = {"keyEntities": key_entities, "byInstanceType": {}, "totalByType": 0}
        with open(os.path.join(dir_path, "entity_stats.json"), "w") as f:
            json.dump(stats, f)

    def test_no_regression(self, tmp_path):
        baseline_dir = str(tmp_path / "baseline")
        os.makedirs(baseline_dir)
        self._write_baseline(baseline_dir, {"epochs": 2, "activities": 3})
        current = {"keyEntities": {"epochs": 2, "activities": 3}}
        warnings = check_regression(current, baseline_dir)
        assert warnings == []

    def test_detects_drop(self, tmp_path):
        baseline_dir = str(tmp_path / "baseline")
        os.makedirs(baseline_dir)
        self._write_baseline(baseline_dir, {"epochs": 10, "activities": 20})
        current = {"keyEntities": {"epochs": 5, "activities": 20}}
        warnings = check_regression(current, baseline_dir, threshold=0.8)
        assert len(warnings) == 1
        assert warnings[0]["entity"] == "epochs"
        assert warnings[0]["severity"] == "warning"

    def test_critical_drop(self, tmp_path):
        baseline_dir = str(tmp_path / "baseline")
        os.makedirs(baseline_dir)
        self._write_baseline(baseline_dir, {"epochs": 10, "activities": 20})
        current = {"keyEntities": {"epochs": 2, "activities": 20}}
        warnings = check_regression(current, baseline_dir, threshold=0.8)
        assert len(warnings) == 1
        assert warnings[0]["severity"] == "critical"

    def test_no_baseline(self, tmp_path):
        current = {"keyEntities": {"epochs": 2}}
        warnings = check_regression(current, str(tmp_path))
        assert warnings == []

    def test_zero_baseline_skipped(self, tmp_path):
        baseline_dir = str(tmp_path / "baseline")
        os.makedirs(baseline_dir)
        self._write_baseline(baseline_dir, {"epochs": 0, "activities": 5})
        current = {"keyEntities": {"epochs": 0, "activities": 5}}
        warnings = check_regression(current, baseline_dir)
        assert warnings == []
