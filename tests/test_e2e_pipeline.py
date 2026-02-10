"""
End-to-End Pipeline Integration Test

Runs the full extraction pipeline on a real protocol PDF and validates:
  1. Pipeline completes without fatal errors (exit code 0)
  2. protocol_usdm.json is produced with valid USDM structure
  3. Key USDM entities are present (study, arms, epochs, objectives, etc.)
  4. M11 DOCX is generated with content
  5. Run manifest and validation artifacts are produced

This test requires:
  - An LLM API key configured in .env (GOOGLE_API_KEY or OPENAI_API_KEY)
  - The Wilson's protocol PDF at input/trial/NCT04573309_Wilsons/

Usage:
    # Run with pytest (skipped by default unless --run-e2e is passed)
    python -m pytest tests/test_e2e_pipeline.py -v --run-e2e

    # Run standalone (always runs)
    python tests/test_e2e_pipeline.py
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WILSON_PDF = PROJECT_ROOT / "input" / "trial" / "NCT04573309_Wilsons" / "NCT04573309_Wilsons_Protocol.pdf"
WILSON_SAP = PROJECT_ROOT / "input" / "trial" / "NCT04573309_Wilsons" / "NCT04573309_Wilsons_SAP.pdf"
WILSON_SITES = PROJECT_ROOT / "input" / "trial" / "NCT04573309_Wilsons" / "NCT04573309_Wilsons_sites.csv"

# Minimum thresholds for a valid extraction (conservative — any protocol should pass)
MIN_ARMS = 1
MIN_EPOCHS = 2
MIN_OBJECTIVES = 1
MIN_ELIGIBILITY_CRITERIA = 5
MIN_NARRATIVE_ITEMS = 5
MIN_ACTIVITIES = 3
MIN_ENCOUNTERS = 3
MIN_M11_SECTIONS = 14
MIN_M11_WORDS = 3000
MIN_M11_CONTENT_SECTIONS = 6

PIPELINE_TIMEOUT = 900  # 15 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_latest_output(protocol_prefix: str = "NCT04573309_Wilsons_Protocol") -> Optional[Path]:
    """Find the latest output directory for a protocol."""
    output_dir = PROJECT_ROOT / "output"
    if not output_dir.exists():
        return None
    candidates = sorted(
        [d for d in output_dir.iterdir()
         if d.is_dir() and d.name.startswith(protocol_prefix)
         and (d / "protocol_usdm.json").exists()],
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def _load_usdm(output_dir: Path) -> Dict:
    """Load protocol_usdm.json from an output directory."""
    usdm_path = output_dir / "protocol_usdm.json"
    with open(usdm_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_design(usdm: Dict) -> Dict:
    """Navigate to studyDesigns[0]."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    designs = version.get('studyDesigns', [{}])
    return designs[0] if designs else {}


def _get_version(usdm: Dict) -> Dict:
    """Navigate to study.versions[0]."""
    return (usdm.get('study', {}).get('versions', [{}]) or [{}])[0]


def _run_pipeline(output_dir: str) -> int:
    """Run the full pipeline and return exit code."""
    cmd = [
        sys.executable, str(PROJECT_ROOT / "main_v3.py"),
        str(WILSON_PDF),
        "--complete", "--parallel",
        "--output-dir", output_dir,
    ]
    # Add SAP/sites if available
    if WILSON_SAP.exists():
        cmd.extend(["--sap", str(WILSON_SAP)])
    if WILSON_SITES.exists():
        cmd.extend(["--sites", str(WILSON_SITES)])

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=PIPELINE_TIMEOUT,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout[-2000:]}")
        print(f"STDERR:\n{result.stderr[-2000:]}")
    return result.returncode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline_output_dir():
    """Get or create a pipeline output directory.

    If a recent Wilson's output exists (< 1 hour old), reuse it.
    Otherwise, run the full pipeline.
    """
    import time

    # Check for recent output
    max_age = float(os.environ.get("E2E_MAX_AGE_HOURS", "1"))
    latest = _find_latest_output()
    if latest:
        usdm_path = latest / "protocol_usdm.json"
        age_hours = (time.time() - usdm_path.stat().st_mtime) / 3600
        if age_hours < max_age:
            logger.info(f"Reusing recent output: {latest.name} ({age_hours:.1f}h old)")
            return latest

    # Need to run the pipeline
    if not WILSON_PDF.exists():
        pytest.skip(f"Wilson's protocol PDF not found: {WILSON_PDF}")

    from dotenv import load_dotenv
    load_dotenv()
    has_key = any(os.environ.get(k) for k in [
        'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
    ])
    if not has_key:
        pytest.skip("No LLM API key found in environment")

    output_dir = str(PROJECT_ROOT / "output" / "e2e_test_run")
    exit_code = _run_pipeline(output_dir)
    assert exit_code == 0, f"Pipeline failed with exit code {exit_code}"
    return Path(output_dir)


@pytest.fixture(scope="module")
def usdm(pipeline_output_dir):
    """Load the USDM JSON from the pipeline output."""
    return _load_usdm(pipeline_output_dir)


# ---------------------------------------------------------------------------
# Tests: Pipeline Artifacts
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestPipelineArtifacts:
    """Verify that all expected output files are produced."""

    def test_protocol_usdm_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "protocol_usdm.json").exists()

    def test_provenance_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "protocol_usdm_provenance.json").exists()

    def test_m11_docx_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "m11_protocol.docx").exists()
        size = (pipeline_output_dir / "m11_protocol.docx").stat().st_size
        assert size > 10_000, f"M11 DOCX too small: {size} bytes"

    def test_run_manifest_exists(self, pipeline_output_dir):
        path = pipeline_output_dir / "run_manifest.json"
        assert path.exists()
        manifest = json.loads(path.read_text(encoding='utf-8'))
        assert "input" in manifest
        assert "phases" in manifest

    def test_schema_validation_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "schema_validation.json").exists()

    def test_m11_conformance_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "m11_conformance_report.json").exists()

    def test_soa_output_exists(self, pipeline_output_dir):
        assert (pipeline_output_dir / "9_final_soa.json").exists()


# ---------------------------------------------------------------------------
# Tests: USDM Structure
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestUSDMStructure:
    """Verify the USDM JSON has the correct top-level structure."""

    def test_has_study(self, usdm):
        assert 'study' in usdm
        assert 'id' in usdm['study']

    def test_has_versions(self, usdm):
        versions = usdm['study'].get('versions', [])
        assert len(versions) >= 1

    def test_has_study_designs(self, usdm):
        design = _get_design(usdm)
        assert design, "No studyDesigns found"
        assert 'id' in design

    def test_has_instance_type(self, usdm):
        design = _get_design(usdm)
        itype = design.get('instanceType', '')
        assert itype in ('InterventionalStudyDesign', 'ObservationalStudyDesign'), \
            f"Unexpected instanceType: {itype}"


# ---------------------------------------------------------------------------
# Tests: Entity Counts
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestEntityCounts:
    """Verify minimum entity counts for a valid extraction."""

    def test_arms(self, usdm):
        design = _get_design(usdm)
        arms = design.get('arms', design.get('studyArms', []))
        assert len(arms) >= MIN_ARMS, f"Only {len(arms)} arms (min {MIN_ARMS})"

    def test_epochs(self, usdm):
        design = _get_design(usdm)
        epochs = design.get('epochs', design.get('studyEpochs', []))
        assert len(epochs) >= MIN_EPOCHS, f"Only {len(epochs)} epochs (min {MIN_EPOCHS})"

    def test_objectives(self, usdm):
        design = _get_design(usdm)
        objectives = design.get('objectives', [])
        assert len(objectives) >= MIN_OBJECTIVES, \
            f"Only {len(objectives)} objectives (min {MIN_OBJECTIVES})"

    def test_eligibility_criteria(self, usdm):
        version = _get_version(usdm)
        items = version.get('eligibilityCriterionItems', [])
        assert len(items) >= MIN_ELIGIBILITY_CRITERIA, \
            f"Only {len(items)} eligibility criteria (min {MIN_ELIGIBILITY_CRITERIA})"

    def test_narrative_content(self, usdm):
        version = _get_version(usdm)
        nc = version.get('narrativeContentItems', [])
        assert len(nc) >= MIN_NARRATIVE_ITEMS, \
            f"Only {len(nc)} narrative items (min {MIN_NARRATIVE_ITEMS})"

    def test_activities(self, usdm):
        design = _get_design(usdm)
        activities = design.get('activities', [])
        assert len(activities) >= MIN_ACTIVITIES, \
            f"Only {len(activities)} activities (min {MIN_ACTIVITIES})"

    def test_encounters(self, usdm):
        design = _get_design(usdm)
        encounters = design.get('encounters', [])
        assert len(encounters) >= MIN_ENCOUNTERS, \
            f"Only {len(encounters)} encounters (min {MIN_ENCOUNTERS})"

    def test_schedule_timelines(self, usdm):
        design = _get_design(usdm)
        timelines = design.get('scheduleTimelines', [])
        assert len(timelines) >= 1, "No schedule timelines found"

    def test_study_interventions(self, usdm):
        version = _get_version(usdm)
        interventions = version.get('studyInterventions', [])
        assert len(interventions) >= 1, "No study interventions found"


# ---------------------------------------------------------------------------
# Tests: Entity Quality
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestEntityQuality:
    """Verify entity content quality beyond just counts."""

    def test_primary_objective_exists(self, usdm):
        design = _get_design(usdm)
        objectives = design.get('objectives', [])
        primary = [o for o in objectives if isinstance(o, dict)
                   and isinstance(o.get('level', o.get('objectiveLevel', {})), dict)
                   and 'primary' in o.get('level', o.get('objectiveLevel', {})).get('decode', '').lower()]
        assert len(primary) >= 1, "No primary objective found"

    def test_objectives_have_text(self, usdm):
        design = _get_design(usdm)
        objectives = design.get('objectives', [])
        with_text = [o for o in objectives if isinstance(o, dict)
                     and (o.get('text') or o.get('objectiveText', ''))]
        assert len(with_text) >= 1, "No objectives have text"

    def test_arms_have_names(self, usdm):
        design = _get_design(usdm)
        arms = design.get('arms', design.get('studyArms', []))
        named = [a for a in arms if isinstance(a, dict) and a.get('name')]
        assert len(named) == len(arms), \
            f"{len(arms) - len(named)} arms missing names"

    def test_epochs_have_names(self, usdm):
        design = _get_design(usdm)
        epochs = design.get('epochs', design.get('studyEpochs', []))
        named = [e for e in epochs if isinstance(e, dict) and e.get('name')]
        assert len(named) == len(epochs), \
            f"{len(epochs) - len(named)} epochs missing names"

    def test_population_exists(self, usdm):
        design = _get_design(usdm)
        pop = design.get('population', {})
        assert isinstance(pop, dict) and pop.get('id'), "No population found"

    def test_study_titles(self, usdm):
        version = _get_version(usdm)
        titles = version.get('titles', [])
        assert len(titles) >= 1, "No study titles found"

    def test_study_identifiers(self, usdm):
        version = _get_version(usdm)
        ids = version.get('studyIdentifiers', [])
        assert len(ids) >= 1, "No study identifiers found"

    def test_abbreviations_extracted(self, usdm):
        version = _get_version(usdm)
        abbrevs = version.get('abbreviations', [])
        assert len(abbrevs) >= 5, f"Only {len(abbrevs)} abbreviations (expected ≥5)"


# ---------------------------------------------------------------------------
# Tests: M11 DOCX Quality
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestM11Quality:
    """Verify M11 DOCX rendering quality."""

    def test_m11_conformance_score(self, pipeline_output_dir):
        path = pipeline_output_dir / "m11_conformance_report.json"
        if not path.exists():
            pytest.skip("No M11 conformance report")
        report = json.loads(path.read_text(encoding='utf-8'))
        score = report.get('overallScore', report.get('overall_score', 0))
        assert score >= 70, f"M11 conformance score {score}% < 70%"

    def test_m11_renders_all_sections(self, pipeline_output_dir, usdm):
        from rendering.m11_renderer import render_m11_docx
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = render_m11_docx(usdm, tmp_path)
            assert result.success, f"M11 render failed: {result.error}"
            assert result.sections_rendered >= MIN_M11_SECTIONS, \
                f"Only {result.sections_rendered} sections (min {MIN_M11_SECTIONS})"
            assert result.sections_with_content >= MIN_M11_CONTENT_SECTIONS, \
                f"Only {result.sections_with_content} sections with content (min {MIN_M11_CONTENT_SECTIONS})"
            assert result.total_words >= MIN_M11_WORDS, \
                f"Only {result.total_words} words (min {MIN_M11_WORDS})"
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Tests: Cross-Entity Integrity
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestCrossEntityIntegrity:
    """Verify referential integrity between USDM entities."""

    def test_study_cells_reference_valid_arms_and_epochs(self, usdm):
        design = _get_design(usdm)
        cells = design.get('studyCells', [])
        if not cells:
            pytest.skip("No study cells")
        arm_ids = {a['id'] for a in design.get('arms', []) if isinstance(a, dict) and 'id' in a}
        epoch_ids = {e['id'] for e in design.get('epochs', []) if isinstance(e, dict) and 'id' in e}
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            arm_id = cell.get('armId', '')
            epoch_id = cell.get('epochId', '')
            if arm_id:
                assert arm_id in arm_ids, f"Cell references unknown arm: {arm_id}"
            if epoch_id:
                assert epoch_id in epoch_ids, f"Cell references unknown epoch: {epoch_id}"

    def test_timeline_instances_reference_valid_encounters(self, usdm):
        design = _get_design(usdm)
        timelines = design.get('scheduleTimelines', [])
        if not timelines:
            pytest.skip("No schedule timelines")
        enc_ids = {e['id'] for e in design.get('encounters', [])
                   if isinstance(e, dict) and 'id' in e}
        timeline = timelines[0]
        instances = timeline.get('instances', [])
        dangling = 0
        for inst in instances:
            if isinstance(inst, dict):
                eid = inst.get('encounterId', '')
                if eid and eid not in enc_ids:
                    dangling += 1
        assert dangling == 0, f"{dangling} instances reference unknown encounters"

    def test_all_entities_have_ids(self, usdm):
        """Spot-check that key entity arrays have id fields."""
        design = _get_design(usdm)
        version = _get_version(usdm)
        collections = [
            ('arms', design.get('arms', [])),
            ('epochs', design.get('epochs', [])),
            ('activities', design.get('activities', [])),
            ('encounters', design.get('encounters', [])),
            ('objectives', design.get('objectives', [])),
        ]
        for name, items in collections:
            if not items:
                continue
            missing = sum(1 for i in items if isinstance(i, dict) and not i.get('id'))
            assert missing == 0, f"{missing} {name} missing 'id' field"


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Find latest output
    latest = _find_latest_output()
    if not latest:
        print("No Wilson's output found. Run the pipeline first:")
        print("  python main_v3.py input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_Protocol.pdf --complete --parallel")
        sys.exit(1)

    print(f"Using output: {latest.name}\n")
    usdm = _load_usdm(latest)
    design = _get_design(usdm)
    version = _get_version(usdm)

    # Run checks
    checks_passed = 0
    checks_failed = 0

    def check(name, condition, detail=""):
        global checks_passed, checks_failed
        if condition:
            print(f"  [PASS] {name}")
            checks_passed += 1
        else:
            print(f"  [FAIL] {name}: {detail}")
            checks_failed += 1

    print("=" * 70)
    print("E2E PIPELINE VALIDATION")
    print("=" * 70)

    # Artifacts
    print("\n--- Pipeline Artifacts ---")
    check("protocol_usdm.json", (latest / "protocol_usdm.json").exists())
    check("provenance", (latest / "protocol_usdm_provenance.json").exists())
    check("m11_protocol.docx", (latest / "m11_protocol.docx").exists())
    check("run_manifest.json", (latest / "run_manifest.json").exists())
    check("schema_validation.json", (latest / "schema_validation.json").exists())

    # Structure
    print("\n--- USDM Structure ---")
    check("study exists", 'study' in usdm)
    check("versions exist", len(usdm.get('study', {}).get('versions', [])) >= 1)
    check("studyDesigns exist", bool(design))

    # Entity counts
    print("\n--- Entity Counts ---")
    arms = design.get('arms', design.get('studyArms', []))
    epochs = design.get('epochs', design.get('studyEpochs', []))
    objectives = design.get('objectives', [])
    activities = design.get('activities', [])
    encounters = design.get('encounters', [])
    criteria = version.get('eligibilityCriterionItems', [])
    narrative = version.get('narrativeContentItems', [])
    interventions = version.get('studyInterventions', [])
    abbreviations = version.get('abbreviations', [])
    timelines = design.get('scheduleTimelines', [])

    check(f"arms: {len(arms)}", len(arms) >= MIN_ARMS, f"min {MIN_ARMS}")
    check(f"epochs: {len(epochs)}", len(epochs) >= MIN_EPOCHS, f"min {MIN_EPOCHS}")
    check(f"objectives: {len(objectives)}", len(objectives) >= MIN_OBJECTIVES, f"min {MIN_OBJECTIVES}")
    check(f"activities: {len(activities)}", len(activities) >= MIN_ACTIVITIES, f"min {MIN_ACTIVITIES}")
    check(f"encounters: {len(encounters)}", len(encounters) >= MIN_ENCOUNTERS, f"min {MIN_ENCOUNTERS}")
    check(f"eligibility: {len(criteria)}", len(criteria) >= MIN_ELIGIBILITY_CRITERIA, f"min {MIN_ELIGIBILITY_CRITERIA}")
    check(f"narrative items: {len(narrative)}", len(narrative) >= MIN_NARRATIVE_ITEMS, f"min {MIN_NARRATIVE_ITEMS}")
    check(f"interventions: {len(interventions)}", len(interventions) >= 1, "min 1")
    check(f"abbreviations: {len(abbreviations)}", len(abbreviations) >= 5, "min 5")
    check(f"timelines: {len(timelines)}", len(timelines) >= 1, "min 1")

    # M11
    print("\n--- M11 DOCX ---")
    try:
        from rendering.m11_renderer import render_m11_docx
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp_path = tmp.name
        result = render_m11_docx(usdm, tmp_path)
        os.unlink(tmp_path)
        check(f"render success", result.success, result.error or "")
        check(f"sections: {result.sections_rendered}", result.sections_rendered >= MIN_M11_SECTIONS, f"min {MIN_M11_SECTIONS}")
        check(f"with content: {result.sections_with_content}", result.sections_with_content >= MIN_M11_CONTENT_SECTIONS, f"min {MIN_M11_CONTENT_SECTIONS}")
        check(f"words: {result.total_words}", result.total_words >= MIN_M11_WORDS, f"min {MIN_M11_WORDS}")
    except Exception as e:
        check("M11 render", False, str(e))

    # Summary
    print(f"\n{'=' * 70}")
    total = checks_passed + checks_failed
    print(f"Results: {checks_passed}/{total} passed, {checks_failed} failed")
    print(f"{'=' * 70}")
    sys.exit(0 if checks_failed == 0 else 1)
