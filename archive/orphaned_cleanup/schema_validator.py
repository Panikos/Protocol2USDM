"""
USDM Schema Validator

Validates USDM JSON against the v4.0 schema specification.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Required fields by instance type
REQUIRED_FIELDS = {
    'Study': ['id'],
    'StudyVersion': ['id'],
    'StudyDesign': ['id'],
    'StudyTitle': ['id', 'text', 'type'],
    'StudyIdentifier': ['id', 'text'],
    'Organization': ['id', 'name'],
    'EligibilityCriterion': ['id', 'category'],
    'EligibilityCriterionItem': ['id', 'text'],
    'Objective': ['id', 'text', 'level'],
    'Endpoint': ['id', 'text', 'level'],
    'StudyArm': ['id', 'name'],
    'StudyCohort': ['id', 'name'],
    'StudyIntervention': ['id', 'name'],
    'ScheduleTimeline': ['id'],
    'Encounter': ['id', 'name'],
    'Activity': ['id', 'name'],
    'ScheduledActivityInstance': ['id'],
    'NarrativeContent': ['id', 'name'],
    'Abbreviation': ['id', 'abbreviatedText', 'expandedText'],
    'StudyAmendment': ['id', 'number'],
}

# Valid values for coded fields
VALID_CODES = {
    'objectiveLevel': ['Primary', 'Secondary', 'Exploratory'],
    'endpointLevel': ['Primary', 'Secondary', 'Exploratory'],
    'criterionCategory': ['Inclusion', 'Exclusion'],
    'blindingSchema': ['Open Label', 'Single Blind', 'Double Blind', 'Triple Blind'],
}


def validate_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate USDM data against schema requirements.
    
    Args:
        data: USDM JSON data (dict or file path)
        
    Returns:
        Dict with validation results:
        {
            'valid': bool,
            'issues': List of issue descriptions,
            'warnings': List of warnings,
            'entityCount': int,
        }
    """
    if isinstance(data, str):
        # Load from file
        with open(data, 'r', encoding='utf-8') as f:
            data = json.load(f)
    
    issues = []
    warnings = []
    entity_count = 0
    
    def validate_entity(obj: Dict, path: str = ""):
        nonlocal entity_count
        
        if not isinstance(obj, dict):
            return
        
        instance_type = obj.get('instanceType')
        
        if instance_type:
            entity_count += 1
            
            # Check required fields
            if instance_type in REQUIRED_FIELDS:
                for field in REQUIRED_FIELDS[instance_type]:
                    if field not in obj or obj[field] is None:
                        issues.append(f"{path}/{instance_type}: Missing required field '{field}'")
            
            # Validate ID format
            if 'id' in obj and obj['id']:
                if not isinstance(obj['id'], str):
                    issues.append(f"{path}/{instance_type}: ID must be a string")
                elif len(obj['id']) == 0:
                    issues.append(f"{path}/{instance_type}: ID cannot be empty")
        
        # Recurse into nested objects
        for key, value in obj.items():
            if isinstance(value, dict):
                validate_entity(value, f"{path}/{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        validate_entity(item, f"{path}/{key}[{i}]")
    
    # Validate top-level structure
    if 'study' not in data:
        issues.append("Missing required top-level 'study' object")
    else:
        validate_entity(data['study'], "study")
    
    # Check for USDM version
    if 'usdmVersion' not in data:
        warnings.append("Missing 'usdmVersion' field - recommended for compatibility")
    
    # Check study has versions
    if 'study' in data:
        versions = data['study'].get('versions', [])
        if not versions:
            issues.append("Study must have at least one version")
    
    result = {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'entityCount': entity_count,
    }
    
    logger.info(f"Schema validation: {'PASSED' if result['valid'] else 'FAILED'} "
                f"({len(issues)} issues, {len(warnings)} warnings)")
    
    return result


def validate_references(data: Dict[str, Any]) -> List[str]:
    """
    Validate that all ID references point to existing entities.
    
    Returns list of broken reference errors.
    """
    # Collect all IDs
    all_ids = set()
    references = []  # List of (path, ref_id)
    
    def collect_ids(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return
        
        if 'id' in obj and obj['id']:
            all_ids.add(obj['id'])
        
        # Check for reference fields
        for key, value in obj.items():
            if key.endswith('Id') and isinstance(value, str):
                references.append((path, value))
            elif key.endswith('Ids') and isinstance(value, list):
                for ref in value:
                    if isinstance(ref, str):
                        references.append((path, ref))
            elif isinstance(value, dict):
                collect_ids(value, f"{path}/{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        collect_ids(item, f"{path}/{key}[{i}]")
    
    collect_ids(data)
    
    # Check references
    broken = []
    for path, ref_id in references:
        if ref_id and ref_id not in all_ids:
            broken.append(f"{path}: Reference to non-existent ID '{ref_id}'")
    
    return broken
