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
from core.code_registry import registry as _cr

logger = logging.getLogger(__name__)


def _get_code_object(nci_code: str, client: EVSClient) -> Optional[Dict[str, Any]]:
    """Get a USDM Code object for an NCI code, using cache.
    
    Always returns a fresh copy with a unique UUID id so repeated calls
    for the same code don't produce duplicate IDs (CORE-001015).
    """
    import copy
    import uuid as _uuid
    
    code_obj = client.fetch_ncit_code(nci_code)
    if code_obj:
        result = copy.deepcopy(code_obj)
        result["id"] = str(_uuid.uuid4())
        return result
    
    # Fallback: return minimal code object from USDM_CODES
    if nci_code in USDM_CODES:
        return {
            "id": str(_uuid.uuid4()),
            "code": nci_code,
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "codeSystemVersion": "unknown",
            "decode": USDM_CODES[nci_code],
            "instanceType": "Code",
        }
    return None


def _find_code(text: str, codelist_key: str) -> Optional[str]:
    """Find NCI code for text via CodeRegistry match."""
    if not text:
        return None
    term = _cr.match(codelist_key, text)
    return term.code if term else None


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
        enriched_items: List[Dict[str, str]] = []  # Track individual enriched items
        
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
                    nci_code = _find_code(phase_text, "studyPhase")
                    if nci_code:
                        code_obj = _get_code_object(nci_code, client)
                        if code_obj:
                            phase_obj['standardCode'] = code_obj
                            enriched_count += 1
                            by_type['StudyPhase'] = by_type.get('StudyPhase', 0) + 1
                            enriched_items.append({'type': 'StudyPhase', 'name': phase_text, 'nci_code': nci_code})
            
            # Enrich blinding schema
            if 'blindingSchema' in obj:
                blinding = obj['blindingSchema']
                blinding_text = ''
                if isinstance(blinding, dict):
                    blinding_text = blinding.get('decode') or blinding.get('code', '')
                elif isinstance(blinding, str):
                    blinding_text = blinding
                
                nci_code = _find_code(blinding_text, "blindingSchema")
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['blindingSchema'] = code_obj
                        enriched_count += 1
                        by_type['BlindingSchema'] = by_type.get('BlindingSchema', 0) + 1
                        enriched_items.append({'type': 'BlindingSchema', 'name': blinding_text, 'nci_code': nci_code})
            
            # Enrich objective level (skip if already has valid CDISC code)
            if instance_type == 'Objective' and 'level' in obj:
                level = obj['level']
                _already_coded = (isinstance(level, dict)
                                  and level.get('code', '').startswith('C')
                                  and level.get('codeSystem') == 'http://www.cdisc.org')
                if not _already_coded:
                    level_text = ''
                    if isinstance(level, dict):
                        level_text = level.get('decode') or level.get('code', '')
                    elif isinstance(level, str):
                        level_text = level
                    
                    nci_code = _find_code(level_text, "objectiveLevel")
                    if nci_code:
                        code_obj = _get_code_object(nci_code, client)
                        if code_obj:
                            obj['level'] = code_obj
                            enriched_count += 1
                            by_type['Objective'] = by_type.get('Objective', 0) + 1
                            obj_name = obj.get('name', obj.get('text', 'Unnamed'))[:50]
                            enriched_items.append({'type': 'Objective', 'name': obj_name, 'level': level_text, 'nci_code': nci_code})
            
            # Enrich endpoint level (skip if already has valid CDISC code)
            if instance_type == 'Endpoint' and 'level' in obj:
                level = obj['level']
                _already_coded = (isinstance(level, dict)
                                  and level.get('code', '').startswith('C')
                                  and level.get('codeSystem') == 'http://www.cdisc.org')
                if not _already_coded:
                    level_text = ''
                    if isinstance(level, dict):
                        level_text = level.get('decode') or level.get('code', '')
                    elif isinstance(level, str):
                        level_text = level
                    
                    nci_code = _find_code(level_text, "endpointLevel")
                    if nci_code:
                        code_obj = _get_code_object(nci_code, client)
                        if code_obj:
                            obj['level'] = code_obj
                            enriched_count += 1
                            by_type['Endpoint'] = by_type.get('Endpoint', 0) + 1
                            ep_name = obj.get('name', obj.get('text', 'Unnamed'))[:50]
                            enriched_items.append({'type': 'Endpoint', 'name': ep_name, 'level': level_text, 'nci_code': nci_code})
            
            # Enrich eligibility category (skip if already has valid CDISC code)
            if instance_type == 'EligibilityCriterion' and 'category' in obj:
                category = obj['category']
                _already_coded = (isinstance(category, dict) 
                                  and category.get('code', '').startswith('C')
                                  and category.get('codeSystem') == 'http://www.cdisc.org')
                if not _already_coded:
                    cat_text = ''
                    if isinstance(category, dict):
                        cat_text = category.get('decode') or category.get('code', '')
                    elif isinstance(category, str):
                        cat_text = category
                    
                    nci_code = _find_code(cat_text, "eligibilityCategory")
                    if nci_code:
                        code_obj = _get_code_object(nci_code, client)
                        if code_obj:
                            obj['category'] = code_obj
                            enriched_count += 1
                            by_type['EligibilityCriterion'] = by_type.get('EligibilityCriterion', 0) + 1
                            crit_name = obj.get('name', obj.get('identifier', 'Unnamed'))[:40]
                            enriched_items.append({'type': 'EligibilityCriterion', 'name': crit_name, 'category': cat_text, 'nci_code': nci_code})
            
            # Enrich study arm type
            if instance_type == 'StudyArm' and 'type' in obj:
                arm_type = obj['type']
                type_text = ''
                if isinstance(arm_type, dict):
                    type_text = arm_type.get('decode') or arm_type.get('code', '')
                elif isinstance(arm_type, str):
                    type_text = arm_type
                
                nci_code = _find_code(type_text, "armType")
                if nci_code:
                    code_obj = _get_code_object(nci_code, client)
                    if code_obj:
                        obj['type'] = code_obj
                        enriched_count += 1
                        by_type['StudyArm'] = by_type.get('StudyArm', 0) + 1
                        arm_name = obj.get('name', 'Unnamed Arm')
                        enriched_items.append({'type': 'StudyArm', 'name': arm_name, 'arm_type': type_text, 'nci_code': nci_code})
            
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
            'enriched_items': enriched_items,
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
