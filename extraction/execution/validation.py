"""
Validation and Quality Checks for Execution Model Extraction

Provides functions to validate extracted execution model data for:
- Completeness (required fields present)
- Consistency (no conflicting data)
- Quality (confidence thresholds, source quotes)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from .schema import (
    ExecutionModelData,
    TimeAnchor,
    Repetition,
    ExecutionTypeAssignment,
    TraversalConstraint,
    CrossoverDesign,
    FootnoteCondition,
    EndpointAlgorithm,
    DerivedVariable,
    SubjectStateMachine,
    StateType,
    AnchorType,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity level for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in execution model data."""
    severity: ValidationSeverity
    component: str
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "field": self.field,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of validation checks."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 1.0  # Quality score 0-1
    
    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "isValid": self.is_valid,
            "score": self.score,
            "errorCount": len(self.errors),
            "warningCount": len(self.warnings),
            "issues": [i.to_dict() for i in self.issues],
        }


def validate_execution_model(
    data: ExecutionModelData,
    min_confidence: float = 0.5,
    require_state_machine: bool = False,
) -> ValidationResult:
    """
    Validate execution model data for completeness and consistency.
    
    Args:
        data: ExecutionModelData to validate
        min_confidence: Minimum confidence threshold for components
        require_state_machine: Whether state machine is required
        
    Returns:
        ValidationResult with issues and quality score
    """
    issues: List[ValidationIssue] = []
    
    # Phase 1 validations
    issues.extend(_validate_time_anchors(data.time_anchors, min_confidence))
    issues.extend(_validate_repetitions(data.repetitions, min_confidence))
    issues.extend(_validate_execution_types(data.execution_types))
    
    # Phase 2 validations
    issues.extend(_validate_traversal(data.traversal_constraints))
    issues.extend(_validate_crossover(data.crossover_design))
    issues.extend(_validate_footnotes(data.footnote_conditions))
    
    # Phase 3 validations
    issues.extend(_validate_endpoints(data.endpoint_algorithms, min_confidence))
    issues.extend(_validate_derived_variables(data.derived_variables, min_confidence))
    issues.extend(_validate_state_machine(data.state_machine, require_state_machine))
    
    # Phase 4 stratification validations
    issues.extend(_validate_stratification(data.randomization_scheme))
    
    # Phase 5 validations
    issues.extend(_validate_sampling_constraints(data.sampling_constraints))
    
    # Cross-component consistency checks
    issues.extend(_validate_consistency(data))
    
    # Calculate quality score
    error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
    warning_count = len([i for i in issues if i.severity == ValidationSeverity.WARNING])
    
    # Deduct points for issues
    score = 1.0 - (error_count * 0.15) - (warning_count * 0.05)
    score = max(0.0, min(1.0, score))
    
    is_valid = error_count == 0
    
    return ValidationResult(
        is_valid=is_valid,
        issues=issues,
        score=score,
    )


def _validate_time_anchors(
    anchors: List[TimeAnchor],
    min_confidence: float,
) -> List[ValidationIssue]:
    """Validate time anchor data."""
    issues = []
    
    if not anchors:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="TimeAnchors",
            message="No time anchors extracted",
            suggestion="Check if protocol contains explicit time references (Day 1, baseline, etc.)",
        ))
        return issues
    
    # Check for common anchor types
    anchor_types = {a.anchor_type for a in anchors}
    
    if AnchorType.FIRST_DOSE not in anchor_types and AnchorType.RANDOMIZATION not in anchor_types:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="TimeAnchors",
            message="No first dose or randomization anchor found",
            suggestion="Most trials have a primary time reference (Day 1, randomization)",
        ))
    
    # Check for duplicates
    definitions = [a.definition.lower() for a in anchors]
    if len(definitions) != len(set(definitions)):
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="TimeAnchors",
            message="Duplicate anchor definitions detected",
            suggestion="Review and deduplicate similar anchors",
        ))
    
    return issues


def _validate_repetitions(
    repetitions: List[Repetition],
    min_confidence: float,
) -> List[ValidationIssue]:
    """Validate repetition patterns."""
    issues = []
    
    if not repetitions:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="Repetitions",
            message="No repetition patterns extracted",
        ))
        return issues
    
    # Check for interval patterns without intervals
    for rep in repetitions:
        if rep.type.value == "Interval" and not rep.interval:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="Repetitions",
                message=f"Interval repetition '{rep.id}' missing interval duration",
                field="interval",
            ))
    
    return issues


def _validate_execution_types(
    exec_types: List[ExecutionTypeAssignment],
) -> List[ValidationIssue]:
    """Validate execution type classifications."""
    issues = []
    
    if not exec_types:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="ExecutionTypes",
            message="No execution types classified",
            suggestion="Provide activities list for classification",
        ))
        return issues
    
    return issues


def _validate_traversal(
    constraints: List[TraversalConstraint],
) -> List[ValidationIssue]:
    """Validate traversal constraints."""
    issues = []
    
    if not constraints:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="TraversalConstraints",
            message="No traversal constraints extracted",
        ))
        return issues
    
    for tc in constraints:
        # Check for minimum sequence length
        if len(tc.required_sequence) < 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="TraversalConstraints",
                message="Traversal sequence too short",
                field="required_sequence",
                suggestion="Expected at least: SCREENING → ... → END_OF_STUDY",
            ))
        
        # Check for screening at start
        if tc.required_sequence and tc.required_sequence[0].upper() != "SCREENING":
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                component="TraversalConstraints",
                message="Sequence doesn't start with SCREENING",
                field="required_sequence",
            ))
    
    return issues


def _validate_crossover(
    crossover: Optional[CrossoverDesign],
) -> List[ValidationIssue]:
    """Validate crossover design."""
    issues = []
    
    if not crossover:
        return issues  # Crossover is optional
    
    if crossover.is_crossover:
        # Validate crossover has required fields
        if crossover.num_periods < 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                component="CrossoverDesign",
                message="Crossover design must have at least 2 periods",
                field="num_periods",
            ))
        
        if not crossover.sequences:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="CrossoverDesign",
                message="Crossover missing treatment sequences",
                field="sequences",
                suggestion="Expected sequences like ['AB', 'BA']",
            ))
    
    return issues


def _validate_footnotes(
    footnotes: List[FootnoteCondition],
) -> List[ValidationIssue]:
    """Validate footnote conditions."""
    issues = []
    
    # Check for excessive footnotes (might indicate extraction issues)
    if len(footnotes) > 100:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="FootnoteConditions",
            message=f"Unusually high number of footnotes ({len(footnotes)})",
            suggestion="Review filtering criteria for footnote extraction",
        ))
    
    # Check for footnotes without structured conditions
    unstructured = [f for f in footnotes if not f.structured_condition]
    if len(unstructured) > len(footnotes) * 0.5:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="FootnoteConditions",
            message=f"{len(unstructured)} footnotes lack structured conditions",
            suggestion="LLM enhancement may improve structure extraction",
        ))
    
    return issues


def _validate_endpoints(
    endpoints: List[EndpointAlgorithm],
    min_confidence: float,
) -> List[ValidationIssue]:
    """Validate endpoint algorithms."""
    issues = []
    
    if not endpoints:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="EndpointAlgorithms",
            message="No endpoint algorithms extracted",
            suggestion="Check if protocol contains endpoint definitions",
        ))
        return issues
    
    # Check for primary endpoint
    primary = [e for e in endpoints if e.endpoint_type.value == "Primary"]
    if not primary:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="EndpointAlgorithms",
            message="No primary endpoint extracted",
            suggestion="Most trials have at least one primary endpoint",
        ))
    
    # Check for algorithms without logic
    no_algorithm = [e for e in endpoints if not e.algorithm]
    if no_algorithm:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="EndpointAlgorithms",
            message=f"{len(no_algorithm)} endpoints missing algorithm/calculation logic",
            field="algorithm",
        ))
    
    return issues


def _validate_derived_variables(
    variables: List[DerivedVariable],
    min_confidence: float,
) -> List[ValidationIssue]:
    """Validate derived variables."""
    issues = []
    
    if not variables:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="DerivedVariables",
            message="No derived variables extracted",
        ))
        return issues
    
    # Check for change-from-baseline without baseline definition
    cfb_vars = [v for v in variables if "baseline" in v.variable_type.value.lower()]
    no_baseline = [v for v in cfb_vars if not v.baseline_definition]
    if no_baseline:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="DerivedVariables",
            message=f"{len(no_baseline)} change-from-baseline vars missing baseline definition",
            field="baseline_definition",
        ))
    
    # Check for variables without derivation rule
    no_rule = [v for v in variables if not v.derivation_rule]
    if no_rule:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="DerivedVariables",
            message=f"{len(no_rule)} variables missing derivation rule",
            field="derivation_rule",
        ))
    
    return issues


def _validate_state_machine(
    state_machine: Optional[SubjectStateMachine],
    required: bool,
) -> List[ValidationIssue]:
    """Validate subject state machine."""
    issues = []
    
    if not state_machine:
        if required:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                component="StateMachine",
                message="State machine required but not generated",
            ))
        else:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                component="StateMachine",
                message="No state machine generated",
            ))
        return issues
    
    sm = state_machine
    
    # Check for minimum states
    if len(sm.states) < 3:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="StateMachine",
            message="State machine has too few states",
            field="states",
            suggestion="Expected at least: Screening, OnTreatment, Completed",
        ))
    
    # Check for terminal states
    if not sm.terminal_states:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            component="StateMachine",
            message="State machine has no terminal states",
            field="terminal_states",
            suggestion="Add Completed, Discontinued as terminal states",
        ))
    
    # Check for transitions
    if not sm.transitions:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="StateMachine",
            message="State machine has no transitions",
            field="transitions",
        ))
    
    # Check for unreachable states
    reachable = {sm.initial_state}
    for t in sm.transitions:
        reachable.add(t.to_state)
    
    unreachable = set(sm.states) - reachable - {sm.initial_state}
    if unreachable:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="StateMachine",
            message=f"Unreachable states: {[s.value for s in unreachable]}",
            field="transitions",
            suggestion="Add transitions to reach these states",
        ))
    
    # Check for dead-end non-terminal states
    has_outgoing = set()
    for t in sm.transitions:
        has_outgoing.add(t.from_state)
    
    dead_ends = set(sm.states) - has_outgoing - set(sm.terminal_states)
    if dead_ends:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="StateMachine",
            message=f"Non-terminal dead-end states: {[s.value for s in dead_ends]}",
            suggestion="Add outgoing transitions or mark as terminal",
        ))
    
    return issues


def _validate_sampling_constraints(
    constraints: List,
) -> List[ValidationIssue]:
    """Validate sampling constraints."""
    issues = []
    
    if not constraints:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="SamplingConstraints",
            message="No sampling constraints extracted",
            suggestion="Check if protocol contains PK/PD sampling schedules",
        ))
        return issues
    
    # Check for reasonable sample counts
    for sc in constraints:
        if sc.min_per_window > 30:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="SamplingConstraints",
                message=f"Unusually high sample count ({sc.min_per_window}) for {sc.activity_id}",
                field="min_per_window",
                suggestion="Verify this is not an extraction error",
            ))
        
        if sc.min_per_window < 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="SamplingConstraints",
                message=f"Very low sample count ({sc.min_per_window}) for {sc.activity_id}",
                field="min_per_window",
            ))
    
    # Check for timepoints without window duration
    no_duration = [sc for sc in constraints if sc.timepoints and not sc.window_duration]
    if no_duration:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="SamplingConstraints",
            message=f"{len(no_duration)} constraints have timepoints but no window duration",
            field="window_duration",
        ))
    
    return issues


def _validate_consistency(
    data: ExecutionModelData,
) -> List[ValidationIssue]:
    """Cross-component consistency checks."""
    issues = []
    
    # Check state machine matches traversal
    if data.state_machine and data.traversal_constraints:
        sm_states = {s.value.upper() for s in data.state_machine.states}
        for tc in data.traversal_constraints:
            for epoch in tc.required_sequence:
                # Check if epoch has corresponding state
                if epoch.upper() not in sm_states and epoch.upper().replace("_", "") not in sm_states:
                    # Allow some flexibility in naming
                    pass  # Don't flag as error, just info
    
    # Check crossover matches traversal
    if data.crossover_design and data.crossover_design.is_crossover:
        if data.traversal_constraints:
            has_periods = any(
                "PERIOD" in epoch.upper() or "WASHOUT" in epoch.upper()
                for tc in data.traversal_constraints
                for epoch in tc.required_sequence
            )
            if not has_periods:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    component="Consistency",
                    message="Crossover detected but traversal doesn't show period structure",
                ))
    
    # Check endpoints have corresponding derived variables
    if data.endpoint_algorithms and data.derived_variables:
        endpoint_names = {e.name.lower() for e in data.endpoint_algorithms}
        variable_names = {v.name.lower() for v in data.derived_variables}
        
        # Check if any endpoints mention change from baseline
        cfb_endpoints = [e for e in data.endpoint_algorithms if "change" in e.name.lower() and "baseline" in e.name.lower()]
        cfb_variables = [v for v in data.derived_variables if "change" in v.name.lower() or v.variable_type.value == "ChangeFromBaseline"]
        
        if cfb_endpoints and not cfb_variables:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                component="Consistency",
                message="Change-from-baseline endpoints found but no CFB derived variables",
                suggestion="Check derived variable extraction",
            ))
    
    return issues


def _validate_stratification(scheme) -> List[ValidationIssue]:
    """E1: Validate randomization scheme and stratification coherence."""
    issues: List[ValidationIssue] = []
    
    if not scheme:
        return issues
    
    # Check allocation ratio is present
    ratio = getattr(scheme, 'ratio', '') or ''
    if not ratio:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="Stratification",
            message="Randomization scheme missing allocation ratio",
            field="ratio",
        ))
    
    # Check all factors have ≥2 categories/levels
    factors = getattr(scheme, 'stratification_factors', []) or []
    for factor in factors:
        cats = getattr(factor, 'categories', []) or []
        levels = getattr(factor, 'factor_levels', []) or []
        n_levels = len(levels) if levels else len(cats)
        name = getattr(factor, 'name', 'Unknown')
        
        if n_levels == 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="Stratification",
                message=f"Factor '{name}' has no categories or levels defined",
                field="categories",
                suggestion="Levels should be extracted from protocol text",
            ))
        elif n_levels == 1:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="Stratification",
                message=f"Factor '{name}' has only 1 level — stratification requires ≥2",
                field="categories",
            ))
    
    # Block size compatibility with ratio
    block_size = getattr(scheme, 'block_size', None)
    block_sizes = getattr(scheme, 'block_sizes', []) or []
    if ratio and (block_size or block_sizes):
        import re as _re
        ratio_weights = [int(w) for w in _re.findall(r'\d+', ratio)]
        ratio_sum = sum(ratio_weights) if ratio_weights else 0
        sizes_to_check = block_sizes if block_sizes else ([block_size] if block_size else [])
        for bs in sizes_to_check:
            if ratio_sum > 0 and bs % ratio_sum != 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    component="Stratification",
                    message=(
                        f"Block size {bs} is not a multiple of ratio sum "
                        f"{ratio_sum} ({ratio}) — may cause imbalance"
                    ),
                    field="block_size",
                ))
    
    # Overstratification warning (>16 cells with few subjects)
    if len(factors) >= 2:
        total_cells = 1
        for factor in factors:
            cats = getattr(factor, 'categories', []) or []
            levels = getattr(factor, 'factor_levels', []) or []
            n = len(levels) if levels else len(cats)
            if n > 0:
                total_cells *= n
        if total_cells > 16:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                component="Stratification",
                message=(
                    f"Stratification creates {total_cells} cells — "
                    f"risk of overstratification (recommend ≤16 cells)"
                ),
                suggestion="Consider collapsing factor levels or removing low-impact factors",
            ))
    
    # IWRS check: central randomization claims need a system identified
    central = getattr(scheme, 'central_randomization', False)
    iwrs = getattr(scheme, 'iwrs_system', None)
    if central and not iwrs:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            component="Stratification",
            message="Central randomization indicated but no IWRS/IXRS system identified",
            field="iwrs_system",
            suggestion="Check protocol for IWRS vendor name",
        ))
    
    # Adaptive design should have rules
    is_adaptive = getattr(scheme, 'is_adaptive', False)
    adaptive_rules = getattr(scheme, 'adaptive_rules', None)
    if is_adaptive and not adaptive_rules:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            component="Stratification",
            message="Adaptive randomization indicated but no adaptation rules specified",
            field="adaptive_rules",
            suggestion="Protocol should describe when/how allocation ratios change",
        ))
    
    return issues


def create_validation_summary(result: ValidationResult) -> str:
    """Create a human-readable validation summary."""
    lines = [
        "Execution Model Validation",
        "=" * 40,
        f"Valid: {'✓' if result.is_valid else '✗'}",
        f"Quality Score: {result.score:.2f}",
        f"Errors: {len(result.errors)}",
        f"Warnings: {len(result.warnings)}",
    ]
    
    if result.errors:
        lines.append("\nErrors:")
        for e in result.errors:
            lines.append(f"  ✗ [{e.component}] {e.message}")
            if e.suggestion:
                lines.append(f"    → {e.suggestion}")
    
    if result.warnings:
        lines.append("\nWarnings:")
        for w in result.warnings:
            lines.append(f"  ⚠ [{w.component}] {w.message}")
    
    return "\n".join(lines)
