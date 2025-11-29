"""
USDM OpenAPI Schema Validator

⚠️ DEPRECATION NOTICE: This validator is being phased out in favor of the 
official `usdm` Python package (pip install usdm) which provides authoritative 
Pydantic-based validation. This module is kept for:
    - Backward compatibility
    - Quick programmatic fixes via llm_schema_fixer.py
    - Fallback when usdm package is not installed

For authoritative validation, use:
    from validation.usdm_validator import validate_usdm_dict, validate_usdm_file

This module validates USDM JSON output against the USDM v4.0 OpenAPI specification.
Provides detailed issue reports with fix suggestions.

Architecture:
    1. Load and parse USDM_API.json (OpenAPI 3.1 spec)
    2. Extract JSON Schema for components (e.g., Wrapper-Input, Activity-Input)
    3. Validate data against schema using jsonschema
    4. Return structured issues with paths, expected vs actual, and fix hints
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for schema validation issues."""
    ERROR = "error"          # Must be fixed (violates schema)
    WARNING = "warning"      # Should be fixed (non-standard)
    INFO = "info"           # Informational (enhancement possible)


class IssueCategory(Enum):
    """Categories of schema issues for routing to appropriate fixers."""
    MISSING_REQUIRED = "missing_required"    # Required field is missing
    INVALID_TYPE = "invalid_type"            # Wrong data type
    INVALID_VALUE = "invalid_value"          # Value not in allowed enum
    INVALID_FORMAT = "invalid_format"        # Format mismatch (uuid, date, etc.)
    UNKNOWN_PROPERTY = "unknown_property"    # Extra property not in schema
    INVALID_REF = "invalid_ref"              # Broken ID reference
    STRUCTURAL = "structural"                # Wrong nesting/structure


@dataclass
class SchemaIssue:
    """A single schema validation issue."""
    path: str                        # JSON path to the issue (e.g., "study.versions[0].id")
    category: IssueCategory
    severity: IssueSeverity
    message: str                     # Human-readable description
    expected: Optional[str] = None   # What the schema expects
    actual: Optional[str] = None     # What was found
    fix_hint: Optional[str] = None   # Suggested fix for LLM
    auto_fixable: bool = True        # Whether LLM can fix this
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "fixHint": self.fix_hint,
            "autoFixable": self.auto_fixable,
        }


@dataclass
class ValidationResult:
    """Result of OpenAPI schema validation."""
    valid: bool
    issues: List[SchemaIssue] = field(default_factory=list)
    entity_count: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    schema_version: str = "4.0"
    
    @property
    def fixable_issues(self) -> List[SchemaIssue]:
        """Issues that can potentially be auto-fixed by LLM."""
        return [i for i in self.issues if i.auto_fixable]
    
    @property  
    def unfixable_issues(self) -> List[SchemaIssue]:
        """Issues that require manual intervention."""
        return [i for i in self.issues if not i.auto_fixable]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "schemaVersion": self.schema_version,
            "summary": {
                "entityCount": self.entity_count,
                "errorsCount": self.errors_count,
                "warningsCount": self.warnings_count,
                "fixableCount": len(self.fixable_issues),
                "unfixableCount": len(self.unfixable_issues),
            },
            "issues": [i.to_dict() for i in self.issues],
        }


class OpenAPIValidator:
    """
    Validates USDM JSON against the official OpenAPI 3.1 specification.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize validator with OpenAPI schema.
        
        Args:
            schema_path: Path to USDM_API.json. If None, uses default location.
        """
        if schema_path is None:
            # Default to bundled schema
            schema_path = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "USDM OpenAPI schema", 
                "USDM_API.json"
            )
        
        self.schema_path = Path(schema_path)
        self._schema = None
        self._component_schemas = {}
        
    def _load_schema(self) -> Dict[str, Any]:
        """Load and cache the OpenAPI schema."""
        if self._schema is None:
            if not self.schema_path.exists():
                raise FileNotFoundError(f"USDM OpenAPI schema not found: {self.schema_path}")
            
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self._schema = json.load(f)
            
            # Extract component schemas
            self._component_schemas = self._schema.get('components', {}).get('schemas', {})
            logger.debug(f"Loaded OpenAPI schema with {len(self._component_schemas)} component schemas")
        
        return self._schema
    
    def _get_component_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific component schema by name."""
        self._load_schema()
        return self._component_schemas.get(name)
    
    def _resolve_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Resolve a $ref to its schema definition."""
        if not ref.startswith("#/components/schemas/"):
            return None
        schema_name = ref.split("/")[-1]
        return self._get_component_schema(schema_name)
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate USDM JSON data against the OpenAPI schema.
        
        Args:
            data: USDM JSON data (as dict or file path)
            
        Returns:
            ValidationResult with issues found
        """
        # Load data if path provided
        if isinstance(data, str):
            with open(data, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        self._load_schema()
        
        issues = []
        entity_count = 0
        
        # Get Wrapper-Input schema for top-level validation
        wrapper_schema = self._get_component_schema("Wrapper-Input")
        if not wrapper_schema:
            issues.append(SchemaIssue(
                path="$",
                category=IssueCategory.STRUCTURAL,
                severity=IssueSeverity.ERROR,
                message="Cannot find Wrapper-Input schema in OpenAPI spec",
                auto_fixable=False
            ))
            return ValidationResult(valid=False, issues=issues)
        
        # Validate top-level wrapper structure
        issues.extend(self._validate_wrapper(data))
        
        # Validate study structure
        if "study" in data:
            study_issues, count = self._validate_study(data["study"], "study")
            issues.extend(study_issues)
            entity_count += count
        
        # Count severities
        errors = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        
        return ValidationResult(
            valid=errors == 0,
            issues=issues,
            entity_count=entity_count,
            errors_count=errors,
            warnings_count=warnings,
        )
    
    def _validate_wrapper(self, data: Dict[str, Any]) -> List[SchemaIssue]:
        """Validate top-level Wrapper structure."""
        issues = []
        wrapper_schema = self._get_component_schema("Wrapper-Input")
        
        # Check required fields
        required = wrapper_schema.get("required", [])
        for field in required:
            if field not in data:
                issues.append(SchemaIssue(
                    path=f"$.{field}",
                    category=IssueCategory.MISSING_REQUIRED,
                    severity=IssueSeverity.ERROR,
                    message=f"Missing required field '{field}' in Wrapper",
                    expected=f"'{field}' is required by USDM v4.0",
                    fix_hint=f"Add the '{field}' field to the root object"
                ))
        
        # Validate usdmVersion format
        if "usdmVersion" in data:
            version = data["usdmVersion"]
            if not isinstance(version, str):
                issues.append(SchemaIssue(
                    path="$.usdmVersion",
                    category=IssueCategory.INVALID_TYPE,
                    severity=IssueSeverity.ERROR,
                    message="usdmVersion must be a string",
                    expected="string",
                    actual=type(version).__name__,
                    fix_hint="Convert usdmVersion to string format like '4.0'"
                ))
        
        return issues
    
    def _validate_study(self, study: Dict[str, Any], path: str) -> Tuple[List[SchemaIssue], int]:
        """Validate Study structure."""
        issues = []
        entity_count = 1  # Count Study itself
        
        study_schema = self._get_component_schema("Study-Input")
        if not study_schema:
            # Schema missing Study-Input - noted in investigation
            issues.append(SchemaIssue(
                path=path,
                category=IssueCategory.STRUCTURAL,
                severity=IssueSeverity.WARNING,
                message="Study-Input schema incomplete in OpenAPI spec",
                auto_fixable=False
            ))
        
        # Validate required Study fields
        study_required = ["name", "instanceType"] if study_schema else ["name"]
        for field in study_required:
            if field not in study:
                issues.append(SchemaIssue(
                    path=f"{path}.{field}",
                    category=IssueCategory.MISSING_REQUIRED,
                    severity=IssueSeverity.ERROR,
                    message=f"Missing required field '{field}' in Study",
                    expected=f"Study must have '{field}'",
                    fix_hint=f"Add '{field}' field. For instanceType, use 'Study'"
                ))
        
        # Validate instanceType if present
        if "instanceType" in study and study["instanceType"] != "Study":
            issues.append(SchemaIssue(
                path=f"{path}.instanceType",
                category=IssueCategory.INVALID_VALUE,
                severity=IssueSeverity.ERROR,
                message=f"Invalid instanceType: expected 'Study', got '{study['instanceType']}'",
                expected="Study",
                actual=study["instanceType"],
                fix_hint="Set instanceType to 'Study'"
            ))
        
        # Validate versions array
        if "versions" in study:
            if not isinstance(study["versions"], list):
                issues.append(SchemaIssue(
                    path=f"{path}.versions",
                    category=IssueCategory.INVALID_TYPE,
                    severity=IssueSeverity.ERROR,
                    message="'versions' must be an array",
                    expected="array",
                    actual=type(study["versions"]).__name__
                ))
            else:
                for i, version in enumerate(study["versions"]):
                    version_path = f"{path}.versions[{i}]"
                    version_issues, count = self._validate_study_version(version, version_path)
                    issues.extend(version_issues)
                    entity_count += count
        
        return issues, entity_count
    
    def _validate_study_version(self, version: Dict[str, Any], path: str) -> Tuple[List[SchemaIssue], int]:
        """Validate StudyVersion structure."""
        issues = []
        entity_count = 1  # Count StudyVersion itself
        
        # StudyVersion required fields per OpenAPI schema
        required_fields = ["id", "versionIdentifier", "rationale", "titles", "studyIdentifiers", "instanceType"]
        
        for field in required_fields:
            if field not in version:
                # Determine if this is a critical error or just missing data
                severity = IssueSeverity.ERROR if field in ["id", "instanceType"] else IssueSeverity.WARNING
                issues.append(SchemaIssue(
                    path=f"{path}.{field}",
                    category=IssueCategory.MISSING_REQUIRED,
                    severity=severity,
                    message=f"Missing required field '{field}' in StudyVersion",
                    expected=f"StudyVersion requires '{field}'",
                    fix_hint=self._get_fix_hint_for_field(field)
                ))
        
        # Validate instanceType
        if "instanceType" in version and version["instanceType"] != "StudyVersion":
            issues.append(SchemaIssue(
                path=f"{path}.instanceType",
                category=IssueCategory.INVALID_VALUE,
                severity=IssueSeverity.ERROR,
                message=f"Invalid instanceType: expected 'StudyVersion'",
                expected="StudyVersion",
                actual=version.get("instanceType"),
                fix_hint="Set instanceType to 'StudyVersion'"
            ))
        
        # Check for non-standard 'timeline' key (should be studyDesigns)
        if "timeline" in version:
            issues.append(SchemaIssue(
                path=f"{path}.timeline",
                category=IssueCategory.UNKNOWN_PROPERTY,
                severity=IssueSeverity.WARNING,
                message="'timeline' is not a standard USDM property - data should be in 'studyDesigns'",
                expected="studyDesigns",
                actual="timeline",
                fix_hint="Move timeline contents into studyDesigns[0] structure"
            ))
        
        # Validate studyDesigns if present
        if "studyDesigns" in version:
            for i, design in enumerate(version.get("studyDesigns", [])):
                design_path = f"{path}.studyDesigns[{i}]"
                design_issues, count = self._validate_study_design(design, design_path)
                issues.extend(design_issues)
                entity_count += count
        
        # Validate titles array
        if "titles" in version:
            for i, title in enumerate(version.get("titles", [])):
                title_path = f"{path}.titles[{i}]"
                issues.extend(self._validate_entity(title, title_path, "StudyTitle-Input"))
                entity_count += 1
        
        return issues, entity_count
    
    def _validate_study_design(self, design: Dict[str, Any], path: str) -> Tuple[List[SchemaIssue], int]:
        """Validate StudyDesign structure (Interventional or Observational)."""
        issues = []
        entity_count = 1
        
        # Check instanceType to determine schema
        instance_type = design.get("instanceType", "")
        valid_types = ["InterventionalStudyDesign", "ObservationalStudyDesign"]
        
        if instance_type not in valid_types:
            issues.append(SchemaIssue(
                path=f"{path}.instanceType",
                category=IssueCategory.INVALID_VALUE,
                severity=IssueSeverity.ERROR,
                message=f"Invalid StudyDesign instanceType",
                expected=f"One of: {valid_types}",
                actual=instance_type or "(missing)",
                fix_hint="Set instanceType to 'InterventionalStudyDesign' or 'ObservationalStudyDesign'"
            ))
        
        # Required fields for StudyDesign
        if "id" not in design:
            issues.append(SchemaIssue(
                path=f"{path}.id",
                category=IssueCategory.MISSING_REQUIRED,
                severity=IssueSeverity.ERROR,
                message="StudyDesign missing required 'id' field",
                fix_hint="Add unique id like 'sd_1'"
            ))
        
        # Validate nested entities
        entity_arrays = {
            "activities": "Activity-Input",
            "encounters": "Encounter-Input", 
            "epochs": "Epoch-Input",
            "studyArms": "StudyArm-Input",
            "studyCells": "StudyCell-Input",
            "objectives": "Objective-Input",
            "endpoints": "Endpoint-Input",
        }
        
        for array_name, schema_name in entity_arrays.items():
            if array_name in design:
                for i, item in enumerate(design[array_name]):
                    item_path = f"{path}.{array_name}[{i}]"
                    issues.extend(self._validate_entity(item, item_path, schema_name))
                    entity_count += 1
        
        return issues, entity_count
    
    def _validate_entity(self, entity: Dict[str, Any], path: str, schema_name: str) -> List[SchemaIssue]:
        """Validate a single entity against its schema."""
        issues = []
        schema = self._get_component_schema(schema_name)
        
        if not schema:
            return issues  # Can't validate without schema
        
        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in entity:
                issues.append(SchemaIssue(
                    path=f"{path}.{field}",
                    category=IssueCategory.MISSING_REQUIRED,
                    severity=IssueSeverity.ERROR,
                    message=f"Missing required field '{field}'",
                    expected=f"Required by {schema_name}",
                    fix_hint=self._get_fix_hint_for_field(field)
                ))
        
        # Validate instanceType matches expected
        expected_type = schema_name.replace("-Input", "").replace("-Output", "")
        actual_type = entity.get("instanceType")
        if actual_type and actual_type != expected_type:
            issues.append(SchemaIssue(
                path=f"{path}.instanceType",
                category=IssueCategory.INVALID_VALUE,
                severity=IssueSeverity.ERROR,
                message=f"instanceType mismatch",
                expected=expected_type,
                actual=actual_type,
                fix_hint=f"Set instanceType to '{expected_type}'"
            ))
        
        # Validate property types
        properties = schema.get("properties", {})
        for prop_name, prop_value in entity.items():
            if prop_name in properties:
                prop_schema = properties[prop_name]
                type_issues = self._validate_property_type(
                    prop_value, prop_schema, f"{path}.{prop_name}"
                )
                issues.extend(type_issues)
        
        return issues
    
    def _validate_property_type(self, value: Any, schema: Dict, path: str) -> List[SchemaIssue]:
        """Validate a property value against its schema type."""
        issues = []
        
        # Handle $ref
        if "$ref" in schema:
            # Reference to another schema - would need recursive validation
            return issues
        
        # Handle anyOf (nullable types)
        if "anyOf" in schema:
            # Check if any of the types match
            return issues  # Simplified for now
        
        expected_type = schema.get("type")
        if not expected_type:
            return issues
        
        actual_type = type(value).__name__
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type and not isinstance(value, expected_python_type):
            issues.append(SchemaIssue(
                path=path,
                category=IssueCategory.INVALID_TYPE,
                severity=IssueSeverity.ERROR,
                message=f"Type mismatch: expected {expected_type}, got {actual_type}",
                expected=expected_type,
                actual=actual_type,
                fix_hint=f"Convert value to {expected_type}"
            ))
        
        # Validate enum values
        if "enum" in schema and value not in schema["enum"]:
            issues.append(SchemaIssue(
                path=path,
                category=IssueCategory.INVALID_VALUE,
                severity=IssueSeverity.ERROR,
                message=f"Value not in allowed enum",
                expected=f"One of: {schema['enum']}",
                actual=str(value),
                fix_hint=f"Use one of the allowed values: {schema['enum']}"
            ))
        
        # Validate minLength for strings
        if expected_type == "string" and "minLength" in schema:
            if isinstance(value, str) and len(value) < schema["minLength"]:
                issues.append(SchemaIssue(
                    path=path,
                    category=IssueCategory.INVALID_VALUE,
                    severity=IssueSeverity.ERROR,
                    message=f"String too short: minimum length is {schema['minLength']}",
                    expected=f"minLength: {schema['minLength']}",
                    actual=f"length: {len(value)}",
                    fix_hint=f"Provide a non-empty string value"
                ))
        
        return issues
    
    def _get_fix_hint_for_field(self, field: str) -> str:
        """Get a helpful fix hint for common missing fields."""
        hints = {
            "id": "Generate a unique ID like 'entity_1' or use UUID format",
            "instanceType": "Add the instanceType field matching the entity type",
            "name": "Add a descriptive name for this entity",
            "versionIdentifier": "Add version identifier like '1.0' or 'Amendment 1'",
            "rationale": "Add rationale explaining this version (can be empty string)",
            "titles": "Add at least one StudyTitle object with id, text, and type",
            "studyIdentifiers": "Add at least one StudyIdentifier with id and text",
            "text": "Add the text content for this entity",
            "category": "Add the category code (e.g., 'Inclusion', 'Exclusion')",
            "level": "Add level code (e.g., 'Primary', 'Secondary', 'Exploratory')",
        }
        return hints.get(field, f"Add the required '{field}' field")


def validate_usdm(data: Any, schema_path: Optional[str] = None) -> ValidationResult:
    """
    Convenience function to validate USDM data.
    
    Args:
        data: USDM JSON data (dict or file path)
        schema_path: Optional path to USDM_API.json
        
    Returns:
        ValidationResult with issues found
    """
    validator = OpenAPIValidator(schema_path)
    return validator.validate(data)


if __name__ == "__main__":
    # Test the validator
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python openapi_validator.py <usdm_json_file>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    result = validate_usdm(sys.argv[1])
    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(0 if result.valid else 1)
