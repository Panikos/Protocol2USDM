"""
USDM enrichment functions.

Handles adding required fields and enriching entities with codes/metadata.
"""

from typing import Dict, List
from core import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION


def ensure_required_fields(data: dict) -> List[str]:
    """
    Ensure required USDM fields exist with sensible defaults.
    
    Adds:
    - study.versions array if missing
    - timeline object if missing
    - Required arrays (activities, plannedTimepoints, encounters, etc.)
    - Default epoch if none present
    - Wrapper-level fields (usdmVersion, systemName, systemVersion)
    
    Args:
        data: The USDM JSON object (Wrapper-Input format)
    
    Returns:
        List of fields that were added
    """
    added_fields = []
    
    # Ensure top-level wrapper fields
    if 'usdmVersion' not in data:
        data['usdmVersion'] = USDM_VERSION
        added_fields.append('usdmVersion')
    
    if 'systemName' not in data:
        data['systemName'] = SYSTEM_NAME
        added_fields.append('systemName')
    
    if 'systemVersion' not in data:
        data['systemVersion'] = SYSTEM_VERSION
        added_fields.append('systemVersion')
    
    # Ensure study object exists
    if 'study' not in data:
        data['study'] = {}
        added_fields.append('study')
    
    study = data['study']
    
    # Ensure versions array (support both 'versions' and legacy 'studyVersions')
    if 'versions' not in study and 'studyVersions' not in study:
        study['versions'] = [{}]
        added_fields.append('study.versions')
    
    # Normalize to 'versions' if 'studyVersions' is present
    if 'studyVersions' in study and 'versions' not in study:
        study['versions'] = study.pop('studyVersions')
    
    versions = study.get('versions', [])
    if not versions:
        study['versions'] = [{}]
        versions = study['versions']
        added_fields.append('study.versions[0]')
    
    version = versions[0]
    
    # Ensure timeline object
    if 'timeline' not in version:
        version['timeline'] = {}
        added_fields.append('timeline')
    
    timeline = version['timeline']
    
    # Ensure required arrays in timeline
    required_arrays = [
        'activities',
        'plannedTimepoints',
        'encounters',
        'activityTimepoints',
        'activityGroups',
        'epochs'
    ]
    
    for array_name in required_arrays:
        if array_name not in timeline:
            timeline[array_name] = []
            added_fields.append(f'timeline.{array_name}')
    
    # Ensure at least one epoch exists
    if not timeline.get('epochs'):
        timeline['epochs'] = [{
            'id': 'epoch_1',
            'name': 'Study Period',
            'instanceType': 'Epoch',
            'position': 1
        }]
        added_fields.append('timeline.epochs (default)')
    
    return added_fields


def enrich_with_codes(timeline: dict, entity_mapping: dict = None) -> int:
    """
    Enrich entities with CDISC codes based on entity mapping.
    
    Args:
        timeline: The timeline object
        entity_mapping: Optional mapping of entity names to codes
        
    Returns:
        Number of entities enriched
    """
    if not entity_mapping:
        return 0
    
    enriched = 0
    
    # Enrich activities
    activity_codes = entity_mapping.get('activities', {})
    for activity in timeline.get('activities', []):
        name = activity.get('name', '')
        if name in activity_codes and not activity.get('code'):
            activity['code'] = activity_codes[name]
            enriched += 1
    
    # Enrich encounters
    encounter_codes = entity_mapping.get('encounters', {})
    for encounter in timeline.get('encounters', []):
        name = encounter.get('name', '')
        if name in encounter_codes and not encounter.get('code'):
            encounter['code'] = encounter_codes[name]
            enriched += 1
    
    return enriched


def add_instance_types(timeline: dict) -> int:
    """
    Add instanceType field to all entities that need it.
    
    Args:
        timeline: The timeline object
        
    Returns:
        Number of instanceTypes added
    """
    added = 0
    
    type_mapping = {
        'activities': 'Activity',
        'plannedTimepoints': 'PlannedTimepoint',
        'encounters': 'Encounter',
        'epochs': 'Epoch',
        'activityGroups': 'ActivityGroup',
        'activityTimepoints': 'ActivityTimepoint',
    }
    
    for key, instance_type in type_mapping.items():
        for entity in timeline.get(key, []):
            if 'instanceType' not in entity:
                entity['instanceType'] = instance_type
                added += 1
    
    return added


def get_timeline(data: dict) -> dict:
    """
    Get the timeline object from USDM wrapper format.
    
    Args:
        data: USDM wrapper format data
        
    Returns:
        Timeline object
    """
    study = data.get('study', {})
    versions = study.get('versions', []) or study.get('studyVersions', [])
    
    if versions:
        return versions[0].get('timeline', {})
    
    return {}
