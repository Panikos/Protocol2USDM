"""
USDM normalization functions.

Handles cleaning and standardizing USDM entity data.
"""

import re
from typing import Dict, List, Tuple
from core import standardize_ids


# Timing pattern for extracting timing from names
TIMING_PATTERN = re.compile(
    r'(Week\s*[-+]?\d+|Day\s*[-+]?\d+|±\s*\d+\s*(day|week)s?|'
    r'\(\s*Week\s*[-+]?\d+\s*\)|\(\s*Day\s*[-+]?\d+\s*\))',
    re.IGNORECASE
)

# Standard timing codes for normalization
TIMING_CODES = {
    'screening': 'C48262',  # Screening
    'baseline': 'C25213',   # Baseline
    'treatment': 'C25466',  # Treatment
    'follow-up': 'C48313',  # Follow-up
    'end of study': 'C68846',  # End of Study
}


def normalize_names_vs_timing(timeline: dict) -> int:
    """
    Enforce the naming vs. timing rule: extract timing patterns from entity names
    and move them to proper timing fields.
    
    Rules:
    - Encounter.name should NOT contain timing text like "Week -2", "Day 1"
    - Timing goes in Encounter.timing.windowLabel
    - PlannedTimepoint.name should be clean, timing goes to description
    
    Args:
        timeline: The timeline object containing encounters and plannedTimepoints
    
    Returns:
        Number of entities normalized
    """
    normalized_count = 0
    
    # Process Encounters
    for enc in timeline.get('encounters', []):
        name = enc.get('name', '')
        if not name:
            continue
        
        clean_name, timing_text = _extract_timing(name)
        if timing_text and clean_name != name:
            enc['name'] = clean_name
            
            # Move timing to windowLabel if not already present
            if 'timing' not in enc:
                enc['timing'] = {}
            if not enc['timing'].get('windowLabel'):
                enc['timing']['windowLabel'] = timing_text
            
            normalized_count += 1
    
    # Process PlannedTimepoints
    for pt in timeline.get('plannedTimepoints', []):
        name = pt.get('name', '')
        if not name:
            continue
        
        clean_name, timing_text = _extract_timing(name)
        if timing_text and clean_name != name:
            pt['name'] = clean_name
            
            # Move timing to description if not already present
            if not pt.get('description'):
                pt['description'] = timing_text
            
            normalized_count += 1
    
    return normalized_count


def _extract_timing(name: str) -> Tuple[str, str]:
    """
    Extract timing text from a name and return clean name and timing.
    
    Args:
        name: Entity name potentially containing timing
        
    Returns:
        Tuple of (clean_name, timing_text)
    """
    matches = TIMING_PATTERN.findall(name)
    if not matches:
        return name, ''
    
    # Get the timing text
    timing_text = matches[0][0] if isinstance(matches[0], tuple) else matches[0]
    
    # Clean the name by removing timing text
    clean_name = TIMING_PATTERN.sub('', name).strip()
    
    # Clean up extra spaces, dashes, and parentheses
    clean_name = re.sub(r'\s+', ' ', clean_name)
    clean_name = re.sub(r'\s*[-–—:]+\s*$', '', clean_name)
    clean_name = re.sub(r'^\s*[-–—:]+\s*', '', clean_name)
    clean_name = clean_name.strip('() ')
    
    return clean_name, timing_text.strip()


def normalize_timing_codes(timeline: dict) -> int:
    """
    Normalize timing codes in epochs and encounters.
    
    Maps common phase names to CDISC controlled terminology codes.
    
    Args:
        timeline: The timeline object
        
    Returns:
        Number of entities with codes added
    """
    codes_added = 0
    
    for epoch in timeline.get('epochs', []):
        name = (epoch.get('name') or '').lower()
        
        # Check for matching timing code
        for keyword, code in TIMING_CODES.items():
            if keyword in name and not epoch.get('code'):
                epoch['code'] = {
                    'code': code,
                    'codeSystem': 'NCI Thesaurus',
                    'codeSystemVersion': '24.02d',
                    'decode': epoch.get('name', ''),
                }
                codes_added += 1
                break
    
    return codes_added


def clean_entity_names(timeline: dict) -> int:
    """
    Clean entity names by removing extra whitespace and invalid characters.
    
    Args:
        timeline: The timeline object
        
    Returns:
        Number of entities cleaned
    """
    cleaned = 0
    
    entity_types = ['activities', 'encounters', 'plannedTimepoints', 'epochs', 'activityGroups']
    
    for entity_type in entity_types:
        for entity in timeline.get(entity_type, []):
            name = entity.get('name', '')
            if not name:
                continue
            
            # Clean name
            clean = re.sub(r'\s+', ' ', name).strip()
            clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)  # Remove control chars
            
            if clean != name:
                entity['name'] = clean
                cleaned += 1
    
    return cleaned
