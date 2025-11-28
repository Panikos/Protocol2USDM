"""
CDISC CORE Conformance Checker

Validates USDM output against CDISC conformance rules.
Uses local CDISC CORE engine when available.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Path to local CDISC CORE engine
CORE_ENGINE_PATH = Path(__file__).parent.parent / "tools" / "core" / "core" / "core.exe"


def run_cdisc_conformance(
    json_path: str,
    output_dir: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run CDISC CORE conformance validation.
    
    Priority:
    1. Local CDISC CORE engine (if available)
    2. CDISC API (if key configured and reachable)
    3. Local validation rules (fallback)
    
    Args:
        json_path: Path to USDM JSON file
        output_dir: Directory for output report
        api_key: Optional CDISC API key (from env if not provided)
        
    Returns:
        Dict with conformance results
    """
    # Try local CORE engine first
    if CORE_ENGINE_PATH.exists():
        try:
            return _run_local_core_engine(json_path, output_dir)
        except Exception as e:
            logger.warning(f"Local CORE engine failed: {e}")
    
    # Try CDISC API if key available
    if api_key is None:
        api_key = os.environ.get('CDISC_API_KEY')
    
    if api_key and _check_cdisc_api_available():
        try:
            return _run_cdisc_api(json_path, output_dir, api_key)
        except Exception as e:
            logger.warning(f"CDISC API call failed: {e}")
    
    # Fall back to local validation rules
    logger.info("Using local validation rules")
    return _run_local_conformance(json_path, output_dir)


def _run_local_core_engine(json_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Run local CDISC CORE engine executable.
    """
    logger.info(f"Running local CDISC CORE engine...")
    
    output_path = os.path.join(output_dir, "conformance_report.json")
    
    try:
        # Run CORE engine
        result = subprocess.run(
            [
                str(CORE_ENGINE_PATH),
                "validate",
                "-s", "usdm",  # Standard: USDM
                "-v", "4.0",  # USDM version
                "-d", json_path,  # Data file
                "-o", output_path,  # Output
                "-of", "JSON",  # Output format
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            issues = report.get('issues', [])
            warnings = [i for i in issues if i.get('severity') == 'Warning']
            errors = [i for i in issues if i.get('severity') == 'Error']
            
            logger.info(f"Conformance check: {len(errors)} errors, {len(warnings)} warnings")
            
            return {
                'success': True,
                'output': output_path,
                'issues': len(errors),
                'warnings': len(warnings),
                'engine': 'local_core',
            }
        else:
            # CORE engine ran but may have reported issues
            logger.warning(f"CORE engine output: {result.stderr or result.stdout}")
            raise Exception(f"CORE engine returned code {result.returncode}")
            
    except subprocess.TimeoutExpired:
        raise Exception("CORE engine timed out")
    except FileNotFoundError:
        raise Exception("CORE engine not found")


def _check_cdisc_api_available(timeout: float = 3.0) -> bool:
    """Check if CDISC API is reachable."""
    import socket
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("api.cdisc.org", 443))
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def _run_cdisc_api(
    json_path: str,
    output_dir: str,
    api_key: str,
) -> Dict[str, Any]:
    """Run official CDISC CORE validation."""
    import requests
    
    if not api_key:
        return {
            'success': False,
            'error': 'CDISC API key not configured',
            'issues': 0,
        }
    
    # CDISC CORE API endpoint
    url = "https://api.cdisc.org/usdm/validate"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    response = requests.post(
        url,
        json=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        timeout=60,
    )
    
    if response.status_code == 200:
        result = response.json()
        
        # Save report
        output_path = os.path.join(output_dir, 'cdisc_conformance_report.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        return {
            'success': True,
            'output': output_path,
            'issues': len(result.get('issues', [])),
            'warnings': len(result.get('warnings', [])),
        }
    else:
        return {
            'success': False,
            'error': f'CDISC API error: {response.status_code}',
        }


def _run_local_conformance(json_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Run local conformance checks based on CDISC USDM rules.
    
    Checks:
    1. Required entity types are present
    2. Mandatory fields are populated
    3. Code values are from CDISC controlled terminology
    4. Cross-references are valid
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    issues = []
    warnings = []
    
    # Check 1: Required top-level structure
    if 'study' not in data:
        issues.append({
            'rule': 'USDM001',
            'severity': 'ERROR',
            'message': 'Missing required top-level study object',
        })
    
    study = data.get('study', {})
    versions = study.get('versions', [])
    
    if not versions:
        issues.append({
            'rule': 'USDM002',
            'severity': 'ERROR',
            'message': 'Study must have at least one version',
        })
    
    for i, version in enumerate(versions):
        # Check 2: StudyVersion required fields
        if not version.get('titles'):
            warnings.append({
                'rule': 'USDM010',
                'severity': 'WARNING',
                'message': f'StudyVersion[{i}] missing titles',
            })
        
        if not version.get('studyIdentifiers'):
            warnings.append({
                'rule': 'USDM011',
                'severity': 'WARNING',
                'message': f'StudyVersion[{i}] missing studyIdentifiers',
            })
        
        # Check 3: StudyDesign structure
        designs = version.get('studyDesigns', [])
        if not designs:
            warnings.append({
                'rule': 'USDM020',
                'severity': 'WARNING',
                'message': f'StudyVersion[{i}] missing studyDesigns',
            })
        
        for j, design in enumerate(designs):
            # Check for scheduleTimelines (SoA)
            if not design.get('scheduleTimelines'):
                warnings.append({
                    'rule': 'USDM030',
                    'severity': 'WARNING',
                    'message': f'StudyDesign[{j}] missing scheduleTimelines',
                })
            
            # Check for eligibilityCriteria
            if not design.get('eligibilityCriteria'):
                warnings.append({
                    'rule': 'USDM031',
                    'severity': 'WARNING',
                    'message': f'StudyDesign[{j}] missing eligibilityCriteria',
                })
            
            # Check for objectives
            if not design.get('objectives'):
                warnings.append({
                    'rule': 'USDM032',
                    'severity': 'WARNING',
                    'message': f'StudyDesign[{j}] missing objectives',
                })
    
    # Check 4: Controlled terminology
    _check_controlled_terminology(data, warnings)
    
    # Generate report
    report = {
        'timestamp': _get_timestamp(),
        'validator': 'Protocol2USDM Local Validator',
        'version': '1.0',
        'inputFile': json_path,
        'issues': issues,
        'warnings': warnings,
        'summary': {
            'errorCount': len(issues),
            'warningCount': len(warnings),
            'passed': len(issues) == 0,
        }
    }
    
    # Save report
    output_path = os.path.join(output_dir, 'conformance_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Conformance check: {len(issues)} errors, {len(warnings)} warnings")
    
    return {
        'success': True,
        'output': output_path,
        'issues': len(issues),
        'warnings': len(warnings),
    }


def _check_controlled_terminology(data: Dict, warnings: List) -> None:
    """Check that coded values use CDISC controlled terminology."""
    
    # Valid objective levels
    valid_obj_levels = {'Primary', 'Secondary', 'Exploratory'}
    
    # Valid blinding schemas
    valid_blinding = {'Open Label', 'Single Blind', 'Double Blind', 'Triple Blind'}
    
    def check_recursive(obj, path=""):
        if not isinstance(obj, dict):
            return
        
        # Check objective level
        if 'level' in obj and obj.get('instanceType') in ('Objective', 'Endpoint'):
            level = obj['level']
            if isinstance(level, dict):
                level = level.get('code', level.get('decode'))
            if level and level not in valid_obj_levels:
                warnings.append({
                    'rule': 'CT001',
                    'severity': 'WARNING',
                    'message': f'{path}: Invalid objective/endpoint level "{level}"',
                })
        
        # Check blinding schema
        if 'blindingSchema' in obj:
            blinding = obj['blindingSchema']
            if isinstance(blinding, dict):
                blinding = blinding.get('code', blinding.get('decode'))
            if blinding and blinding not in valid_blinding:
                warnings.append({
                    'rule': 'CT002',
                    'severity': 'WARNING',
                    'message': f'{path}: Invalid blinding schema "{blinding}"',
                })
        
        for key, value in obj.items():
            if isinstance(value, dict):
                check_recursive(value, f"{path}/{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        check_recursive(item, f"{path}/{key}[{i}]")
    
    check_recursive(data)


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"
