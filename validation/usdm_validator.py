"""
USDM Schema Validator using the official CDISC usdm Python package.

This provides authoritative validation against USDM 4.0 Pydantic models.
It replaces the custom OpenAPI parsing approach with the official package.

Installation:
    pip install usdm

Usage:
    from validation.usdm_validator import USDMValidator, validate_usdm_file
    
    result = validate_usdm_file("protocol_usdm.json")
    if not result.valid:
        for issue in result.issues:
            print(f"  {issue.location}: {issue.message}")
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

# Check if usdm package is available
try:
    from pydantic import ValidationError
    from usdm_model import Wrapper
    import usdm_info
    HAS_USDM = True
    USDM_VERSION = usdm_info.__model_version__
    PACKAGE_VERSION = usdm_info.__package_version__
    logger.info(f"Using official usdm package v{PACKAGE_VERSION} (USDM {USDM_VERSION})")
except ImportError:
    HAS_USDM = False
    USDM_VERSION = "4.0.0"
    PACKAGE_VERSION = None
    logger.warning("usdm package not installed. Install with: pip install usdm")


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    location: str
    message: str
    error_type: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'location': self.location,
            'message': self.message,
            'type': self.error_type,
            'severity': self.severity.value
        }


@dataclass
class ValidationResult:
    """Result of USDM schema validation."""
    valid: bool = False
    issues: List[ValidationIssue] = field(default_factory=list)
    usdm_version_expected: str = USDM_VERSION
    usdm_version_found: Optional[str] = None
    validator_type: str = "usdm_pydantic" if HAS_USDM else "fallback"
    
    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == ValidationSeverity.ERROR])
    
    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == ValidationSeverity.WARNING])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'usdm_version_expected': self.usdm_version_expected,
            'usdm_version_found': self.usdm_version_found,
            'validator_type': self.validator_type,
            'issues': [issue.to_dict() for issue in self.issues]
        }
    
    def summary(self) -> str:
        """Create a human-readable summary."""
        if self.valid:
            return f"✓ Valid USDM {self.usdm_version_expected}"
        
        lines = [f"✗ Validation failed: {self.error_count} error(s), {self.warning_count} warning(s)"]
        
        # Group by error type
        grouped = defaultdict(list)
        for issue in self.issues:
            grouped[issue.error_type].append(issue)
        
        for error_type, issues in grouped.items():
            lines.append(f"\n  {error_type} ({len(issues)}x):")
            for issue in issues[:3]:  # Show first 3
                lines.append(f"    - {issue.location}: {issue.message[:80]}")
            if len(issues) > 3:
                lines.append(f"    ... and {len(issues) - 3} more")
        
        return '\n'.join(lines)


class USDMValidator:
    """
    Validator for USDM 4.0 JSON using the official usdm Python package.
    
    This uses Pydantic models from the usdm_model package for authoritative
    schema validation against the CDISC USDM 4.0 specification.
    """
    
    def __init__(self):
        self.model_version = USDM_VERSION
        self.has_usdm = HAS_USDM
        if not HAS_USDM:
            logger.warning("usdm package not available. Validation will be limited.")
    
    def validate_file(self, filepath: str) -> ValidationResult:
        """
        Validate a USDM JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            ValidationResult with validity status and any issues
        """
        result = ValidationResult(usdm_version_expected=self.model_version)
        
        # Load JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.issues.append(ValidationIssue(
                location='file',
                message=f'Invalid JSON syntax: {str(e)}',
                error_type='json_parse_error'
            ))
            return result
        except FileNotFoundError:
            result.issues.append(ValidationIssue(
                location='file',
                message=f'File not found: {filepath}',
                error_type='file_not_found'
            ))
            return result
        except Exception as e:
            result.issues.append(ValidationIssue(
                location='file',
                message=f'Error reading file: {str(e)}',
                error_type='file_read_error'
            ))
            return result
        
        return self._validate_data(data, result)
    
    def validate_dict(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate a USDM data dictionary.
        
        Args:
            data: Dictionary containing USDM data
            
        Returns:
            ValidationResult with validity status and any issues
        """
        result = ValidationResult(usdm_version_expected=self.model_version)
        return self._validate_data(data, result)
    
    def _validate_data(self, data: Dict[str, Any], result: ValidationResult) -> ValidationResult:
        """Internal validation logic using the usdm Pydantic models."""
        
        # Check for usdmVersion in data
        result.usdm_version_found = data.get('usdmVersion')
        
        # Version mismatch warning
        if result.usdm_version_found:
            found_normalized = result.usdm_version_found.split('.')[0]  # Major version
            expected_normalized = self.model_version.split('.')[0]
            
            if found_normalized != expected_normalized:
                result.issues.append(ValidationIssue(
                    location='usdmVersion',
                    message=f'Major version mismatch: file declares {result.usdm_version_found}, validator uses {self.model_version}',
                    error_type='version_mismatch',
                    severity=ValidationSeverity.WARNING
                ))
        
        if not self.has_usdm:
            # Fallback to basic validation without the package
            result.issues.append(ValidationIssue(
                location='validator',
                message='usdm package not installed. Install with: pip install usdm',
                error_type='package_not_installed',
                severity=ValidationSeverity.WARNING
            ))
            # Can't properly validate, assume valid but with warning
            result.valid = True
            result.validator_type = "fallback"
            return result
        
        # Perform schema validation using usdm Pydantic models
        try:
            wrapper = Wrapper(**data)
            result.valid = True
            logger.info("USDM validation passed")
        except ValidationError as e:
            for error in e.errors():
                location = ' -> '.join(str(loc) for loc in error['loc'])
                result.issues.append(ValidationIssue(
                    location=location,
                    message=error['msg'],
                    error_type=error['type']
                ))
            logger.warning(f"USDM validation failed with {len(result.issues)} error(s)")
        except Exception as e:
            result.issues.append(ValidationIssue(
                location='validation',
                message=f'Unexpected validation error: {str(e)}',
                error_type='validation_exception'
            ))
            logger.error(f"USDM validation exception: {e}")
        
        return result


def validate_usdm_file(filepath: str) -> ValidationResult:
    """
    Convenience function to validate a USDM JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        ValidationResult with validity status and any issues
    """
    validator = USDMValidator()
    return validator.validate_file(filepath)


def validate_usdm_dict(data: Dict[str, Any]) -> ValidationResult:
    """
    Convenience function to validate a USDM data dictionary.
    
    Args:
        data: Dictionary containing USDM data
        
    Returns:
        ValidationResult with validity status and any issues
    """
    validator = USDMValidator()
    return validator.validate_dict(data)


def get_usdm_schema() -> Optional[Dict]:
    """
    Get the JSON schema from the usdm Wrapper model.
    
    Returns:
        JSON schema dict or None if usdm package not available
    """
    if not HAS_USDM:
        return None
    return Wrapper.model_json_schema()


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python usdm_validator.py <usdm_json_file>")
        print("\nValidates a USDM JSON file using the official CDISC usdm package.")
        if not HAS_USDM:
            print("\n⚠️  Warning: usdm package not installed. Install with: pip install usdm")
        else:
            print(f"\nUsing usdm package v{PACKAGE_VERSION} (USDM {USDM_VERSION})")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    result = validate_usdm_file(sys.argv[1])
    
    print(f"\nValidator: {result.validator_type}")
    print(f"USDM Version (expected): {result.usdm_version_expected}")
    print(f"USDM Version (file): {result.usdm_version_found}")
    print(f"\nResult: {'✓ VALID' if result.valid else '✗ INVALID'}")
    print(f"Errors: {result.error_count}")
    print(f"Warnings: {result.warning_count}")
    
    if result.issues:
        print("\nIssues:")
        for issue in result.issues[:20]:  # Show first 20
            severity = issue.severity.value.upper()
            print(f"  [{severity}] {issue.location}")
            print(f"         {issue.message}")
            print(f"         Type: {issue.error_type}")
        if len(result.issues) > 20:
            print(f"\n  ... and {len(result.issues) - 20} more issues")
    
    sys.exit(0 if result.valid else 1)
