"""
Extension→USDM promotion rules.

Promotes data from extension attributes and conditional extractions
back into core USDM entities. Runs after all phase combines.

Promotion rules (each is a no-op if the target already has a value):
1. SAP sampleSizeCalculations → StudyDesignPopulation.plannedEnrollmentNumber
2. SAP sampleSizeCalculations → StudyDesignPopulation.plannedCompletionNumber
3. Eligibility criteria text → StudyDesignPopulation.plannedSex
4. Eligibility criteria text → StudyDesignPopulation.plannedAge
"""

from typing import Dict, Optional, Any
import json
import logging
import re
import uuid

from core.usdm_types import generate_uuid

logger = logging.getLogger(__name__)


def _build_participant_quantity(value: int) -> dict:
    """Build a USDM-compliant Quantity object for participant counts."""
    return {
        "id": generate_uuid(),
        "value": float(value),
        "unit": {
            "id": generate_uuid(),
            "standardCode": {
                "code": "C25463",
                "codeSystem": "http://www.cdisc.org",
                "decode": "Count",
                "instanceType": "Code",
            },
            "standardCodeAliases": [],
            "instanceType": "AliasCode",
        },
        "instanceType": "Quantity",
    }


def promote_extensions_to_usdm(combined: dict) -> None:
    """Promote extension/conditional data back into core USDM entities.
    
    This is the key architectural mechanism for cross-phase enrichment.
    It runs after ALL phase combines and conditional integrations (SAP, sites,
    execution), allowing later phases to enrich entities created by earlier ones.
    
    Promotion rules (each is a no-op if the target already has a value):
    
    1. SAP sampleSizeCalculations → StudyDesignPopulation.plannedEnrollmentNumber
       (SAP provides the authoritative sample size; eligibility may have a rough estimate)
    
    2. SAP sampleSizeCalculations → StudyDesignPopulation.plannedCompletionNumber
       (if SAP specifies completers separately)
    
    3. narrative safety sections → NarrativeContent/NarrativeContentItem with sectionType=Safety (set at extraction time)
    4. narrative discontinuation → NarrativeContent/NarrativeContentItem with sectionType=Discontinuation (set at extraction time)
    """
    try:
        study = combined.get('study', {})
        versions = study.get('versions', [{}])
        version = versions[0] if versions else {}
        designs = version.get('studyDesigns', [{}])
        design = designs[0] if designs else {}
        
        population = design.get('population', {})
        if not isinstance(population, dict):
            population = {}
        
        promotions = 0
        
        # --- Rule 1: SAP sample size → plannedEnrollmentNumber ---
        if not population.get('plannedEnrollmentNumber'):
            sample_size = _extract_sample_size_from_extensions(design)
            if sample_size is not None:
                population['plannedEnrollmentNumber'] = _build_participant_quantity(sample_size)
                logger.info(f"  ✓ Promoted SAP sample size ({sample_size}) → population.plannedEnrollmentNumber")
                promotions += 1
        
        # --- Rule 2: SAP completers → plannedCompletionNumber ---
        if not population.get('plannedCompletionNumber'):
            completion_n = _extract_completion_number_from_extensions(design)
            if completion_n is not None:
                population['plannedCompletionNumber'] = _build_participant_quantity(completion_n)
                logger.info(f"  ✓ Promoted SAP completers ({completion_n}) → population.plannedCompletionNumber")
                promotions += 1
        
        # --- Rule 3: Infer plannedSex from eligibility criteria text if missing ---
        if not population.get('plannedSex'):
            inferred_sex = _infer_sex_from_criteria(design)
            if inferred_sex:
                population['plannedSex'] = inferred_sex
                sex_labels = [s.get('decode', s.get('code', '')) for s in inferred_sex]
                logger.info(f"  ✓ Inferred population sex from criteria: {sex_labels}")
                promotions += 1
        
        # --- Rule 4: Infer plannedAge from eligibility criteria text if missing ---
        if not population.get('plannedAge'):
            inferred_age = _infer_age_from_criteria(design, version)
            if inferred_age:
                population['plannedAge'] = inferred_age
                min_v = inferred_age.get('minValue', {}).get('value', '?') if isinstance(inferred_age.get('minValue'), dict) else '?'
                max_v = inferred_age.get('maxValue', {}).get('value', '?') if isinstance(inferred_age.get('maxValue'), dict) else '?'
                logger.info(f"  ✓ Inferred population age from criteria: {min_v}-{max_v} Years")
                promotions += 1
        
        # Write back if we made changes
        if population and promotions > 0:
            design['population'] = population
            logger.info(f"  ✓ Extension→USDM promotion: {promotions} field(s) enriched")
    
    except Exception as e:
        logger.warning(f"  ⚠ Extension→USDM promotion skipped: {e}")


def _extract_sample_size_from_extensions(design: dict) -> Optional[int]:
    """Extract the target sample size from SAP extension attributes."""
    for ext in design.get('extensionAttributes', []):
        url = ext.get('url', '')
        if 'sap-sample-size' in url:
            try:
                calcs = json.loads(ext.get('valueString', '[]'))
                if isinstance(calcs, list):
                    for calc in calcs:
                        n = calc.get('targetSampleSize')
                        if n and isinstance(n, (int, float)):
                            return int(n)
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def _extract_completion_number_from_extensions(design: dict) -> Optional[int]:
    """Extract the planned completion number from SAP extension attributes."""
    for ext in design.get('extensionAttributes', []):
        url = ext.get('url', '')
        if 'sap-sample-size' in url:
            try:
                calcs = json.loads(ext.get('valueString', '[]'))
                if isinstance(calcs, list):
                    for calc in calcs:
                        # Some SAPs specify completers separately
                        n = calc.get('plannedCompleters') or calc.get('completionNumber')
                        if n and isinstance(n, (int, float)):
                            return int(n)
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def _infer_sex_from_criteria(design: dict) -> Optional[list]:
    """Infer planned sex from eligibility criteria text if not explicitly set.
    
    Scans inclusion/exclusion criteria for sex-specific language.
    Returns None if criteria suggest both sexes (the default for most trials).
    """
    criteria = design.get('eligibilityCriteria', [])
    if not criteria:
        return None
    
    all_text = ' '.join(
        c.get('text', '') or c.get('name', '')
        for c in criteria if isinstance(c, dict)
    ).lower()
    
    # Check for sex-specific exclusions or restrictions
    male_only = bool(re.search(r'\b(male\s+(?:only|subjects?|participants?))\b', all_text))
    female_only = bool(re.search(r'\b(female\s+(?:only|subjects?|participants?))\b', all_text))
    pregnancy_exclusion = bool(re.search(r'\b(pregnan|nursing|lactating|breastfeeding)\b', all_text))
    
    # If trial explicitly excludes pregnancy, it likely includes females
    # (pregnancy exclusion doesn't mean female-only)
    
    if male_only and not female_only:
        return [_make_sex_code('Male')]
    elif female_only and not male_only:
        return [_make_sex_code('Female')]
    else:
        # Default: both sexes (most common)
        return [_make_sex_code('Male'), _make_sex_code('Female')]


def _infer_age_from_criteria(design: dict, version: dict) -> Optional[dict]:
    """Infer planned age range from eligibility criteria text.
    
    Scans inclusion criteria for age requirements like "≥18 years" or
    "18 to 75 years of age".
    """
    # First check criterion items for text (more reliable than criteria names)
    criterion_items = version.get('eligibilityCriterionItems', [])
    criteria = design.get('eligibilityCriteria', [])
    
    all_texts = []
    for item in criterion_items:
        if isinstance(item, dict) and item.get('text'):
            all_texts.append(item['text'])
    for crit in criteria:
        if isinstance(crit, dict):
            name = crit.get('name', '')
            if name:
                all_texts.append(name)
    
    combined = ' '.join(all_texts)
    
    min_age = None
    max_age = None
    
    # Pattern: "18 to 75 years" or "18-75 years"
    m = re.search(r'(\d{1,3})\s*(?:to|-|–)\s*(\d{1,3})\s*(?:years?\b)?', combined, re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 120 and 1 <= b <= 120:
            min_age = a
            max_age = b
    
    # Pattern: "≥18 years" or ">=18" or "at least 18 years"
    if min_age is None:
        m = re.search(r'(?:≥|>=|at\s+least|minimum\s+(?:of\s+)?)\s*(\d{1,3})\s*(?:years?\b)?', combined, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 120:
                min_age = v
    
    # Pattern: "aged ≥18" or "aged >=18" (common clinical phrasing)
    if min_age is None:
        m = re.search(r'\baged\s*(?:≥|>=|>)\s*(\d{1,3})\b', combined, re.IGNORECASE)
        if m:
            min_age = int(m.group(1))
    
    # Pattern: "≤75 years" or "<=75" or "up to 75 years"
    if max_age is None:
        m = re.search(r'(?:≤|<=|up\s+to|not\s+(?:older|more)\s+than|maximum\s+(?:of\s+)?)\s*(\d{1,3})\s*(?:years?\b)?', combined, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 120:
                max_age = v
    
    # Pattern: "Age ≥ 18" or "Age >= 18" (age keyword before comparator)
    if min_age is None:
        m = re.search(r'\bage\s*(?:≥|>=|>)\s*(\d{1,3})\b', combined, re.IGNORECASE)
        if m:
            min_age = int(m.group(1))
    if max_age is None:
        m = re.search(r'\bage\s*(?:≤|<=|<)\s*(\d{1,3})\b', combined, re.IGNORECASE)
        if m:
            max_age = int(m.group(1))
    
    if min_age is not None or max_age is not None:
        unit_code = {
            'id': str(uuid.uuid4()),
            'standardCode': {'code': 'C29848', 'codeSystem': 'http://www.cdisc.org', 'decode': 'Years', 'instanceType': 'Code'},
            'standardCodeAliases': [],
            'instanceType': 'AliasCode',
        }
        age_range: dict = {'id': str(uuid.uuid4()), 'instanceType': 'Range', 'isApproximate': False}
        if min_age is not None:
            age_range['minValue'] = {
                'id': str(uuid.uuid4()),
                'value': min_age,
                'unit': unit_code,
                'instanceType': 'Quantity',
            }
        if max_age is not None:
            age_range['maxValue'] = {
                'id': str(uuid.uuid4()),
                'value': max_age,
                'unit': unit_code,
                'instanceType': 'Quantity',
            }
        return age_range
    
    return None


def _make_sex_code(sex: str) -> dict:
    """Create a USDM Code object for sex."""
    return {
        'id': str(uuid.uuid4()),
        'code': sex,
        'codeSystem': 'http://www.cdisc.org/USDM/sex',
        'codeSystemVersion': '2024-09-27',
        'decode': sex,
        'instanceType': 'Code',
    }
