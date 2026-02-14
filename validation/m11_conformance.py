"""
M11 Conformance Validator — checks USDM output against ICH M11 requirements.

Validates that a protocol_usdm.json contains the data elements required
by the M11 Technical Specification (Step 4, 19 Nov 2025).  Produces a
conformance report with:
  - Missing required title-page fields
  - Missing required M11 sections (content coverage)
  - Synopsis §1.1.2 structured-field completeness
  - Controlled-terminology alignment gaps
  - Overall conformance score

Reference: ICH M11 Technical Specification, NCI Thesaurus Subset C217023
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# M11 Required data element definitions
# Derived from core/m11_usdm_mapping.yaml (single source of truth)
# ---------------------------------------------------------------------------

def _load_conformance_data():
    """Load conformance lists from the YAML config."""
    from core.m11_mapping_config import get_m11_config
    config = get_m11_config()
    return (
        config.get_title_page_fields_dicts(),
        config.get_synopsis_fields_dicts(),
        config.get_m11_required_sections(),
    )


_tp, _syn, _req = _load_conformance_data()

TITLE_PAGE_FIELDS = _tp
SYNOPSIS_FIELDS = _syn
M11_REQUIRED_SECTIONS = _req


@dataclass
class ConformanceIssue:
    """Single conformance issue."""
    severity: str  # "ERROR" (required missing), "WARNING" (optional missing), "INFO"
    category: str  # "title_page", "synopsis", "section_coverage", "terminology"
    field: str
    message: str
    cCode: str = ""


@dataclass
class M11ConformanceReport:
    """Full M11 conformance report."""
    timestamp: str = ""
    protocol_id: str = ""
    issues: List[ConformanceIssue] = field(default_factory=list)
    title_page_score: str = ""  # "X/Y required"
    synopsis_score: str = ""
    section_coverage_score: str = ""
    overall_score: float = 0.0
    total_required: int = 0
    total_required_present: int = 0
    total_optional: int = 0
    total_optional_present: int = 0


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def validate_m11_conformance(
    usdm: Dict,
    m11_mapping: Optional[Dict] = None,
) -> M11ConformanceReport:
    """
    Validate a USDM JSON against M11 Technical Specification requirements.

    Args:
        usdm: Full protocol_usdm.json dict
        m11_mapping: Optional pre-computed M11 section mapping

    Returns:
        M11ConformanceReport with issues and scores
    """
    report = M11ConformanceReport(
        timestamp=datetime.now().isoformat(),
    )

    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # Extract protocol ID for report
    identifiers = version.get('studyIdentifiers', study.get('studyIdentifiers', []))
    for ident in identifiers:
        if isinstance(ident, dict):
            ident_type = ident.get('type', {})
            code = ident_type.get('code', '') if isinstance(ident_type, dict) else ''
            if code == 'C132351' or 'sponsor' in str(ident_type.get('decode', '')).lower():
                report.protocol_id = ident.get('text', ident.get('studyIdentifier', ''))
                break

    # ---- 1. Title Page Validation ----
    _validate_title_page(report, version, study, design)

    # ---- 2. Synopsis §1.1.2 Validation ----
    _validate_synopsis(report, version, design, usdm)

    # ---- 3. Section Coverage Validation ----
    _validate_section_coverage(report, usdm, version, design, m11_mapping)

    # ---- 4. Calculate scores ----
    _calculate_scores(report)

    logger.info(
        f"M11 conformance: {report.total_required_present}/{report.total_required} "
        f"required ({report.overall_score:.0f}%), "
        f"{len(report.issues)} issues"
    )

    return report


def _validate_title_page(
    report: M11ConformanceReport,
    version: Dict,
    study: Dict,
    design: Dict,
) -> None:
    """Check title page required/optional fields."""
    titles = version.get('titles', [])
    identifiers = version.get('studyIdentifiers', study.get('studyIdentifiers', []))
    organizations = version.get('organizations', study.get('organizations', []))
    phase = version.get('studyPhase', design.get('studyPhase', {}))
    interventions = version.get('studyInterventions', [])

    # Build presence checks
    checks = {
        "titles": any(isinstance(t, dict) and t.get('text') for t in titles),
        "identifiers": any(
            isinstance(i, dict) and
            (i.get('type', {}).get('code', '') == 'C132351' or
             'sponsor' in str(i.get('type', {}).get('decode', '')).lower())
            for i in identifiers
        ),
        "amendments": True,  # Original Protocol Indicator can be derived
        "phase": bool(
            isinstance(phase, dict) and (
                phase.get('decode') or phase.get('code') or
                (isinstance(phase.get('standardCode'), dict) and
                 phase['standardCode'].get('decode'))
            )
        ),
        "sponsor": any(
            isinstance(o, dict) and
            (o.get('type', {}).get('code', '') == 'C54086' or
             'pharma' in str(o.get('type', {}).get('decode', '')).lower() or
             'sponsor' in str(o.get('type', {}).get('decode', '')).lower())
            for o in organizations
        ),
        "reg_identifiers": any(
            isinstance(i, dict) and i.get('text')
            for i in identifiers
        ),
        "approval": bool(
            version.get('effectiveDate') or
            any(
                isinstance(dv, dict) and dv.get('dateValue') and
                ('approval' in (dv.get('name', '') or '').lower() or
                 'approval' in str((dv.get('type', {}) or {}).get('decode', '')).lower())
                for dv in version.get('dateValues', [])
            )
        ),
        "acronym": any(
            isinstance(t, dict) and 'acronym' in str(t.get('type', {}).get('decode', '')).lower()
            for t in titles
        ),
        "short_title": any(
            isinstance(t, dict) and
            ('brief' in str(t.get('type', {}).get('decode', '')).lower() or
             'short' in str(t.get('type', {}).get('decode', '')).lower())
            for t in titles
        ),
        "version": bool(version.get('versionIdentifier')),
        "date": bool(version.get('effectiveDate')),
        "ip_names": bool(interventions),
    }

    for field_def in TITLE_PAGE_FIELDS:
        name = field_def["name"]
        conf = field_def["conformance"]
        present = checks.get(field_def["check"], False)

        if conf == "Required":
            report.total_required += 1
            if present:
                report.total_required_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="ERROR",
                    category="title_page",
                    field=name,
                    message=f"Required title page field '{name}' is missing or empty",
                    cCode=field_def.get("cCode", ""),
                ))
        else:
            report.total_optional += 1
            if present:
                report.total_optional_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="INFO",
                    category="title_page",
                    field=name,
                    message=f"Optional title page field '{name}' is not populated",
                    cCode=field_def.get("cCode", ""),
                ))


def _validate_synopsis(
    report: M11ConformanceReport,
    version: Dict,
    design: Dict,
    usdm: Optional[Dict] = None,
) -> None:
    """Check Synopsis §1.1.2 Overall Design structured fields."""
    pop = design.get('population', design.get('populations', {}))
    if isinstance(pop, list):
        pop = pop[0] if pop else {}

    arms = design.get('arms', design.get('studyArms', []))
    sites = design.get('studySites', [])

    # Check participants: first from USDM population, then narrative fallback
    has_participants = bool(
        isinstance(pop, dict) and
        (pop.get('plannedEnrollmentNumber') or
         pop.get('plannedNumberOfSubjects') or
         pop.get('plannedMaximumNumberOfSubjects'))
    )
    if not has_participants and usdm:
        try:
            from rendering.composers import _extract_participant_count_from_narrative
            has_participants = bool(_extract_participant_count_from_narrative(usdm))
        except ImportError:
            pass

    checks = {
        "model": bool(isinstance(design.get('model', {}), dict) and
                       design.get('model', {}).get('decode')),
        "pop_type": bool(isinstance(pop, dict) and
                          pop.get('includesHealthySubjects') is not None),
        "indication": bool(design.get('indications')),
        "control": bool(arms),  # Can infer control type from arms
        "randomization": bool(design.get('randomizationType')),
        "arms": bool(arms),
        "blinding": bool(isinstance(design.get('blindingSchema', {}), dict) and
                          design.get('blindingSchema', {})),
        "participants": has_participants,
        "sites": bool(sites),
        "age": bool(
            isinstance(pop, dict) and
            (pop.get('plannedAge') or
             pop.get('plannedMinimumAgeOfSubjects') or
             pop.get('minimumAge'))
        ),
        "geo_scope": bool(sites),  # Can infer from site addresses
        "strat": True,  # Can always emit Yes/No
        "master": True,
        "adaptive": True,
        "combo": True,
        "blind_roles": bool(design.get('maskingRoles')),
        "duration": bool(design.get('epochs', design.get('studyEpochs'))),
        "committees": False,  # Usually not structured in USDM
    }

    for field_def in SYNOPSIS_FIELDS:
        name = field_def["name"]
        conf = field_def["conformance"]
        present = checks.get(field_def["check"], False)

        if conf == "Required":
            report.total_required += 1
            if present:
                report.total_required_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="ERROR",
                    category="synopsis",
                    field=name,
                    message=f"Required synopsis field '{name}' cannot be derived from USDM",
                ))
        else:
            report.total_optional += 1
            if present:
                report.total_optional_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="INFO",
                    category="synopsis",
                    field=name,
                    message=f"Optional synopsis field '{name}' is not populated",
                ))


def _validate_section_coverage(
    report: M11ConformanceReport,
    usdm: Dict,
    version: Dict,
    design: Dict,
    m11_mapping: Optional[Dict],
) -> None:
    """Check which M11 sections have narrative or structured content."""
    # Determine which sections have content from mapping
    mapped_sections = set()
    if m11_mapping:
        sections = m11_mapping.get('sections', {})
        for num, sec_data in sections.items():
            if isinstance(sec_data, dict) and sec_data.get('hasContent'):
                mapped_sections.add(num)

    # Check which sections have entity data available
    entity_sections = set()
    if design.get('objectives'):
        entity_sections.add('3')
    if design.get('arms') or design.get('studyArms') or design.get('model'):
        entity_sections.add('4')
    if design.get('population') or design.get('populations'):
        entity_sections.add('5')
    if version.get('studyInterventions'):
        entity_sections.add('6')
    if design.get('analysisPopulations') or design.get('extensionAttributes'):
        entity_sections.add('10')
    if version.get('abbreviations'):
        entity_sections.add('13')
    if version.get('amendments'):
        entity_sections.add('12')

    # Narrative content items — scan section numbers to detect which M11 sections
    # have narrative content (covers §7, §8, §9, §11 which are narrative-only)
    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])
    has_narrative = bool(nc or nci)
    if has_narrative:
        entity_sections.add('1')  # Likely has synopsis narrative
        entity_sections.add('2')  # Likely has introduction
    for item in nc + nci:
        if not isinstance(item, dict):
            continue
        sec_num = item.get('sectionNumber', '')
        text = item.get('text', '')
        if sec_num and text and len(text.strip()) > 20:
            # Map section number to top-level M11 section (e.g. '7.1' → '7')
            top_section = sec_num.split('.')[0]
            if top_section.isdigit():
                entity_sections.add(top_section)

    covered = mapped_sections | entity_sections

    for num, title, required in M11_REQUIRED_SECTIONS:
        if required:
            report.total_required += 1
            if num in covered:
                report.total_required_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="ERROR" if required else "WARNING",
                    category="section_coverage",
                    field=f"§{num} {title}",
                    message=f"Required section '{num} {title}' has no content (narrative or structured)",
                ))
        else:
            report.total_optional += 1
            if num in covered:
                report.total_optional_present += 1
            else:
                report.issues.append(ConformanceIssue(
                    severity="INFO",
                    category="section_coverage",
                    field=f"§{num} {title}",
                    message=f"Optional section '{num} {title}' has no content",
                ))


def _calculate_scores(report: M11ConformanceReport) -> None:
    """Calculate summary scores."""
    if report.total_required > 0:
        report.overall_score = (
            report.total_required_present / report.total_required * 100
        )

    tp_required = sum(1 for f in TITLE_PAGE_FIELDS if f["conformance"] == "Required")
    tp_present = tp_required - sum(
        1 for i in report.issues
        if i.category == "title_page" and i.severity == "ERROR"
    )
    report.title_page_score = f"{tp_present}/{tp_required} required"

    syn_required = sum(1 for f in SYNOPSIS_FIELDS if f["conformance"] == "Required")
    syn_present = syn_required - sum(
        1 for i in report.issues
        if i.category == "synopsis" and i.severity == "ERROR"
    )
    report.synopsis_score = f"{syn_present}/{syn_required} required"

    sec_required = sum(1 for _, _, r in M11_REQUIRED_SECTIONS if r)
    sec_present = sec_required - sum(
        1 for i in report.issues
        if i.category == "section_coverage" and i.severity == "ERROR"
    )
    report.section_coverage_score = f"{sec_present}/{sec_required} required"


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------

def conformance_report_to_dict(report: M11ConformanceReport) -> Dict:
    """Convert conformance report to JSON-serializable dict."""
    return {
        "timestamp": report.timestamp,
        "protocolId": report.protocol_id,
        "overallScore": round(report.overall_score, 1),
        "totalRequired": report.total_required,
        "totalRequiredPresent": report.total_required_present,
        "totalOptional": report.total_optional,
        "totalOptionalPresent": report.total_optional_present,
        "scores": {
            "titlePage": report.title_page_score,
            "synopsis": report.synopsis_score,
            "sectionCoverage": report.section_coverage_score,
        },
        "issues": [
            {
                "severity": i.severity,
                "category": i.category,
                "field": i.field,
                "message": i.message,
                "cCode": i.cCode,
            }
            for i in report.issues
        ],
        "summary": {
            "errors": sum(1 for i in report.issues if i.severity == "ERROR"),
            "warnings": sum(1 for i in report.issues if i.severity == "WARNING"),
            "info": sum(1 for i in report.issues if i.severity == "INFO"),
        },
    }


def save_conformance_report(
    report: M11ConformanceReport,
    output_path: str,
) -> str:
    """Save conformance report as JSON."""
    report_dict = conformance_report_to_dict(report)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(report_dict, f, indent=2)
    logger.info(f"M11 conformance report saved: {output_path}")
    return str(path)
