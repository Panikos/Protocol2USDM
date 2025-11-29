"""
Terminology Enrichment

Enriches USDM entities with standardized terminology codes from:
- NCI Thesaurus (via EVS API)
- CDISC Controlled Terminology

Uses the EVS client with local caching for offline operation.
Based on the approach from https://github.com/Panikos/AIBC
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from core.evs_client import (
    EVSClient, 
    get_client, 
    fetch_code, 
    find_ct_entry,
    ensure_usdm_codes_cached,
    USDM_CODES,
)

logger = logging.getLogger(__name__)

# Term-to-code mappings for common USDM entities
# These map text values to NCI codes for quick lookup
STUDY_PHASE_MAPPINGS = {
    'phase 1': 'C15600',
    'phase i': 'C15600',
    'phase 2': 'C15601',
    'phase ii': 'C15601',
    'phase 3': 'C15602',
    'phase iii': 'C15602',
    'phase 4': 'C15603',
    'phase iv': 'C15603',
    'phase 1/2': 'C15693',
    'phase i/ii': 'C15693',
    'phase 2/3': 'C15694',
    'phase ii/iii': 'C15694',
}

BLINDING_MAPPINGS = {
    'open label': 'C82639',
    'open-label': 'C82639',
    'single blind': 'C15228',
    'single-blind': 'C15228',
    'double blind': 'C15227',
    'double-blind': 'C15227',
    'triple blind': 'C156397',
    'triple-blind': 'C156397',
}

OBJECTIVE_LEVEL_MAPPINGS = {
    'primary': 'C98772',
    'secondary': 'C98781',
    'exploratory': 'C98724',
}

ELIGIBILITY_MAPPINGS = {
    'inclusion': 'C25532',
    'exclusion': 'C25370',
}

ENDPOINT_LEVEL_MAPPINGS = {
    'primary': 'C98770',
    'secondary': 'C98784',
    'exploratory': 'C157551',
}

ARM_TYPE_MAPPINGS = {
    'experimental': 'C174266',
    'treatment': 'C174266',
    'placebo': 'C49648',
    'active comparator': 'C49649',
    'comparator': 'C49649',
    'no intervention': 'C174269',
    'control': 'C49649',
}


def _get_code_object(nci_code: str, client: EVSClient) -> Optional[Dict[str, Any]]:
    """Get a USDM Code object for an NCI code, using cache."""
    code_obj = client.fetch_ncit_code(nci_code)
    if code_obj:
        return code_obj
    
    # Fallback: return minimal code object from USDM_CODES
    if nci_code in USDM_CODES:
        return {
            "id": nci_code,
            "code": nci_code,
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "codeSystemVersion": "unknown",
            "decode": USDM_CODES[nci_code],
            "instanceType": "Code",
        }
    return None


def _find_mapping(text: str, mappings: Dict[str, str]) -> Optional[str]:
    """Find NCI code for text in mappings."""
    if not text:
        return None
    text_lower = text.lower().strip()
    
    # Exact match
    if text_lower in mappings:
        return mappings[text_lower]
    
    # Partial match
    for key, code in mappings.items():
        if key in text_lower or text_lower in key:
            return code
    
    return None


def enrich_terminology(json_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Enrich USDM entities with standardized NCI terminology codes.
    
    Uses the EVS API with local caching for efficient lookups.
    
    Args:
        json_path: Path to USDM JSON file (modified in place)
        output_dir: Optional output directory for enrichment report
        
    Returns:
        Dict with enrichment results
    """
    try:
        # Initialize EVS client and ensure USDM codes are cached
        client = get_client()
        ensure_usdm_codes_cached(client)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enriched_count = 0
        total_entities = 0
        by_type: Dict[str, int] = {}
        
        def enrich_entity(obj: Dict, path: str = "") -> None:
            nonlocal enriched_count, total_entities
            
            if not isinstance(obj, dict):
                return
            
            instance_type = obj.get('instanceType')
            if instance_type:
                total_entities += 1
            
            # Enrich study phase
            if 'studyPhase' in obj or instance_type == 'StudyPhase':
                phase_obj = obj.get('studyPhase', obj) if 'studyPhase' in obj else obj
                if isinstance(phase_obj, dict):
                    phase_text = (
                        phase_obj.get('phase') or 
                        phase_obj.get('standardCode', {}).get('decode') or
                        phase_obj.get('decode', '')
                    )
                    nci_code = _find_mapping(phase_text, STUDY_PHASE_MAPPINGS)
                    if nci_code:
                        code_obj = _get_code_object(nci_code, client)
                        if code_obj:
                            phase_obj['standardCode'] = code_obj
                            enriched_count += 1
                            by_type['StudyPhase'] = by_type.get('StudyPhase', 0) + 1
            
            # Enrich blinding schema
            if 'blindingSchema' in obj:
                blinding = obj['blindingSchema']
                blinding_text = ''
                if isinstance(blinding, dict):
                    blinding_text = blinding.get('decode') or blinding.get('code', '')
                elif isinstance(blinding, str):
                    blinding_text = blinding
                
                nci_code = _find_mapping(blinding_text, BLINDING_MAPPINGS)
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['blindingSchema'] = code_obj
                        enriched_count += 1
                        by_type['BlindingSchema'] = by_type.get('BlindingSchema', 0) + 1
            
            # Enrich objective level
            if instance_type == 'Objective' and 'level' in obj:
                level = obj['level']
                level_text = ''
                if isinstance(level, dict):
                    level_text = level.get('decode') or level.get('code', '')
                elif isinstance(level, str):
                    level_text = level
                
                nci_code = _find_mapping(level_text, OBJECTIVE_LEVEL_MAPPINGS)
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['level'] = code_obj
                        enriched_count += 1
                        by_type['Objective'] = by_type.get('Objective', 0) + 1
            
            # Enrich endpoint level
            if instance_type == 'Endpoint' and 'level' in obj:
                level = obj['level']
                level_text = ''
                if isinstance(level, dict):
                    level_text = level.get('decode') or level.get('code', '')
                elif isinstance(level, str):
                    level_text = level
                
                nci_code = _find_mapping(level_text, ENDPOINT_LEVEL_MAPPINGS)
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['level'] = code_obj
                        enriched_count += 1
                        by_type['Endpoint'] = by_type.get('Endpoint', 0) + 1
            
            # Enrich eligibility category
            if instance_type == 'EligibilityCriterion' and 'category' in obj:
                category = obj['category']
                cat_text = ''
                if isinstance(category, dict):
                    cat_text = category.get('decode') or category.get('code', '')
                elif isinstance(category, str):
                    cat_text = category
                
                nci_code = _find_mapping(cat_text, ELIGIBILITY_MAPPINGS)
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['category'] = code_obj
                        enriched_count += 1
                        by_type['EligibilityCriterion'] = by_type.get('EligibilityCriterion', 0) + 1
            
            # Enrich study arm type
            if instance_type == 'StudyArm' and 'type' in obj:
                arm_type = obj['type']
                type_text = ''
                if isinstance(arm_type, dict):
                    type_text = arm_type.get('decode') or arm_type.get('code', '')
                elif isinstance(arm_type, str):
                    type_text = arm_type
                
                nci_code = _find_mapping(type_text, ARM_TYPE_MAPPINGS)
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['type'] = code_obj
                        enriched_count += 1
                        by_type['StudyArm'] = by_type.get('StudyArm', 0) + 1
            
            # Recurse into nested objects
            for key, value in obj.items():
                if isinstance(value, dict):
                    enrich_entity(value, f"{path}/{key}")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            enrich_entity(item, f"{path}/{key}[{i}]")
        
        # Run enrichment
        enrich_entity(data)
        
        # Save enriched data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Enriched {enriched_count} entities with NCI terminology codes")
        
        # Build result
        result = {
            'success': True,
            'enriched': enriched_count,
            'total_entities': total_entities,
            'by_type': by_type,
            'cache_stats': client.get_cache_stats(),
        }
        
        # Save enrichment report if output_dir provided
        if output_dir:
            report_path = Path(output_dir) / "terminology_enrichment.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Enrichment report saved to: {report_path}")
        
        return result
        
    except Exception as e:
        logger.error(f"Terminology enrichment failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'enriched': 0,
        }


def lookup_nci_code(term: str) -> Optional[Dict[str, Any]]:
    """
    Look up NCI Thesaurus code for a term using the EVS API.
    
    Args:
        term: Term to search for
        
    Returns:
        USDM Code object or None if not found
    """
    entry = find_ct_entry(term)
    if entry:
        return {
            "id": entry.get("code"),
            "code": entry.get("code"),
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "codeSystemVersion": "unknown",
            "decode": entry.get("preferredName") or entry.get("name", term),
            "instanceType": "Code",
        }
    return None


def update_evs_cache() -> Dict[str, int]:
    """
    Update the EVS cache with all USDM-relevant NCI codes.
    
    Call this to refresh the cache or on first run.
    
    Returns:
        Dict with success/failed/skipped counts
    """
    client = get_client()
    return ensure_usdm_codes_cached(client)


def get_evs_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the EVS cache.
    
    Returns:
        Dict with cache statistics
    """
    return get_client().get_cache_stats()


def clear_evs_cache() -> None:
    """
    Clear the EVS cache.
    """
    get_client().clear_cache()
