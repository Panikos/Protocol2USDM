"""Referential Integrity Checker for USDM output.

Three-layer validation:
  Layer 1: Schema-driven ID integrity — all *Id/*Ids references resolve
  Layer 2: Orphan detection — entities created but never referenced
  Layer 3: Semantic rules — cross-phase consistency checks

Produces an integrity_report.json with findings at ERROR/WARNING/INFO severity.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class IntegrityFinding:
    """A single integrity check finding."""
    rule: str
    severity: Severity
    message: str
    entity_type: str = ''
    entity_ids: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            'rule': self.rule,
            'severity': self.severity.value,
            'message': self.message,
        }
        if self.entity_type:
            d['entityType'] = self.entity_type
        if self.entity_ids:
            d['entityIds'] = self.entity_ids
        if self.details:
            d['details'] = self.details
        return d


@dataclass
class IntegrityReport:
    """Full integrity report."""
    findings: List[IntegrityFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    def to_dict(self) -> dict:
        return {
            'summary': {
                'totalFindings': len(self.findings),
                'errors': self.error_count,
                'warnings': self.warning_count,
                'info': self.info_count,
            },
            'findings': [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Layer 1: Schema-driven ID reference validation
# ---------------------------------------------------------------------------

# Known reference fields in USDM v4.0 output:
# Format: (json_path_pattern, ref_field, target_collection_path, target_entity_type)
# json_path_pattern: dot-separated path to the collection containing the ref field
# ref_field: the field name that holds the reference ID(s)
# target_collection_path: where to find the target entities
# is_array: whether the field holds an array of IDs

REFERENCE_RULES: List[Tuple[str, str, str, str, bool]] = [
    # StudyCell references
    ('studyDesigns.0.studyCells', 'armId', 'studyDesigns.0.arms', 'StudyArm', False),
    ('studyDesigns.0.studyCells', 'epochId', 'studyDesigns.0.epochs', 'StudyEpoch', False),
    ('studyDesigns.0.studyCells', 'elementIds', 'studyDesigns.0.elements', 'StudyElement', True),
    # ScheduledActivityInstance references
    ('studyDesigns.0.scheduleTimelines.0.instances', 'encounterId', 'studyDesigns.0.encounters', 'Encounter', False),
    ('studyDesigns.0.scheduleTimelines.0.instances', 'epochId', 'studyDesigns.0.epochs', 'StudyEpoch', False),
    ('studyDesigns.0.scheduleTimelines.0.instances', 'activityIds', 'studyDesigns.0.activities', 'Activity', True),
    ('studyDesigns.0.scheduleTimelines.0.instances', 'timingId', 'studyDesigns.0.scheduleTimelines.0.timings', 'Timing', False),
    # Estimand references
    ('studyDesigns.0.estimands', 'analysisPopulationId', 'studyDesigns.0.analysisPopulations', 'AnalysisPopulation', False),
    ('studyDesigns.0.estimands', 'interventionIds', 'studyInterventions', 'StudyIntervention', True),
    # Epoch chain
    ('studyDesigns.0.epochs', 'previousId', 'studyDesigns.0.epochs', 'StudyEpoch', False),
    ('studyDesigns.0.epochs', 'nextId', 'studyDesigns.0.epochs', 'StudyEpoch', False),
    # Encounter chain
    ('studyDesigns.0.encounters', 'previousId', 'studyDesigns.0.encounters', 'Encounter', False),
    ('studyDesigns.0.encounters', 'nextId', 'studyDesigns.0.encounters', 'Encounter', False),
    # NarrativeContent chain
    ('documentedBy.versions.0.contents', 'previousId', 'documentedBy.versions.0.contents', 'NarrativeContent', False),
    ('documentedBy.versions.0.contents', 'nextId', 'documentedBy.versions.0.contents', 'NarrativeContent', False),
    # Activity definedProcedures
    ('studyDesigns.0.activities', 'definedProcedures.*.procedureId', 'studyDesigns.0.procedures', 'Procedure', False),
]


def _resolve_path(obj: Any, path: str) -> Any:
    """Navigate a dot-separated path through nested dicts/lists."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if current is None:
            return None
        if part == '*':
            # Wildcard — handled by caller
            return current
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            except ValueError:
                return None
        else:
            return None
    return current


def _collect_ids(collection: Any) -> Set[str]:
    """Collect all 'id' fields from a list of entities."""
    ids = set()
    if isinstance(collection, list):
        for item in collection:
            if isinstance(item, dict) and 'id' in item:
                ids.add(item['id'])
    return ids


def check_id_references(usdm: dict) -> List[IntegrityFinding]:
    """Layer 1: Check all known ID reference fields resolve to existing entities."""
    findings = []
    study = usdm.get('study', {})
    version = (study.get('versions') or [{}])[0] if study.get('versions') else {}

    def resolve_from_version(path: str) -> Any:
        return _resolve_path(version, path)

    for source_path, ref_field, target_path, target_type, is_array in REFERENCE_RULES:
        source_collection = resolve_from_version(source_path)
        if not isinstance(source_collection, list):
            continue

        target_collection = resolve_from_version(target_path)
        valid_ids = _collect_ids(target_collection)

        if not valid_ids and not target_collection:
            continue  # Target collection doesn't exist — skip silently

        for entity in source_collection:
            if not isinstance(entity, dict):
                continue

            # Handle nested ref fields like "definedProcedures.*.procedureId"
            if '.*.' in ref_field:
                parts = ref_field.split('.*.')
                nested_list = entity.get(parts[0], [])
                if not isinstance(nested_list, list):
                    continue
                for nested in nested_list:
                    if isinstance(nested, dict):
                        ref_val = nested.get(parts[1])
                        if ref_val and ref_val not in valid_ids:
                            findings.append(IntegrityFinding(
                                rule='dangling_reference',
                                severity=Severity.ERROR,
                                message=f'{target_type} reference "{ref_val}" in {ref_field} does not resolve',
                                entity_type=target_type,
                                entity_ids=[ref_val],
                                details={'source': source_path, 'field': ref_field, 'entityId': entity.get('id', '')},
                            ))
                continue

            ref_val = entity.get(ref_field)
            if ref_val is None:
                continue

            if is_array:
                if not isinstance(ref_val, list):
                    ref_val = [ref_val]
                for rid in ref_val:
                    if rid and rid not in valid_ids:
                        findings.append(IntegrityFinding(
                            rule='dangling_reference',
                            severity=Severity.ERROR,
                            message=f'{target_type} reference "{rid}" in {ref_field} does not resolve',
                            entity_type=target_type,
                            entity_ids=[rid],
                            details={'source': source_path, 'field': ref_field, 'entityId': entity.get('id', '')},
                        ))
            else:
                if ref_val not in valid_ids:
                    findings.append(IntegrityFinding(
                        rule='dangling_reference',
                        severity=Severity.ERROR,
                        message=f'{target_type} reference "{ref_val}" in {ref_field} does not resolve',
                        entity_type=target_type,
                        entity_ids=[ref_val],
                        details={'source': source_path, 'field': ref_field, 'entityId': entity.get('id', '')},
                    ))

    return findings


# ---------------------------------------------------------------------------
# Layer 2: Orphan detection
# ---------------------------------------------------------------------------

def check_orphans(usdm: dict) -> List[IntegrityFinding]:
    """Layer 2: Find entities that exist but are never referenced by anything."""
    findings = []
    study = usdm.get('study', {})
    version = (study.get('versions') or [{}])[0] if study.get('versions') else {}
    design = (version.get('studyDesigns') or [{}])[0] if version.get('studyDesigns') else {}

    # Collect all IDs that are referenced somewhere
    referenced_ids: Set[str] = set()

    def _scan_refs(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.endswith('Id') and isinstance(v, str):
                    referenced_ids.add(v)
                elif k.endswith('Ids') and isinstance(v, list):
                    referenced_ids.update(vid for vid in v if isinstance(vid, str))
                elif k == 'procedureId' and isinstance(v, str):
                    referenced_ids.add(v)
                else:
                    _scan_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                _scan_refs(item)

    _scan_refs(version)

    # Check key collections for orphans
    orphan_checks = [
        ('arms', design.get('arms', []), 'StudyArm'),
        ('epochs', design.get('epochs', []), 'StudyEpoch'),
        ('elements', design.get('elements', []), 'StudyElement'),
        ('activities', design.get('activities', []), 'Activity'),
        ('encounters', design.get('encounters', []), 'Encounter'),
        ('procedures', design.get('procedures', []), 'Procedure'),
        ('analysisPopulations', design.get('analysisPopulations', []), 'AnalysisPopulation'),
    ]

    for collection_name, collection, entity_type in orphan_checks:
        if not isinstance(collection, list):
            continue
        for entity in collection:
            if not isinstance(entity, dict):
                continue
            eid = entity.get('id', '')
            if eid and eid not in referenced_ids:
                findings.append(IntegrityFinding(
                    rule='orphan_entity',
                    severity=Severity.WARNING,
                    message=f'{entity_type} "{entity.get("name", eid)}" is never referenced',
                    entity_type=entity_type,
                    entity_ids=[eid],
                ))

    return findings


# ---------------------------------------------------------------------------
# Layer 3: Semantic consistency rules
# ---------------------------------------------------------------------------

def check_semantic_rules(usdm: dict) -> List[IntegrityFinding]:
    """Layer 3: Cross-phase semantic consistency checks."""
    findings = []
    study = usdm.get('study', {})
    version = (study.get('versions') or [{}])[0] if study.get('versions') else {}
    design = (version.get('studyDesigns') or [{}])[0] if version.get('studyDesigns') else {}

    # Rule S1: Every arm must appear in at least one StudyCell
    arms = design.get('arms', [])
    cells = design.get('studyCells', [])
    cell_arm_ids = {c.get('armId') for c in cells if isinstance(c, dict)}
    for arm in arms:
        if isinstance(arm, dict) and arm.get('id') not in cell_arm_ids:
            findings.append(IntegrityFinding(
                rule='arm_not_in_cell',
                severity=Severity.WARNING,
                message=f'Arm "{arm.get("name", arm.get("id"))}" has no StudyCell assignment',
                entity_type='StudyArm',
                entity_ids=[arm.get('id', '')],
            ))

    # Rule S2: Every epoch must appear in at least one StudyCell
    epochs = design.get('epochs', [])
    cell_epoch_ids = {c.get('epochId') for c in cells if isinstance(c, dict)}
    for epoch in epochs:
        if isinstance(epoch, dict) and epoch.get('id') not in cell_epoch_ids:
            findings.append(IntegrityFinding(
                rule='epoch_not_in_cell',
                severity=Severity.WARNING,
                message=f'Epoch "{epoch.get("name", epoch.get("id"))}" has no StudyCell assignment',
                entity_type='StudyEpoch',
                entity_ids=[epoch.get('id', '')],
            ))

    # Rule S3: Estimands should reference existing endpoints
    estimands = design.get('estimands', [])
    endpoint_ids = _collect_ids(design.get('endpoints', []))
    for est in estimands:
        if not isinstance(est, dict):
            continue
        var_id = est.get('variableOfInterestId')
        if var_id and endpoint_ids and var_id not in endpoint_ids:
            findings.append(IntegrityFinding(
                rule='estimand_endpoint_mismatch',
                severity=Severity.ERROR,
                message=f'Estimand "{est.get("name", est.get("id"))}" references unknown endpoint',
                entity_type='Estimand',
                entity_ids=[est.get('id', '')],
                details={'variableOfInterestId': var_id},
            ))

    # Rule S4: Activities in SoA should have non-empty names
    activities = design.get('activities', [])
    unnamed = [a for a in activities if isinstance(a, dict) and not (a.get('name') or a.get('label'))]
    if unnamed:
        findings.append(IntegrityFinding(
            rule='unnamed_activities',
            severity=Severity.WARNING,
            message=f'{len(unnamed)} activities have no name or label',
            entity_type='Activity',
            entity_ids=[a.get('id', '') for a in unnamed],
        ))

    # Rule S5: Eligibility criteria should have a category (inclusion/exclusion)
    criteria = design.get('eligibilityCriteria', [])
    uncategorized = [c for c in criteria if isinstance(c, dict) and not c.get('category')]
    if uncategorized:
        findings.append(IntegrityFinding(
            rule='uncategorized_criteria',
            severity=Severity.WARNING,
            message=f'{len(uncategorized)} eligibility criteria missing inclusion/exclusion category',
            entity_type='EligibilityCriterion',
            entity_ids=[c.get('id', '') for c in uncategorized],
        ))

    # Rule S6: Objectives should have a level (primary/secondary/exploratory)
    objectives = design.get('objectives', [])
    unleveled = [o for o in objectives if isinstance(o, dict) and not o.get('level')]
    if unleveled:
        findings.append(IntegrityFinding(
            rule='unleveled_objectives',
            severity=Severity.WARNING,
            message=f'{len(unleveled)} objectives missing level (primary/secondary/exploratory)',
            entity_type='Objective',
            entity_ids=[o.get('id', '') for o in unleveled],
        ))

    # Rule S7: StudyInterventions should have a type
    interventions = version.get('studyInterventions', [])
    untyped = [i for i in interventions if isinstance(i, dict) and not i.get('type')]
    if untyped:
        findings.append(IntegrityFinding(
            rule='untyped_interventions',
            severity=Severity.INFO,
            message=f'{len(untyped)} interventions missing type code',
            entity_type='StudyIntervention',
            entity_ids=[i.get('id', '') for i in untyped],
        ))

    # Rule S8: Duplicate entity IDs across collections
    all_ids: Dict[str, List[str]] = {}
    collections_to_check = [
        ('arms', arms), ('epochs', epochs), ('activities', activities),
        ('encounters', design.get('encounters', [])),
        ('objectives', objectives), ('endpoints', design.get('endpoints', [])),
        ('interventions', interventions),
    ]
    for cname, coll in collections_to_check:
        if not isinstance(coll, list):
            continue
        for entity in coll:
            if isinstance(entity, dict) and entity.get('id'):
                eid = entity['id']
                all_ids.setdefault(eid, []).append(cname)

    duplicates = {eid: locs for eid, locs in all_ids.items() if len(locs) > 1}
    if duplicates:
        for eid, locs in duplicates.items():
            findings.append(IntegrityFinding(
                rule='duplicate_id',
                severity=Severity.ERROR,
                message=f'ID "{eid}" appears in multiple collections: {", ".join(locs)}',
                entity_ids=[eid],
                details={'collections': locs},
            ))

    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_integrity(usdm: dict) -> IntegrityReport:
    """Run all three layers of referential integrity checks on a USDM output.
    
    Args:
        usdm: The full protocol_usdm.json dict.
    
    Returns:
        IntegrityReport with all findings.
    """
    report = IntegrityReport()

    # Layer 1: ID references
    report.findings.extend(check_id_references(usdm))

    # Layer 2: Orphan detection
    report.findings.extend(check_orphans(usdm))

    # Layer 3: Semantic rules
    report.findings.extend(check_semantic_rules(usdm))

    logger.info(
        f"Integrity check: {report.error_count} errors, "
        f"{report.warning_count} warnings, {report.info_count} info"
    )
    return report


def save_integrity_report(report: IntegrityReport, output_dir: str) -> str:
    """Save integrity report to output directory.
    
    Returns the path to the saved file.
    """
    path = os.path.join(output_dir, 'integrity_report.json')
    with open(path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info(f"Saved integrity report to {path}")
    return path
