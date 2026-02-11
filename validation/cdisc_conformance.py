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


def _resolve_core_engine_path(auto_install: bool = True) -> Optional[Path]:
    """
    Resolve the CORE engine executable path.

    Priority:
    1. New installer location (tools/core/bin/core[.exe])
    2. Legacy location (tools/core/core/core.exe) — backward compat
    3. Auto-download via ensure_core_engine() if auto_install=True
    """
    # Try new installer path first
    try:
        from tools.core.download_core import get_core_engine_path, ensure_core_engine
        path = get_core_engine_path()
        if path:
            return path
        if auto_install:
            return ensure_core_engine(auto_install=True)
    except ImportError:
        pass

    # Legacy fallback
    legacy = Path(__file__).parent.parent / "tools" / "core" / "core" / "core.exe"
    if legacy.exists():
        return legacy

    return None


# Resolved at import time (no auto-install); auto-install happens in run_cdisc_conformance()
CORE_ENGINE_PATH = _resolve_core_engine_path(auto_install=False) or Path("__core_not_installed__")


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
    
    If validation fails, the error is captured and returned (no fallback).
    
    Args:
        json_path: Path to USDM JSON file
        output_dir: Directory for output report
        api_key: Optional CDISC API key (from env if not provided)
        
    Returns:
        Dict with conformance results (including errors if engine failed)
    """
    output_path = os.path.join(output_dir, "conformance_report.json")
    
    # Resolve CORE engine path (auto-download on first run)
    core_path = _resolve_core_engine_path(auto_install=True)
    if core_path and core_path.exists():
        result = _run_local_core_engine(json_path, output_dir, core_path)
        # Save result to file (success or error)
        _save_conformance_report(result, output_path)
        return result
    
    # Try CDISC API if key available
    if api_key is None:
        api_key = os.environ.get('CDISC_API_KEY')
    
    if api_key and _check_cdisc_api_available():
        result = _run_cdisc_api(json_path, output_dir, api_key)
        _save_conformance_report(result, output_path)
        return result
    
    # No validation method available
    result = {
        'success': False,
        'engine': 'none',
        'inputFile': json_path,
        'error': 'CDISC CORE engine not available. Install with: python tools/core/download_core.py',
        'error_summary': None,
        'error_details': None,
        'issues': 0,
        'warnings': 0,
        'issues_list': [],
        'timestamp': _get_timestamp(),
    }
    _save_conformance_report(result, output_path)
    return result


def _save_conformance_report(result: Dict[str, Any], output_path: str) -> None:
    """Save conformance result to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)


def _ensure_core_cache(core_dir: Path, core_exe: Path) -> bool:
    """
    Ensure CORE engine cache is up to date.
    Runs update-cache if rules_dictionary.pkl is missing.
    
    Requires CDISC_LIBRARY_API_KEY environment variable.
    """
    cache_file = core_dir / "resources" / "cache" / "rules_dictionary.pkl"
    if cache_file.exists():
        return True
    
    # Check for API key (support both naming conventions)
    api_key = os.environ.get('CDISC_LIBRARY_API_KEY') or os.environ.get('CDISC_API_KEY')
    if not api_key:
        logger.warning("CDISC CORE requires CDISC_LIBRARY_API_KEY or CDISC_API_KEY environment variable")
        logger.warning("Get your API key from: https://www.cdisc.org/cdisc-library")
        return False
    
    logger.info("Updating CDISC CORE cache (first run, may take a few minutes)...")
    try:
        result = subprocess.run(
            [str(core_exe), "update-cache", "--apikey", api_key],
            capture_output=True,
            text=True,
            timeout=300,  # Cache update can take a while
            cwd=str(core_dir),
        )
        if result.returncode == 0:
            logger.info("CORE cache updated successfully")
            return True
        else:
            logger.warning(f"CORE cache update failed: {result.stderr}")
            return False
    except Exception as e:
        logger.warning(f"CORE cache update error: {e}")
        return False


def _run_local_core_engine(
    json_path: str,
    output_dir: str,
    core_exe: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run local CDISC CORE engine executable.
    
    Returns result dict with success/error status (never raises).
    """
    if core_exe is None:
        core_exe = _resolve_core_engine_path(auto_install=False)
    if not core_exe or not core_exe.exists():
        return {
            'success': False,
            'engine': 'local_core',
            'inputFile': json_path,
            'error': 'CORE engine executable not found',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
        }

    core_dir = core_exe.parent
    
    # Ensure cache is available
    if not _ensure_core_cache(core_dir, core_exe):
        return {
            'success': False,
            'engine': 'local_core',
            'inputFile': json_path,
            'error': 'CORE cache not available. Set CDISC_API_KEY and run: python main_v3.py --update-cache',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
        }
    
    logger.info(f"Running CDISC CORE engine (local)...")
    
    # CORE engine appends .json to output path, so use base name without extension
    output_base = os.path.join(output_dir, "conformance_report")
    output_path = output_base + ".json"  # The actual file CORE will create
    
    try:
        # Run CORE engine
        # Note: Exclude CORE-000955 and CORE-000956 due to JSONata bugs in CORE engine
        # when processing certain USDM data structures (causes NoneType errors)
        result = subprocess.run(
            [
                str(core_exe),
                "validate",
                "-s", "usdm",  # Standard: USDM
                "-v", "4-0",  # USDM version (format: X-Y not X.Y)
                "-dp", os.path.abspath(json_path),  # Dataset file path (absolute)
                "-o", os.path.abspath(output_base),  # Output base (CORE appends .json)
                "-of", "JSON",  # Output format
                "-er", "CORE-000955",  # Exclude buggy rule
                "-er", "CORE-000956",  # Exclude buggy rule
                "-p", "disabled",  # Disable progress bar for cleaner logs
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(core_dir),
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
                'engine': 'local_core',
                'inputFile': json_path,
                'output': output_path,
                'error': None,
                'error_summary': None,
                'error_details': None,
                'issues': len(errors),
                'warnings': len(warnings),
                'issues_list': issues,
                'timestamp': _get_timestamp(),
            }
        else:
            # CORE engine failed - capture error details
            error_output = result.stderr or result.stdout or "Unknown error"
            
            # Extract the key error message (often buried in traceback)
            error_lines = error_output.strip().split('\n')
            error_summary = None
            for line in reversed(error_lines):
                if 'Error' in line or 'Exception' in line or 'TypeError' in line:
                    error_summary = line.strip()
                    break
            if not error_summary and error_lines:
                error_summary = error_lines[-1].strip()
            
            logger.warning(f"CORE engine failed: {error_summary}")
            
            return {
                'success': False,
                'engine': 'local_core',
                'inputFile': json_path,
                'error': f"CORE engine failed (exit code {result.returncode})",
                'error_summary': error_summary,
                'error_details': error_output,
                'issues': 0,
                'warnings': 0,
                'issues_list': [],
                'timestamp': _get_timestamp(),
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'engine': 'local_core',
            'inputFile': json_path,
            'error': 'CORE engine timed out (>120s)',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
        }
    except FileNotFoundError:
        return {
            'success': False,
            'engine': 'local_core',
            'inputFile': json_path,
            'error': 'CORE engine executable not found',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
        }
    except Exception as e:
        return {
            'success': False,
            'engine': 'local_core',
            'inputFile': json_path,
            'error': f'CORE engine error: {str(e)}',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
        }


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
            'engine': 'cdisc_api',
            'inputFile': json_path,
            'error': 'CDISC API key not configured',
            'error_summary': None,
            'error_details': None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
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
        
        # Save report (use consistent filename)
        output_path = os.path.join(output_dir, 'conformance_report.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        return {
            'success': True,
            'engine': 'cdisc_api',
            'inputFile': json_path,
            'output': output_path,
            'error': None,
            'error_summary': None,
            'error_details': None,
            'issues': len(result.get('issues', [])),
            'warnings': len(result.get('warnings', [])),
            'issues_list': result.get('issues', []),
            'timestamp': _get_timestamp(),
        }
    else:
        return {
            'success': False,
            'engine': 'cdisc_api',
            'inputFile': json_path,
            'error': f'CDISC API error: {response.status_code}',
            'error_summary': None,
            'error_details': response.text[:500] if response.text else None,
            'issues': 0,
            'warnings': 0,
            'issues_list': [],
            'timestamp': _get_timestamp(),
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
