"""
Schema Safety Net Fixer

Provides programmatic fixes for USDM schema validation issues.
This is a SAFETY NET - most issues should be fixed upstream by:
  1. normalize_usdm_data() - type inference for Encounters, Arms, Epochs, Codes
  2. Extraction prompts - proper entity structure from LLM

This fixer handles edge cases that slip through:
    - Missing Study/StudyVersion required fields
    - Property renames (legacy compatibility)
    - Timeline -> studyDesigns migration

Note: LLM-based fixing has been deprecated and moved to:
    archive/validation_legacy/llm_schema_fixer_with_llm.py
"""

import json
import logging
import copy
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .openapi_validator import SchemaIssue, ValidationResult, IssueCategory, IssueSeverity, validate_usdm

logger = logging.getLogger(__name__)

# LLM utilities deprecated - programmatic fixes only
HAS_LLM = False


@dataclass
class FixResult:
    """Result of a schema fix attempt."""
    success: bool
    issue: SchemaIssue
    fix_applied: Optional[str] = None      # Description of fix applied
    error: Optional[str] = None            # Error if fix failed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "path": self.issue.path,
            "category": self.issue.category.value,
            "fixApplied": self.fix_applied,
            "error": self.error,
        }


@dataclass
class SchemaFixerResult:
    """Overall result of schema fixing process."""
    original_issues: int
    fixed_issues: int
    remaining_issues: int
    iterations: int
    fixes_applied: List[FixResult] = field(default_factory=list)
    unfixable_issues: List[SchemaIssue] = field(default_factory=list)
    final_validation: Optional[ValidationResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "originalIssues": self.original_issues,
                "fixedIssues": self.fixed_issues,
                "remainingIssues": self.remaining_issues,
                "iterations": self.iterations,
            },
            "fixesApplied": [f.to_dict() for f in self.fixes_applied],
            "unfixableIssues": [i.to_dict() for i in self.unfixable_issues],
            "finalValidation": self.final_validation.to_dict() if self.final_validation else None,
        }


# Schema fix prompt template
SCHEMA_FIX_PROMPT = """You are a USDM v4.0 schema expert. Fix the following JSON to comply with USDM specifications.

## CURRENT JSON (excerpt around issue):
```json
{context_json}
```

## SCHEMA ISSUES TO FIX:
{issues_list}

## USDM v4.0 REQUIREMENTS:
- Every entity needs 'id' (unique string) and 'instanceType' (matching entity type)
- Study requires: name, instanceType="Study"
- StudyVersion requires: id, versionIdentifier, rationale, titles[], studyIdentifiers[], instanceType="StudyVersion"
- Activities go inside studyDesigns[].activities, not in a 'timeline' object
- StudyDesign requires: id, instanceType="InterventionalStudyDesign" or "ObservationalStudyDesign"

## OUTPUT FORMAT:
Return ONLY a JSON object with the fixes:
{{
    "fixes": [
        {{
            "path": "<json path from issue>",
            "action": "set" | "add" | "rename" | "move",
            "value": <the value to set/add>,
            "description": "<what this fix does>"
        }}
    ]
}}

RULES:
- Only fix the specific issues listed
- Preserve all existing data
- Generate realistic placeholder values where needed (e.g., "Protocol Title" not "TODO")
- For moves, specify both source and destination paths
"""


class LLMSchemaFixer:
    """
    Uses LLM to automatically fix schema validation issues.
    """
    
    def __init__(self, model_name: str = "gemini-2.5-pro", max_iterations: int = 3):
        """
        Initialize the schema fixer.
        
        Args:
            model_name: LLM model to use for fixes
            max_iterations: Maximum fix iterations before giving up
        """
        self.model_name = model_name
        self.max_iterations = max_iterations
        self._llm_client = None
    
    def fix_schema_issues(
        self, 
        data: Dict[str, Any], 
        validation_result: ValidationResult,
        use_llm: bool = True,
    ) -> Tuple[Dict[str, Any], SchemaFixerResult]:
        """
        Attempt to fix schema issues in the data.
        
        Args:
            data: USDM JSON data
            validation_result: Initial validation result with issues
            use_llm: Whether to use LLM for complex fixes
            
        Returns:
            Tuple of (fixed_data, fixer_result)
        """
        # Make a deep copy to avoid modifying original
        fixed_data = copy.deepcopy(data)
        
        original_issues = len(validation_result.issues)
        all_fixes = []
        unfixable = []
        iterations = 0
        
        # ALWAYS run comprehensive Code object fixes first
        # This catches issues that OpenAPI validator misses but official usdm catches
        code_fixes = self._fix_all_code_objects(fixed_data)
        all_fixes.extend(code_fixes)
        if code_fixes:
            logger.info(f"Pre-fixed {len(code_fixes)} Code object issues")
        
        current_issues = validation_result.issues
        
        while iterations < self.max_iterations and current_issues:
            iterations += 1
            logger.info(f"Schema fix iteration {iterations}: {len(current_issues)} issues")
            
            # Separate fixable from unfixable
            fixable = [i for i in current_issues if i.auto_fixable]
            unfixable.extend([i for i in current_issues if not i.auto_fixable])
            
            if not fixable:
                break
            
            # Apply programmatic fixes first (fast, reliable)
            fixed_data, programmatic_fixes = self._apply_programmatic_fixes(fixed_data, fixable)
            all_fixes.extend(programmatic_fixes)
            
            # Filter out successfully fixed issues
            fixed_paths = {f.issue.path for f in programmatic_fixes if f.success}
            remaining = [i for i in fixable if i.path not in fixed_paths]
            
            # Use LLM for remaining complex fixes
            if remaining and use_llm and HAS_LLM:
                fixed_data, llm_fixes = self._apply_llm_fixes(fixed_data, remaining)
                all_fixes.extend(llm_fixes)
            
            # Re-validate
            new_validation = validate_usdm(fixed_data)
            current_issues = new_validation.fixable_issues
            
            # Check if we're making progress
            if len(current_issues) >= len(fixable):
                logger.warning("No progress made in fix iteration, stopping")
                break
        
        # Final validation
        final_validation = validate_usdm(fixed_data)
        unfixable.extend(final_validation.unfixable_issues)
        
        # Remove duplicates from unfixable
        seen_paths = set()
        unique_unfixable = []
        for issue in unfixable:
            if issue.path not in seen_paths:
                seen_paths.add(issue.path)
                unique_unfixable.append(issue)
        
        result = SchemaFixerResult(
            original_issues=original_issues,
            fixed_issues=sum(1 for f in all_fixes if f.success),
            remaining_issues=len(final_validation.issues),
            iterations=iterations,
            fixes_applied=all_fixes,
            unfixable_issues=unique_unfixable,
            final_validation=final_validation,
        )
        
        return fixed_data, result
    
    def _apply_programmatic_fixes(
        self, 
        data: Dict[str, Any], 
        issues: List[SchemaIssue]
    ) -> Tuple[Dict[str, Any], List[FixResult]]:
        """
        Apply programmatic fixes for common issues.
        These don't require LLM and are fast/reliable.
        """
        fixes = []
        
        # FIRST PASS: Comprehensive fixes for all Code objects in the JSON
        # This catches Code objects from LLM extraction that are missing required fields
        code_fixes = self._fix_all_code_objects(data)
        fixes.extend(code_fixes)
        
        # SECOND PASS: Fix individual issues
        for issue in issues:
            fix_result = self._try_programmatic_fix(data, issue)
            if fix_result:
                fixes.append(fix_result)
        
        return data, fixes
    
    def _fix_all_code_objects(self, data: Dict[str, Any]) -> List[FixResult]:
        """
        Recursively find and fix all Code objects in the JSON.
        Ensures all Code objects have: id, codeSystem, codeSystemVersion, instanceType
        """
        import uuid
        fixes = []
        
        def is_code_object(obj):
            """Check if dict looks like a Code object."""
            if not isinstance(obj, dict):
                return False
            return "code" in obj and ("decode" in obj or "codeSystem" in obj)
        
        def is_alias_code_object(obj):
            """Check if dict looks like an AliasCode object (blindingSchema)."""
            if not isinstance(obj, dict):
                return False
            return "standardCode" in obj or obj.get("instanceType") == "AliasCode"
        
        def fix_code(obj, path):
            """Fix a single Code object."""
            fixed = False
            if "id" not in obj:
                obj["id"] = str(uuid.uuid4())
                fixes.append(FixResult(True, SchemaIssue(
                    path=f"{path}.id", category=IssueCategory.MISSING_REQUIRED,
                    message="Added id", severity=IssueSeverity.ERROR
                ), f"Added id to Code at {path}"))
                fixed = True
            if "codeSystem" not in obj:
                obj["codeSystem"] = "http://www.cdisc.org"
                fixed = True
            if "codeSystemVersion" not in obj:
                obj["codeSystemVersion"] = "2024-09-27"
                fixes.append(FixResult(True, SchemaIssue(
                    path=f"{path}.codeSystemVersion", category=IssueCategory.MISSING_REQUIRED,
                    message="Added codeSystemVersion", severity=IssueSeverity.ERROR
                ), f"Added codeSystemVersion to Code at {path}"))
                fixed = True
            if "instanceType" not in obj:
                obj["instanceType"] = "Code"
                fixed = True
            return fixed
        
        def fix_alias_code(obj, path):
            """Fix an AliasCode object (e.g., blindingSchema)."""
            fixed = False
            if "id" not in obj:
                obj["id"] = str(uuid.uuid4())
                fixed = True
            if "instanceType" not in obj:
                obj["instanceType"] = "AliasCode"
                fixed = True
            # Check if standardCode needs to be created from top-level code fields
            if "standardCode" not in obj and "code" in obj:
                # Move code fields into standardCode
                obj["standardCode"] = {
                    "id": str(uuid.uuid4()),
                    "code": obj.pop("code"),
                    "decode": obj.pop("decode", obj.get("code")),
                    "codeSystem": obj.pop("codeSystem", "http://www.cdisc.org"),
                    "codeSystemVersion": obj.pop("codeSystemVersion", "2024-09-27"),
                    "instanceType": "Code"
                }
                fixed = True
            elif "standardCode" in obj:
                # Fix the standardCode if it exists
                fix_code(obj["standardCode"], f"{path}.standardCode")
            return fixed
        
        def fix_study_arm(obj, path):
            """Fix StudyArm required fields."""
            if obj.get("instanceType") == "StudyArm" or ("name" in obj and path.endswith("]")):
                # Only fix if it looks like a StudyArm
                if "dataOriginDescription" not in obj:
                    obj["dataOriginDescription"] = "Collected"
                if "dataOriginType" not in obj:
                    obj["dataOriginType"] = {
                        "id": str(uuid.uuid4()),
                        "code": "C70793",
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": "Collected",
                        "instanceType": "Code"
                    }
                if "type" not in obj:
                    # Infer type from arm name
                    name = obj.get("name", "").lower()
                    if "placebo" in name:
                        code, decode = "C49648", "Placebo Comparator Arm"
                    elif "active" in name or "comparator" in name:
                        code, decode = "C49647", "Active Comparator Arm"
                    elif "control" in name:
                        code, decode = "C174266", "No Intervention Arm"
                    else:
                        code, decode = "C174267", "Experimental Arm"
                    obj["type"] = {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": decode,
                        "instanceType": "Code"
                    }
        
        def walk_and_fix(obj, path="$"):
            """Recursively walk JSON and fix Code objects and required fields."""
            if isinstance(obj, dict):
                # Check for specific field types that should be Code/AliasCode
                for key, value in list(obj.items()):
                    full_path = f"{path}.{key}"
                    
                    # Handle arms array - fix StudyArm required fields
                    if key == "arms" and isinstance(value, list):
                        for i, arm in enumerate(value):
                            if isinstance(arm, dict):
                                fix_study_arm(arm, f"{full_path}[{i}]")
                                walk_and_fix(arm, f"{full_path}[{i}]")
                    # blindingSchema should be AliasCode
                    elif key == "blindingSchema" and isinstance(value, dict):
                        fix_alias_code(value, full_path)
                    # type, model, dataOriginType, etc. should be Code
                    elif key in ("type", "model", "dataOriginType", "standardCode", "unit"):
                        if isinstance(value, dict) and is_code_object(value):
                            fix_code(value, full_path)
                    # Check if value is a Code-like object
                    elif isinstance(value, dict):
                        if is_code_object(value):
                            fix_code(value, full_path)
                        else:
                            walk_and_fix(value, full_path)
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            walk_and_fix(item, f"{full_path}[{i}]")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk_and_fix(item, f"{path}[{i}]")
        
        walk_and_fix(data)
        return fixes
    
    def _try_programmatic_fix(self, data: Dict[str, Any], issue: SchemaIssue) -> Optional[FixResult]:
        """Try to programmatically fix a single issue."""
        
        try:
            # Fix missing Study fields
            if issue.path == "$.study.name" and issue.category == IssueCategory.MISSING_REQUIRED:
                if "study" in data:
                    # Try to derive name from titles or identifiers
                    name = self._derive_study_name(data)
                    data["study"]["name"] = name
                    return FixResult(True, issue, f"Set study.name to '{name}'")
            
            if issue.path == "$.study.instanceType" and issue.category == IssueCategory.MISSING_REQUIRED:
                if "study" in data:
                    data["study"]["instanceType"] = "Study"
                    return FixResult(True, issue, "Set study.instanceType to 'Study'")
            
            # Fix missing StudyVersion fields
            if "versions[" in issue.path:
                version_match = self._extract_version_index(issue.path)
                if version_match is not None:
                    versions = data.get("study", {}).get("versions", [])
                    if version_match < len(versions):
                        version = versions[version_match]
                        
                        if issue.path.endswith(".id"):
                            version["id"] = f"sv_{version_match + 1}"
                            return FixResult(True, issue, f"Set version id to 'sv_{version_match + 1}'")
                        
                        if issue.path.endswith(".instanceType"):
                            version["instanceType"] = "StudyVersion"
                            return FixResult(True, issue, "Set instanceType to 'StudyVersion'")
                        
                        if issue.path.endswith(".versionIdentifier"):
                            version["versionIdentifier"] = "1.0"
                            return FixResult(True, issue, "Set versionIdentifier to '1.0'")
                        
                        if issue.path.endswith(".rationale"):
                            version["rationale"] = "Initial protocol version"
                            return FixResult(True, issue, "Set rationale to default value")
                        
                        if issue.path.endswith(".titles"):
                            # Create from existing data if possible
                            titles = self._derive_titles(data, version)
                            version["titles"] = titles
                            return FixResult(True, issue, f"Added {len(titles)} title(s)")
                        
                        if issue.path.endswith(".studyIdentifiers"):
                            identifiers = self._derive_identifiers(data, version)
                            version["studyIdentifiers"] = identifiers
                            return FixResult(True, issue, f"Added {len(identifiers)} identifier(s)")
            
            # Fix missing studyDesign instanceType
            if "studyDesigns[" in issue.path and issue.path.endswith(".instanceType"):
                design_idx = self._extract_design_index(issue.path)
                if design_idx is not None:
                    versions = data.get("study", {}).get("versions", [])
                    for version in versions:
                        designs = version.get("studyDesigns", [])
                        if design_idx < len(designs):
                            designs[design_idx]["instanceType"] = "InterventionalStudyDesign"
                            return FixResult(True, issue, "Set instanceType to 'InterventionalStudyDesign'")
            
            # Fix missing StudyArm required fields
            if "studyArms[" in issue.path:
                if issue.path.endswith(".dataOriginDescription"):
                    arm = self._navigate_to_parent(data, issue.path)
                    if arm:
                        arm["dataOriginDescription"] = "Primary data collected from study participants"
                        return FixResult(True, issue, "Set dataOriginDescription to default")
                
                if issue.path.endswith(".dataOriginType"):
                    arm = self._navigate_to_parent(data, issue.path)
                    if arm:
                        arm["dataOriginType"] = {
                            "code": "C70793",
                            "codeSystem": "NCI Thesaurus",
                            "decode": "Collected"
                        }
                        return FixResult(True, issue, "Set dataOriginType to 'Collected'")
            
            # Fix missing Encounter.type (required field)
            if "encounters[" in issue.path and issue.path.endswith(".type"):
                encounter = self._navigate_to_parent(data, issue.path)
                if encounter:
                    # Infer type from encounter name
                    name = encounter.get("name", "").lower()
                    if "screen" in name:
                        enc_type = {"code": "C48262", "codeSystem": "http://www.cdisc.org", "decode": "Screening"}
                    elif "baseline" in name or "day 1" in name or "day1" in name:
                        enc_type = {"code": "C82517", "codeSystem": "http://www.cdisc.org", "decode": "Baseline"}
                    elif "follow" in name:
                        enc_type = {"code": "C99158", "codeSystem": "http://www.cdisc.org", "decode": "Follow-up"}
                    elif "end" in name or "eos" in name or "completion" in name:
                        enc_type = {"code": "C126070", "codeSystem": "http://www.cdisc.org", "decode": "End of Study"}
                    elif "early" in name or "discontin" in name or "termination" in name:
                        enc_type = {"code": "C49631", "codeSystem": "http://www.cdisc.org", "decode": "Early Termination"}
                    elif "unscheduled" in name:
                        enc_type = {"code": "C99157", "codeSystem": "http://www.cdisc.org", "decode": "Unscheduled"}
                    else:
                        enc_type = {"code": "C99156", "codeSystem": "http://www.cdisc.org", "decode": "Scheduled Visit"}
                    encounter["type"] = enc_type
                    return FixResult(True, issue, f"Set encounter type to '{enc_type['decode']}'")
            
            # Fix missing entity IDs
            if issue.path.endswith(".id") and issue.category == IssueCategory.MISSING_REQUIRED:
                # Navigate to the entity and add an ID
                entity = self._navigate_to_path(data, issue.path.rsplit(".", 1)[0])
                if entity is not None:
                    new_id = self._generate_id_from_path(issue.path)
                    entity["id"] = new_id
                    return FixResult(True, issue, f"Set id to '{new_id}'")
            
            # Handle timeline -> studyDesigns migration
            if issue.category == IssueCategory.UNKNOWN_PROPERTY and "timeline" in issue.path:
                return self._migrate_timeline_to_study_designs(data, issue)
            
            # ===============================================================
            # USDM v4.0 SCHEMA COMPLIANCE FIXES
            # ===============================================================
            
            # Fix InterventionalStudyDesign required fields
            if "studyDesigns[" in issue.path:
                design = self._navigate_to_design(data, issue.path)
                if design:
                    # Fix missing name
                    if issue.path.endswith(".name") and issue.category == IssueCategory.MISSING_REQUIRED:
                        design["name"] = "Study Design"
                        return FixResult(True, issue, "Set studyDesign.name to 'Study Design'")
                    
                    # Fix missing rationale
                    if issue.path.endswith(".rationale") and issue.category == IssueCategory.MISSING_REQUIRED:
                        design["rationale"] = "Protocol-defined study design for investigating efficacy and safety"
                        return FixResult(True, issue, "Set studyDesign.rationale to default value")
                    
                    # Fix missing model (Code object)
                    if issue.path.endswith(".model") and issue.category == IssueCategory.MISSING_REQUIRED:
                        # Infer model from study design characteristics
                        arms = design.get("arms", design.get("studyArms", []))
                        if len(arms) >= 2:
                            design["model"] = {
                                "id": "code_model_1",
                                "code": "C82639",
                                "codeSystem": "http://www.cdisc.org",
                                "codeSystemVersion": "2024-09-27",
                                "decode": "Parallel Study",
                                "instanceType": "Code"
                            }
                        else:
                            design["model"] = {
                                "id": "code_model_1", 
                                "code": "C82638",
                                "codeSystem": "http://www.cdisc.org",
                                "codeSystemVersion": "2024-09-27",
                                "decode": "Single Group Study",
                                "instanceType": "Code"
                            }
                        return FixResult(True, issue, f"Set studyDesign.model to '{design['model']['decode']}'")
            
            # Fix property name: studyArms -> arms
            if issue.category == IssueCategory.UNKNOWN_PROPERTY and "studyArms" in issue.path:
                design = self._navigate_to_design(data, issue.path)
                if design and "studyArms" in design and "arms" not in design:
                    design["arms"] = design.pop("studyArms")
                    return FixResult(True, issue, "Renamed 'studyArms' to 'arms'")
            
            # Fix property name: studyDesignPopulation -> population
            if issue.category == IssueCategory.UNKNOWN_PROPERTY and "studyDesignPopulation" in issue.path:
                design = self._navigate_to_design(data, issue.path)
                if design and "studyDesignPopulation" in design and "population" not in design:
                    design["population"] = design.pop("studyDesignPopulation")
                    return FixResult(True, issue, "Renamed 'studyDesignPopulation' to 'population'")
            
            # Fix missing ScheduledActivityInstance.name
            if "instances[" in issue.path and issue.path.endswith(".name"):
                instance = self._navigate_to_parent(data, issue.path)
                if instance and issue.category == IssueCategory.MISSING_REQUIRED:
                    # Derive name from activityId and encounterId
                    act_id = instance.get("activityId", instance.get("activityIds", ["act"])[0] if instance.get("activityIds") else "act")
                    enc_id = instance.get("encounterId", "enc")
                    instance["name"] = f"{act_id}@{enc_id}"
                    return FixResult(True, issue, f"Set instance.name to '{instance['name']}'")
            
            # Fix incomplete Code objects (missing id, codeSystemVersion, instanceType)
            if issue.category == IssueCategory.MISSING_REQUIRED:
                # Check if this is a Code object field
                parent_path = issue.path.rsplit(".", 1)[0] if "." in issue.path else ""
                code_obj = self._navigate_to_path(data, parent_path)
                if code_obj and isinstance(code_obj, dict) and "code" in code_obj and "decode" in code_obj:
                    if issue.path.endswith(".id") and "id" not in code_obj:
                        code_obj["id"] = f"code_{hash(code_obj.get('code', ''))%10000}"
                        return FixResult(True, issue, f"Set code.id")
                    if issue.path.endswith(".codeSystemVersion") and "codeSystemVersion" not in code_obj:
                        code_obj["codeSystemVersion"] = "2024-09-27"
                        return FixResult(True, issue, "Set code.codeSystemVersion to '2024-09-27'")
                    if issue.path.endswith(".instanceType") and "instanceType" not in code_obj:
                        code_obj["instanceType"] = "Code"
                        return FixResult(True, issue, "Set code.instanceType to 'Code'")
            
        except Exception as e:
            logger.debug(f"Programmatic fix failed for {issue.path}: {e}")
            return FixResult(False, issue, error=str(e))
        
        return None  # No programmatic fix available
    
    def _apply_llm_fixes(
        self, 
        data: Dict[str, Any], 
        issues: List[SchemaIssue]
    ) -> Tuple[Dict[str, Any], List[FixResult]]:
        """Use LLM to fix complex issues."""
        fixes = []
        
        if not HAS_LLM:
            # Mark all as unfixable without LLM
            for issue in issues:
                fixes.append(FixResult(False, issue, error="LLM not available"))
            return data, fixes
        
        # Batch issues for efficiency (max 5 per call)
        batches = [issues[i:i+5] for i in range(0, len(issues), 5)]
        
        for batch in batches:
            try:
                # Get context around issues
                context = self._get_context_for_issues(data, batch)
                
                # Build prompt
                issues_text = "\n".join([
                    f"- Path: {i.path}\n  Issue: {i.message}\n  Hint: {i.fix_hint}"
                    for i in batch
                ])
                
                prompt = SCHEMA_FIX_PROMPT.format(
                    context_json=json.dumps(context, indent=2),
                    issues_list=issues_text
                )
                
                # Call LLM
                response = self._call_llm(prompt)
                fix_instructions = parse_llm_json(response, fallback={"fixes": []})
                
                # Apply fixes
                for fix in fix_instructions.get("fixes", []):
                    path = fix.get("path", "")
                    action = fix.get("action", "set")
                    value = fix.get("value")
                    description = fix.get("description", "LLM fix")
                    
                    # Find the matching issue
                    matching_issue = next((i for i in batch if i.path == path), None)
                    if not matching_issue:
                        continue
                    
                    try:
                        if action == "set":
                            self._set_value_at_path(data, path, value)
                            fixes.append(FixResult(True, matching_issue, description))
                        elif action == "add":
                            self._add_value_at_path(data, path, value)
                            fixes.append(FixResult(True, matching_issue, description))
                        elif action == "move":
                            # Handle moving data (e.g., timeline -> studyDesigns)
                            source = fix.get("source", path)
                            dest = fix.get("destination", "")
                            self._move_value(data, source, dest)
                            fixes.append(FixResult(True, matching_issue, description))
                    except Exception as e:
                        fixes.append(FixResult(False, matching_issue, error=str(e)))
                
            except Exception as e:
                logger.error(f"LLM fix batch failed: {e}")
                for issue in batch:
                    fixes.append(FixResult(False, issue, error=str(e)))
        
        return data, fixes
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM with the given prompt."""
        import google.generativeai as genai
        import os
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model_name)
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        return response.text or ""
    
    # Helper methods
    
    def _derive_study_name(self, data: Dict[str, Any]) -> str:
        """Try to derive study name from existing data."""
        # Check versions for titles
        versions = data.get("study", {}).get("versions", [])
        for version in versions:
            titles = version.get("titles", [])
            for title in titles:
                if title.get("text"):
                    return title["text"][:100]
        
        # Check for protocol name in metadata
        if "generatedFrom" in data:
            return data["generatedFrom"]
        
        return "Protocol Study"
    
    def _derive_titles(self, data: Dict[str, Any], version: Dict[str, Any]) -> List[Dict]:
        """Derive titles from existing data."""
        # Check if titles exist somewhere else
        existing = version.get("titles", [])
        if existing:
            return existing
        
        # Create minimal title
        study_name = data.get("study", {}).get("name", "Protocol Study")
        return [{
            "id": "title_1",
            "text": study_name,
            "type": {"code": "Official", "decode": "Official Study Title"},
            "instanceType": "StudyTitle"
        }]
    
    def _derive_identifiers(self, data: Dict[str, Any], version: Dict[str, Any]) -> List[Dict]:
        """Derive study identifiers from existing data."""
        existing = version.get("studyIdentifiers", [])
        if existing:
            return existing
        
        return [{
            "id": "sid_1",
            "text": "STUDY-001",
            "instanceType": "StudyIdentifier"
        }]
    
    def _extract_version_index(self, path: str) -> Optional[int]:
        """Extract version array index from path."""
        import re
        match = re.search(r'versions\[(\d+)\]', path)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_design_index(self, path: str) -> Optional[int]:
        """Extract studyDesigns array index from path."""
        import re
        match = re.search(r'studyDesigns\[(\d+)\]', path)
        if match:
            return int(match.group(1))
        return None
    
    def _navigate_to_path(self, data: Dict[str, Any], path: str) -> Optional[Dict]:
        """Navigate to a JSON path and return the object there."""
        import re
        
        # Remove leading $.
        if path.startswith("$."):
            path = path[2:]
        
        current = data
        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]  # Remove empty strings
        
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    return None
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current if isinstance(current, dict) else None
    
    def _navigate_to_parent(self, data: Dict[str, Any], path: str) -> Optional[Dict]:
        """Navigate to the parent of a JSON path and return the parent object."""
        # Remove the last part of the path to get parent
        # e.g., "study.versions[0].studyDesigns[0].studyArms[0].dataOriginType"
        # becomes "study.versions[0].studyDesigns[0].studyArms[0]"
        import re
        
        # Remove leading $.
        if path.startswith("$."):
            path = path[2:]
        
        # Remove the last field name
        if "." in path:
            parent_path = path.rsplit(".", 1)[0]
        else:
            return data  # Already at root
        
        return self._navigate_to_path(data, parent_path)
    
    def _navigate_to_design(self, data: Dict[str, Any], path: str) -> Optional[Dict]:
        """Navigate to the studyDesign object from a path within it."""
        import re
        
        # Find studyDesigns[N] in the path and navigate there
        match = re.search(r'studyDesigns\[(\d+)\]', path)
        if not match:
            return None
        
        design_idx = int(match.group(1))
        versions = data.get("study", {}).get("versions", [])
        
        for version in versions:
            designs = version.get("studyDesigns", [])
            if design_idx < len(designs):
                return designs[design_idx]
        
        return None
    
    def _generate_id_from_path(self, path: str) -> str:
        """Generate a reasonable ID based on the path context."""
        import re
        
        # Extract entity type from path
        if "activities[" in path:
            match = re.search(r'activities\[(\d+)\]', path)
            idx = match.group(1) if match else "1"
            return f"act_{idx}"
        elif "encounters[" in path:
            match = re.search(r'encounters\[(\d+)\]', path)
            idx = match.group(1) if match else "1"
            return f"enc_{idx}"
        elif "objectives[" in path:
            match = re.search(r'objectives\[(\d+)\]', path)
            idx = match.group(1) if match else "1"
            return f"obj_{idx}"
        elif "endpoints[" in path:
            match = re.search(r'endpoints\[(\d+)\]', path)
            idx = match.group(1) if match else "1"
            return f"ep_{idx}"
        
        # Generic ID
        return f"entity_{hash(path) % 10000}"
    
    def _migrate_timeline_to_study_designs(
        self, 
        data: Dict[str, Any], 
        issue: SchemaIssue
    ) -> FixResult:
        """Migrate timeline data to proper studyDesigns structure."""
        try:
            versions = data.get("study", {}).get("versions", [])
            for version in versions:
                if "timeline" in version:
                    timeline = version.pop("timeline")
                    
                    # Create studyDesign from timeline
                    study_design = {
                        "id": "sd_1",
                        "instanceType": "InterventionalStudyDesign",
                    }
                    
                    # Move timeline contents to studyDesign
                    for key in ["activities", "encounters", "epochs", "plannedTimepoints", 
                                "activityTimepoints", "activityGroups", "scheduleTimelines"]:
                        if key in timeline:
                            study_design[key] = timeline[key]
                    
                    # Initialize or append to studyDesigns
                    if "studyDesigns" not in version:
                        version["studyDesigns"] = []
                    version["studyDesigns"].append(study_design)
                    
                    return FixResult(True, issue, "Migrated timeline to studyDesigns[0]")
            
            return FixResult(False, issue, error="No timeline found to migrate")
            
        except Exception as e:
            return FixResult(False, issue, error=str(e))
    
    def _get_context_for_issues(self, data: Dict[str, Any], issues: List[SchemaIssue]) -> Dict:
        """Extract relevant context for LLM to understand issues."""
        # Return a simplified view around the issues
        context = {}
        
        if "study" in data:
            context["study"] = {
                "id": data["study"].get("id"),
                "name": data["study"].get("name"),
                "instanceType": data["study"].get("instanceType"),
            }
            
            versions = data["study"].get("versions", [])
            if versions:
                v = versions[0]
                context["study"]["versions"] = [{
                    "id": v.get("id"),
                    "instanceType": v.get("instanceType"),
                    "versionIdentifier": v.get("versionIdentifier"),
                    "_hasTimeline": "timeline" in v,
                    "_hasStudyDesigns": "studyDesigns" in v,
                    "_keys": list(v.keys())[:10],
                }]
        
        return context
    
    def _set_value_at_path(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value at a JSON path."""
        import re
        
        if path.startswith("$."):
            path = path[2:]
        
        parts = re.split(r'\.(?![^\[]*\])', path)  # Split on dots not in brackets
        current = data
        
        for i, part in enumerate(parts[:-1]):
            # Handle array indices
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            if array_match:
                key, idx = array_match.group(1), int(array_match.group(2))
                if key not in current:
                    current[key] = []
                while len(current[key]) <= idx:
                    current[key].append({})
                current = current[key][idx]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        # Set the final value
        final_part = parts[-1]
        array_match = re.match(r'(\w+)\[(\d+)\]', final_part)
        if array_match:
            key, idx = array_match.group(1), int(array_match.group(2))
            if key not in current:
                current[key] = []
            while len(current[key]) <= idx:
                current[key].append({})
            current[key][idx] = value
        else:
            current[final_part] = value
    
    def _add_value_at_path(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Add a value to an array at a JSON path."""
        parent_path = path.rsplit("[", 1)[0] if "[" in path else path.rsplit(".", 1)[0]
        parent = self._navigate_to_path(data, parent_path)
        if parent is not None:
            key = path.split(".")[-1].split("[")[0]
            if key in parent and isinstance(parent[key], list):
                parent[key].append(value)
            else:
                parent[key] = [value]
    
    def _move_value(self, data: Dict[str, Any], source: str, dest: str) -> None:
        """Move a value from source path to destination path."""
        source_value = self._navigate_to_path(data, source)
        if source_value is not None:
            # Remove from source (simplified - just for timeline case)
            if "timeline" in source:
                versions = data.get("study", {}).get("versions", [])
                for v in versions:
                    if "timeline" in v:
                        v.pop("timeline")
            
            # Add to destination
            self._set_value_at_path(data, dest, source_value)


def fix_usdm_schema(
    data: Dict[str, Any],
    model_name: str = "gemini-2.5-pro",
    use_llm: bool = True,
    max_iterations: int = 3,
) -> Tuple[Dict[str, Any], SchemaFixerResult]:
    """
    Convenience function to fix USDM schema issues.
    
    Args:
        data: USDM JSON data (dict or file path)
        model_name: LLM model for complex fixes
        use_llm: Whether to use LLM (set False for fast programmatic-only)
        max_iterations: Maximum fix iterations
        
    Returns:
        Tuple of (fixed_data, fixer_result)
    """
    # Load data if path provided
    if isinstance(data, str):
        with open(data, 'r', encoding='utf-8') as f:
            data = json.load(f)
    
    # Initial validation (using our OpenAPI validator)
    validation = validate_usdm(data)
    
    # ALWAYS apply fixes, even if OpenAPI validation passes
    # This is because the official usdm Pydantic validator catches more issues
    # than our custom OpenAPI validator (e.g., Code object required fields)
    fixer = LLMSchemaFixer(model_name, max_iterations)
    return fixer.fix_schema_issues(data, validation, use_llm)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python llm_schema_fixer.py <usdm_json_file> [--no-llm]")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    use_llm = "--no-llm" not in sys.argv
    
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    fixed_data, result = fix_usdm_schema(data, use_llm=use_llm)
    
    print(json.dumps(result.to_dict(), indent=2))
    
    # Optionally save fixed data
    if result.fixed_issues > 0:
        output_path = sys.argv[1].replace(".json", "_fixed.json")
        with open(output_path, 'w') as f:
            json.dump(fixed_data, f, indent=2)
        print(f"\nFixed data saved to: {output_path}")
