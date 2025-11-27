"""
Terminology Enrichment

Enriches USDM entities with standardized terminology codes from:
- NCI Thesaurus
- CDISC Controlled Terminology
- MedDRA
- SNOMED CT
"""

import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Common mappings for study phase
STUDY_PHASE_CODES = {
    'Phase 1': {'code': 'C15600', 'codeSystem': 'NCI', 'decode': 'Phase I Trial'},
    'Phase 2': {'code': 'C15601', 'codeSystem': 'NCI', 'decode': 'Phase II Trial'},
    'Phase 3': {'code': 'C15602', 'codeSystem': 'NCI', 'decode': 'Phase III Trial'},
    'Phase 4': {'code': 'C15603', 'codeSystem': 'NCI', 'decode': 'Phase IV Trial'},
    'Phase 1/2': {'code': 'C15693', 'codeSystem': 'NCI', 'decode': 'Phase I/II Trial'},
    'Phase 2/3': {'code': 'C15694', 'codeSystem': 'NCI', 'decode': 'Phase II/III Trial'},
}

# Blinding schema codes
BLINDING_CODES = {
    'Open Label': {'code': 'C82639', 'codeSystem': 'NCI', 'decode': 'Open Label Study'},
    'Single Blind': {'code': 'C15228', 'codeSystem': 'NCI', 'decode': 'Single Blind Study'},
    'Double Blind': {'code': 'C15227', 'codeSystem': 'NCI', 'decode': 'Double Blind Study'},
    'Triple Blind': {'code': 'C156397', 'codeSystem': 'NCI', 'decode': 'Triple Blind Study'},
}

# Objective level codes
OBJECTIVE_LEVEL_CODES = {
    'Primary': {'code': 'C98772', 'codeSystem': 'NCI', 'decode': 'Primary Objective'},
    'Secondary': {'code': 'C98781', 'codeSystem': 'NCI', 'decode': 'Secondary Objective'},
    'Exploratory': {'code': 'C98724', 'codeSystem': 'NCI', 'decode': 'Exploratory Objective'},
}

# Eligibility category codes
ELIGIBILITY_CODES = {
    'Inclusion': {'code': 'C25532', 'codeSystem': 'NCI', 'decode': 'Inclusion Criteria'},
    'Exclusion': {'code': 'C25370', 'codeSystem': 'NCI', 'decode': 'Exclusion Criteria'},
}


def enrich_terminology(json_path: str) -> Dict[str, Any]:
    """
    Enrich USDM entities with standardized terminology.
    
    Args:
        json_path: Path to USDM JSON file (modified in place)
        
    Returns:
        Dict with enrichment results
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enriched_count = 0
        
        # Enrich recursively
        def enrich_entity(obj: Dict, path: str = "") -> None:
            nonlocal enriched_count
            
            if not isinstance(obj, dict):
                return
            
            instance_type = obj.get('instanceType')
            
            # Enrich study phase
            if instance_type == 'StudyPhase' or 'studyPhase' in obj:
                phase_obj = obj if instance_type == 'StudyPhase' else obj.get('studyPhase', {})
                if isinstance(phase_obj, dict):
                    phase = phase_obj.get('phase') or phase_obj.get('standardCode', {}).get('decode')
                    if phase:
                        for key, code_obj in STUDY_PHASE_CODES.items():
                            if key.lower() in phase.lower():
                                phase_obj['standardCode'] = code_obj.copy()
                                enriched_count += 1
                                break
            
            # Enrich blinding schema
            if 'blindingSchema' in obj:
                blinding = obj['blindingSchema']
                if isinstance(blinding, dict):
                    blinding_text = blinding.get('code') or blinding.get('decode') or ''
                elif isinstance(blinding, str):
                    blinding_text = blinding
                else:
                    blinding_text = ''
                
                for key, code_obj in BLINDING_CODES.items():
                    if key.lower() in blinding_text.lower():
                        if isinstance(obj['blindingSchema'], dict):
                            obj['blindingSchema'].update(code_obj)
                        else:
                            obj['blindingSchema'] = code_obj.copy()
                        enriched_count += 1
                        break
            
            # Enrich objective level
            if instance_type in ('Objective', 'Endpoint') and 'level' in obj:
                level = obj['level']
                if isinstance(level, dict):
                    level_text = level.get('code') or level.get('decode') or ''
                elif isinstance(level, str):
                    level_text = level
                else:
                    level_text = ''
                
                for key, code_obj in OBJECTIVE_LEVEL_CODES.items():
                    if key.lower() == level_text.lower():
                        if isinstance(obj['level'], dict):
                            obj['level'].update(code_obj)
                        else:
                            obj['level'] = code_obj.copy()
                        enriched_count += 1
                        break
            
            # Enrich eligibility category
            if instance_type == 'EligibilityCriterion' and 'category' in obj:
                category = obj['category']
                if isinstance(category, dict):
                    cat_text = category.get('code') or category.get('decode') or ''
                elif isinstance(category, str):
                    cat_text = category
                else:
                    cat_text = ''
                
                for key, code_obj in ELIGIBILITY_CODES.items():
                    if key.lower() == cat_text.lower():
                        if isinstance(obj['category'], dict):
                            obj['category'].update(code_obj)
                        else:
                            obj['category'] = code_obj.copy()
                        enriched_count += 1
                        break
            
            # Recurse
            for key, value in obj.items():
                if isinstance(value, dict):
                    enrich_entity(value, f"{path}/{key}")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            enrich_entity(item, f"{path}/{key}[{i}]")
        
        enrich_entity(data)
        
        # Save enriched data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Enriched {enriched_count} entities with terminology codes")
        
        return {
            'success': True,
            'enriched': enriched_count,
        }
        
    except Exception as e:
        logger.error(f"Terminology enrichment failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'enriched': 0,
        }


def lookup_nci_code(term: str) -> Optional[Dict[str, str]]:
    """
    Look up NCI Thesaurus code for a term.
    
    In production, this would call the NCI EVS API.
    """
    # Placeholder - would call NCI EVS API
    return None


def lookup_meddra_code(term: str) -> Optional[Dict[str, str]]:
    """
    Look up MedDRA code for a medical term.
    
    In production, this would call MedDRA API.
    """
    # Placeholder - would call MedDRA API
    return None
