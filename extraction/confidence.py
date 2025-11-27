"""
Extraction Confidence Scoring

Calculates confidence scores for extraction results based on:
- Completeness of extracted data
- Presence of key fields
- Consistency with expected patterns
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class ConfidenceScore:
    """Confidence score with breakdown."""
    overall: float  # 0.0 to 1.0
    completeness: float  # How many expected fields are filled
    field_quality: float  # Quality of individual field values
    breakdown: Dict[str, float]  # Per-field scores
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 2),
            "completeness": round(self.completeness, 2),
            "fieldQuality": round(self.field_quality, 2),
            "breakdown": {k: round(v, 2) for k, v in self.breakdown.items()},
        }


def calculate_metadata_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for metadata extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    # Check key fields
    scores['titles'] = 1.0 if data.titles and len(data.titles) > 0 else 0.0
    scores['identifiers'] = 1.0 if data.identifiers and len(data.identifiers) >= 2 else 0.5 if data.identifiers else 0.0
    scores['organizations'] = 1.0 if data.organizations and len(data.organizations) > 0 else 0.0
    scores['study_phase'] = 1.0 if data.study_phase else 0.0
    scores['indications'] = 1.0 if data.indications and len(data.indications) > 0 else 0.0
    
    # Completeness
    completeness = sum(scores.values()) / len(scores)
    
    # Field quality - check for reasonable content
    quality_scores = []
    if data.titles:
        # Title should be reasonable length
        avg_len = sum(len(t.text) for t in data.titles) / len(data.titles)
        quality_scores.append(1.0 if 20 < avg_len < 300 else 0.5)
    if data.identifiers:
        # Should have NCT number or sponsor ID
        has_nct = any('NCT' in (i.text or '') for i in data.identifiers)
        quality_scores.append(1.0 if has_nct else 0.7)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_eligibility_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for eligibility extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    # Check key fields
    inc_count = data.inclusion_count if hasattr(data, 'inclusion_count') else 0
    exc_count = data.exclusion_count if hasattr(data, 'exclusion_count') else 0
    
    # Typical protocols have 5-15 inclusion, 10-30 exclusion
    scores['inclusion'] = 1.0 if 3 <= inc_count <= 20 else 0.5 if inc_count > 0 else 0.0
    scores['exclusion'] = 1.0 if 5 <= exc_count <= 40 else 0.5 if exc_count > 0 else 0.0
    scores['population'] = 1.0 if data.population else 0.0
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality - check text lengths from criterion_items
    quality_scores = []
    criterion_items = getattr(data, 'criterion_items', [])
    if criterion_items:
        avg_text_len = sum(len(item.text) for item in criterion_items if hasattr(item, 'text') and item.text) / len(criterion_items)
        quality_scores.append(1.0 if avg_text_len > 30 else 0.5)
    
    # Check for identifiers in criteria
    criteria = getattr(data, 'criteria', [])
    if criteria:
        has_ids = all(c.identifier for c in criteria if hasattr(c, 'identifier'))
        quality_scores.append(1.0 if has_ids else 0.7)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_objectives_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for objectives extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    objectives = getattr(data, 'objectives', [])
    endpoints = getattr(data, 'endpoints', [])
    
    primary = len([o for o in objectives if hasattr(o, 'level') and o.level.value == 'Primary'])
    secondary = len([o for o in objectives if hasattr(o, 'level') and o.level.value == 'Secondary'])
    
    # Must have at least 1 primary objective
    scores['primary_objectives'] = 1.0 if primary >= 1 else 0.0
    scores['secondary_objectives'] = 1.0 if secondary >= 1 else 0.5
    scores['endpoints'] = 1.0 if len(endpoints) >= primary else 0.5 if len(endpoints) > 0 else 0.0
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality
    quality_scores = []
    if objectives:
        avg_text_len = sum(len(getattr(o, 'text', '') or '') for o in objectives) / len(objectives)
        quality_scores.append(1.0 if avg_text_len > 20 else 0.5)
    if endpoints:
        # Endpoints should link to objectives (check for objective_id singular)
        linked = sum(1 for e in endpoints if getattr(e, 'objective_id', None) or getattr(e, 'objective_ids', None))
        quality_scores.append(linked / len(endpoints) if endpoints else 0.0)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_studydesign_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for study design extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    study_design = getattr(data, 'study_design', None)
    arms = getattr(data, 'arms', [])
    cohorts = getattr(data, 'cohorts', [])
    
    scores['study_design'] = 1.0 if study_design else 0.0
    scores['arms'] = 1.0 if arms and len(arms) >= 1 else 0.0
    scores['cohorts'] = 1.0 if cohorts else 0.5  # Not all studies have cohorts
    scores['blinding'] = 1.0 if study_design and getattr(study_design, 'blinding_schema', None) else 0.5
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality
    quality_scores = []
    if arms:
        # Arms should have names and descriptions
        has_names = all(getattr(a, 'name', None) for a in arms)
        quality_scores.append(1.0 if has_names else 0.5)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_interventions_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for interventions extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    interventions = getattr(data, 'interventions', [])
    products = getattr(data, 'products', [])
    administrations = getattr(data, 'administrations', [])
    substances = getattr(data, 'substances', [])
    
    scores['interventions'] = 1.0 if interventions and len(interventions) >= 1 else 0.0
    scores['products'] = 1.0 if products and len(products) >= 1 else 0.5
    scores['administrations'] = 1.0 if administrations else 0.5
    scores['substances'] = 1.0 if substances else 0.5
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality
    quality_scores = []
    if interventions:
        has_names = all(getattr(i, 'name', None) for i in interventions)
        quality_scores.append(1.0 if has_names else 0.5)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_narrative_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for narrative extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    sections = getattr(data, 'sections', [])
    abbreviations = getattr(data, 'abbreviations', [])
    document = getattr(data, 'document', None)
    
    scores['sections'] = 1.0 if sections and len(sections) >= 5 else 0.5 if sections else 0.0
    scores['abbreviations'] = 1.0 if abbreviations and len(abbreviations) >= 3 else 0.5 if abbreviations else 0.0
    scores['document'] = 1.0 if document else 0.5
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality
    quality_scores = []
    if abbreviations:
        # Abbreviations should have both short and expanded text
        complete = all(getattr(a, 'abbreviated_text', None) and getattr(a, 'expanded_text', None) for a in abbreviations)
        quality_scores.append(1.0 if complete else 0.5)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)


def calculate_advanced_confidence(data: Any) -> ConfidenceScore:
    """Calculate confidence for advanced entities extraction."""
    if not data:
        return ConfidenceScore(0.0, 0.0, 0.0, {})
    
    scores = {}
    
    amendments = getattr(data, 'amendments', [])
    geographic_scope = getattr(data, 'geographic_scope', None)
    countries = getattr(data, 'countries', [])
    
    scores['amendments'] = 1.0 if amendments else 0.5  # Not all protocols have amendments
    scores['geographic_scope'] = 1.0 if geographic_scope else 0.5
    scores['countries'] = 1.0 if countries and len(countries) >= 1 else 0.5
    
    completeness = sum(scores.values()) / len(scores)
    
    # Quality
    quality_scores = []
    if amendments:
        has_numbers = all(getattr(a, 'number', None) for a in amendments)
        quality_scores.append(1.0 if has_numbers else 0.5)
    
    field_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
    
    overall = (completeness * 0.6) + (field_quality * 0.4)
    
    return ConfidenceScore(overall, completeness, field_quality, scores)
