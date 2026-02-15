"""
M11 Golden-Protocol Regression Tests

Validates M11 document generation across multiple real protocol outputs.
Ensures that:
  1. Renderer produces valid DOCX without errors for every protocol
  2. All 14 M11 sections are rendered
  3. Conformance score meets minimum threshold
  4. Key entity composers produce non-empty output
  5. Section mapping achieves minimum coverage

Usage:
    python -m pytest tests/test_m11_regression.py -v
    python tests/test_m11_regression.py  # standalone
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Discover golden protocols — latest run per unique NCT/protocol ID
# ---------------------------------------------------------------------------

OUTPUT_DIR = PROJECT_ROOT / "output"
MIN_CONFORMANCE_SCORE = 70.0  # Minimum acceptable conformance %
MIN_SECTIONS_WITH_CONTENT = 8  # At least 8/14 sections should have content
MIN_WORD_COUNT = 5000  # Minimum words in generated document


def discover_golden_protocols(max_count: int = 10) -> list:
    """Find the latest output run for each unique protocol.
    
    Currently restricted to Wilson's protocol (NCT04573309) which has
    full narrative extraction.  Other protocols can be added once they
    are re-run with the narrative phase enabled.
    """
    if not OUTPUT_DIR.exists():
        return []

    # Group by protocol prefix (e.g. NCT04573309_Wilsons_Protocol)
    protocol_groups: dict = {}
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir():
            continue
        # Skip test directories
        if d.name.startswith('test_'):
            continue
        # Only include Wilson's protocol for now
        if 'Wilsons' not in d.name and 'NCT04573309' not in d.name:
            continue
        usdm_path = d / "protocol_usdm.json"
        if not usdm_path.exists():
            continue
        # Extract protocol prefix (everything before the timestamp)
        name = d.name
        parts = name.rsplit("_", 2)
        if len(parts) >= 3 and len(parts[-1]) == 6 and len(parts[-2]) == 8:
            prefix = "_".join(parts[:-2])
        else:
            prefix = name
        protocol_groups[prefix] = str(usdm_path)

    # Return up to max_count protocols
    protocols = list(protocol_groups.items())[-max_count:]
    return protocols


def _require_golden_protocols(max_count: int) -> list:
    """Discover golden protocols or skip when local artifacts are unavailable."""
    protocols = discover_golden_protocols(max_count=max_count)
    if not protocols:
        pytest.skip("No golden protocols found in output/ (run pipeline on golden protocol first)")
    return protocols


def run_m11_generation(usdm_path: str) -> dict:
    """Run M11 generation for a single protocol and return results."""
    from rendering.m11_renderer import render_m11_docx
    from validation.m11_conformance import validate_m11_conformance, conformance_report_to_dict

    with open(usdm_path, 'r') as f:
        usdm = json.load(f)

    # Generate DOCX to a temp file
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        output_path = tmp.name

    try:
        result = render_m11_docx(usdm, output_path)
        conf_report = validate_m11_conformance(usdm)
        conf_dict = conformance_report_to_dict(conf_report)

        return {
            "success": result.success,
            "error": result.error,
            "sections_rendered": result.sections_rendered,
            "sections_with_content": result.sections_with_content,
            "total_words": result.total_words,
            "conformance_score": conf_report.overall_score,
            "conformance_errors": sum(1 for i in conf_report.issues if i.severity == "ERROR"),
            "conformance_report": conf_dict,
            "output_path": output_path,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sections_rendered": 0,
            "sections_with_content": 0,
            "total_words": 0,
            "conformance_score": 0,
            "conformance_errors": -1,
            "conformance_report": {},
            "output_path": output_path,
        }
    finally:
        # Cleanup temp file
        try:
            os.unlink(output_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test functions (pytest-compatible)
# ---------------------------------------------------------------------------

def test_m11_all_protocols():
    """Test M11 generation across all golden protocols."""
    protocols = _require_golden_protocols(max_count=10)

    results = []
    failures = []

    for prefix, usdm_path in protocols:
        logger.info(f"Testing: {prefix}")
        r = run_m11_generation(usdm_path)
        results.append((prefix, r))

        # Check assertions
        issues = []
        if not r["success"]:
            issues.append(f"Render failed: {r['error']}")
        if r["sections_rendered"] != 14:
            issues.append(f"Expected 14 sections, got {r['sections_rendered']}")
        if r["sections_with_content"] < MIN_SECTIONS_WITH_CONTENT:
            issues.append(f"Only {r['sections_with_content']} sections with content (min {MIN_SECTIONS_WITH_CONTENT})")
        if r["total_words"] < MIN_WORD_COUNT:
            issues.append(f"Only {r['total_words']} words (min {MIN_WORD_COUNT})")
        if r["conformance_score"] < MIN_CONFORMANCE_SCORE:
            issues.append(f"Conformance {r['conformance_score']:.1f}% < {MIN_CONFORMANCE_SCORE}%")

        if issues:
            failures.append((prefix, issues))

    # Print summary
    print("\n" + "=" * 80)
    print("M11 REGRESSION TEST RESULTS")
    print("=" * 80)

    for prefix, r in results:
        status = "PASS" if not any(prefix == f[0] for f in failures) else "FAIL"
        print(f"  [{status}] {prefix[:55]:55s} "
              f"sec={r['sections_with_content']:2d}/14 "
              f"words={r['total_words']:6d} "
              f"conf={r['conformance_score']:5.1f}% "
              f"err={r['conformance_errors']}")

    print(f"\n  Total: {len(results)} protocols, "
          f"{len(results) - len(failures)} passed, "
          f"{len(failures)} failed")

    if failures:
        print("\n  FAILURES:")
        for prefix, issues in failures:
            print(f"    {prefix}:")
            for issue in issues:
                print(f"      - {issue}")

    assert len(failures) == 0, f"{len(failures)} protocols failed M11 regression"


def test_m11_entity_composers():
    """Test that entity composers produce output for at least one protocol."""
    from rendering.m11_renderer import (
        _compose_synopsis, _compose_objectives, _compose_study_design,
        _compose_eligibility, _compose_interventions, _compose_discontinuation,
        _compose_safety, _compose_statistics, _compose_estimands,
    )

    protocols = _require_golden_protocols(max_count=3)

    composers = {
        "synopsis": _compose_synopsis,
        "objectives": _compose_objectives,
        "study_design": _compose_study_design,
        "eligibility": _compose_eligibility,
        "interventions": _compose_interventions,
        "discontinuation": _compose_discontinuation,
        "safety": _compose_safety,
        "statistics": _compose_statistics,
        "estimands": _compose_estimands,
    }

    # Track which composers produced output across any protocol
    produced_output = {name: False for name in composers}

    for prefix, usdm_path in protocols:
        with open(usdm_path, 'r') as f:
            usdm = json.load(f)
        for name, fn in composers.items():
            try:
                result = fn(usdm)
                if result and result.strip():
                    produced_output[name] = True
            except Exception as e:
                logger.warning(f"Composer {name} failed on {prefix}: {e}")

    print("\n" + "=" * 80)
    print("ENTITY COMPOSER RESULTS")
    print("=" * 80)
    for name, produced in produced_output.items():
        status = "OK" if produced else "EMPTY"
        print(f"  [{status:5s}] {name}")

    # At least synopsis, objectives, and study_design should produce output
    critical = ["synopsis", "objectives", "study_design"]
    for name in critical:
        assert produced_output[name], f"Critical composer '{name}' produced no output"


def test_m11_section_mapping_coverage():
    """Test that section mapping achieves good coverage."""
    from extraction.narrative.m11_mapper import map_sections_to_m11

    protocols = _require_golden_protocols(max_count=5)

    for prefix, usdm_path in protocols:
        with open(usdm_path, 'r') as f:
            usdm = json.load(f)

        v = usdm.get('study', {}).get('versions', [{}])[0]
        nc = v.get('narrativeContents', [])
        nci = v.get('narrativeContentItems', [])

        sec_dicts = []
        sec_texts = {}
        seen = set()
        for item in nc + nci:
            if not isinstance(item, dict):
                continue
            num = item.get('sectionNumber', '')
            if not num or num in seen:
                continue
            seen.add(num)
            title = item.get('sectionTitle', item.get('name', ''))
            text = item.get('text', '')
            sec_type = ''
            st = item.get('sectionType', {})
            if isinstance(st, dict):
                sec_type = st.get('decode', st.get('code', ''))
            sec_dicts.append({'number': num, 'title': title, 'type': sec_type})
            if text and text != title:
                sec_texts[num] = text

        if not sec_dicts:
            continue

        mapping = map_sections_to_m11(sec_dicts, section_texts=sec_texts)

        # At least 50% of M11 sections should be covered
        assert mapping.m11_covered >= 7, (
            f"{prefix}: Only {mapping.m11_covered}/14 M11 sections covered"
        )
        # Less than 30% of protocol sections should be unmapped
        total = len(sec_dicts)
        unmapped_pct = len(mapping.unmapped) / max(1, total) * 100
        assert unmapped_pct < 30, (
            f"{prefix}: {unmapped_pct:.0f}% unmapped ({len(mapping.unmapped)}/{total})"
        )


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Running M11 regression tests...\n")

    try:
        test_m11_entity_composers()
        print("\n✓ Entity composer test passed\n")
    except (AssertionError, Exception) as e:
        print(f"\n✗ Entity composer test failed: {e}\n")

    try:
        test_m11_section_mapping_coverage()
        print("\n✓ Section mapping coverage test passed\n")
    except (AssertionError, Exception) as e:
        print(f"\n✗ Section mapping coverage test failed: {e}\n")

    try:
        test_m11_all_protocols()
        print("\n✓ All-protocols regression test passed\n")
    except (AssertionError, Exception) as e:
        print(f"\n✗ All-protocols regression test failed: {e}\n")
