"""
Export Functions for Execution Model Data

Provides functions to export execution model data to various formats:
- CSV for tabular data
- Markdown summary reports
- HTML reports
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .schema import ExecutionModelData

logger = logging.getLogger(__name__)


def export_to_csv(
    data: ExecutionModelData,
    output_dir: str,
    prefix: str = "execution_model",
) -> Dict[str, str]:
    """
    Export execution model data to CSV files.
    
    Creates separate CSV files for each component type.
    
    Args:
        data: ExecutionModelData to export
        output_dir: Directory to save CSV files
        prefix: Prefix for output filenames
        
    Returns:
        Dict mapping component names to file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    files_created = {}
    
    # Export time anchors
    if data.time_anchors:
        filepath = output_path / f"{prefix}_time_anchors.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'anchor_type', 'definition', 'day_value', 'source_text'])
            for anchor in data.time_anchors:
                writer.writerow([
                    anchor.id,
                    anchor.anchor_type.value,
                    anchor.definition,
                    anchor.day_value,
                    anchor.source_text[:100] if anchor.source_text else '',
                ])
        files_created['time_anchors'] = str(filepath)
    
    # Export repetitions
    if data.repetitions:
        filepath = output_path / f"{prefix}_repetitions.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'type', 'interval', 'count', 'source_text'])
            for rep in data.repetitions:
                writer.writerow([
                    rep.id,
                    rep.type.value,
                    rep.interval or '',
                    rep.count or '',
                    rep.source_text[:100] if rep.source_text else '',
                ])
        files_created['repetitions'] = str(filepath)
    
    # Export execution types
    if data.execution_types:
        filepath = output_path / f"{prefix}_execution_types.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['activity_id', 'execution_type', 'rationale'])
            for et in data.execution_types:
                writer.writerow([
                    et.activity_id,
                    et.execution_type.value,
                    et.rationale[:100] if et.rationale else '',
                ])
        files_created['execution_types'] = str(filepath)
    
    # Export traversal constraints
    if data.traversal_constraints:
        filepath = output_path / f"{prefix}_traversal.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'required_sequence', 'mandatory_visits', 'allow_early_exit'])
            for tc in data.traversal_constraints:
                writer.writerow([
                    tc.id,
                    ' → '.join(tc.required_sequence),
                    ', '.join(tc.mandatory_visits),
                    tc.allow_early_exit,
                ])
        files_created['traversal'] = str(filepath)
    
    # Export footnote conditions
    if data.footnote_conditions:
        filepath = output_path / f"{prefix}_footnotes.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'condition_type', 'text', 'structured_condition'])
            for fc in data.footnote_conditions:
                writer.writerow([
                    fc.id,
                    fc.condition_type,
                    fc.text[:100] if fc.text else '',
                    fc.structured_condition or '',
                ])
        files_created['footnotes'] = str(filepath)
    
    # Export endpoint algorithms
    if data.endpoint_algorithms:
        filepath = output_path / f"{prefix}_endpoints.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'name', 'endpoint_type', 'algorithm', 'inputs', 'time_window'])
            for ep in data.endpoint_algorithms:
                writer.writerow([
                    ep.id,
                    ep.name,
                    ep.endpoint_type.value,
                    ep.algorithm[:100] if ep.algorithm else '',
                    ', '.join(ep.inputs) if ep.inputs else '',
                    ep.time_window_duration or '',
                ])
        files_created['endpoints'] = str(filepath)
    
    # Export derived variables
    if data.derived_variables:
        filepath = output_path / f"{prefix}_derived_variables.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'name', 'variable_type', 'derivation_rule', 'baseline_definition', 'source_variables'])
            for dv in data.derived_variables:
                writer.writerow([
                    dv.id,
                    dv.name,
                    dv.variable_type.value,
                    dv.derivation_rule[:100] if dv.derivation_rule else '',
                    dv.baseline_definition[:100] if dv.baseline_definition else '',
                    ', '.join(dv.source_variables) if dv.source_variables else '',
                ])
        files_created['derived_variables'] = str(filepath)
    
    # Export state machine
    if data.state_machine:
        sm = data.state_machine
        filepath = output_path / f"{prefix}_state_machine.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['from_state', 'to_state', 'trigger', 'guard_condition'])
            for t in sm.transitions:
                writer.writerow([
                    t.from_state.value,
                    t.to_state.value,
                    t.trigger,
                    t.guard_condition or '',
                ])
        files_created['state_machine'] = str(filepath)
    
    # Export dosing regimens (Phase 4)
    if data.dosing_regimens:
        filepath = output_path / f"{prefix}_dosing_regimens.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'treatment_name', 'doses', 'frequency', 'route', 'start_day', 'duration', 'titration'])
            for dr in data.dosing_regimens:
                doses = '; '.join(f"{d.amount}{d.unit}" for d in dr.dose_levels)
                writer.writerow([
                    dr.id,
                    dr.treatment_name,
                    doses,
                    dr.frequency.value,
                    dr.route.value,
                    dr.start_day,
                    dr.duration_description or '',
                    dr.titration_schedule[:100] if dr.titration_schedule else '',
                ])
        files_created['dosing_regimens'] = str(filepath)
    
    # Export visit windows (Phase 4)
    if data.visit_windows:
        filepath = output_path / f"{prefix}_visit_windows.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'visit_name', 'visit_number', 'target_day', 'target_week', 'window_before', 'window_after', 'is_required', 'epoch'])
            for vw in data.visit_windows:
                writer.writerow([
                    vw.id,
                    vw.visit_name,
                    vw.visit_number or '',
                    vw.target_day,
                    vw.target_week or '',
                    vw.window_before,
                    vw.window_after,
                    vw.is_required,
                    vw.epoch or '',
                ])
        files_created['visit_windows'] = str(filepath)
    
    # Export randomization scheme (Phase 4)
    if data.randomization_scheme:
        rs = data.randomization_scheme
        filepath = output_path / f"{prefix}_randomization.csv"
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'ratio', 'method', 'block_size', 'central_randomization', 'stratification_factors'])
            factors = '; '.join(f.name for f in rs.stratification_factors) if rs.stratification_factors else ''
            writer.writerow([
                rs.id,
                rs.ratio,
                rs.method,
                rs.block_size or '',
                rs.central_randomization,
                factors,
            ])
        files_created['randomization'] = str(filepath)
        
        # Also export stratification factors detail
        if rs.stratification_factors:
            filepath = output_path / f"{prefix}_stratification_factors.csv"
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'categories', 'is_blocking'])
                for sf in rs.stratification_factors:
                    writer.writerow([
                        sf.id,
                        sf.name,
                        '; '.join(sf.categories),
                        sf.is_blocking,
                    ])
            files_created['stratification_factors'] = str(filepath)
    
    logger.info(f"Exported {len(files_created)} CSV files to {output_dir}")
    return files_created


def generate_markdown_report(
    data: ExecutionModelData,
    protocol_name: str = "Protocol",
    confidence: float = 0.0,
    validation_result: Optional[Any] = None,
) -> str:
    """
    Generate a Markdown summary report of execution model extraction.
    
    Args:
        data: ExecutionModelData to summarize
        protocol_name: Name of the protocol
        confidence: Overall extraction confidence
        validation_result: Optional ValidationResult to include
        
    Returns:
        Markdown formatted report string
    """
    lines = [
        f"# Execution Model Report: {protocol_name}",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Confidence:** {confidence:.0%}",
        f"",
        "---",
        "",
    ]
    
    # Summary statistics
    lines.extend([
        "## Summary",
        "",
        "| Component | Count |",
        "|-----------|-------|",
        f"| Time Anchors | {len(data.time_anchors)} |",
        f"| Repetitions | {len(data.repetitions)} |",
        f"| Execution Types | {len(data.execution_types)} |",
        f"| Traversal Constraints | {len(data.traversal_constraints)} |",
        f"| Footnote Conditions | {len(data.footnote_conditions)} |",
        f"| Endpoint Algorithms | {len(data.endpoint_algorithms)} |",
        f"| Derived Variables | {len(data.derived_variables)} |",
        f"| State Machine | {'Yes' if data.state_machine else 'No'} |",
        "",
    ])
    
    # Phase 1: Time Anchors
    if data.time_anchors:
        lines.extend([
            "## Time Anchors",
            "",
            "| Type | Definition | Day |",
            "|------|------------|-----|",
        ])
        for a in data.time_anchors:
            lines.append(f"| {a.anchor_type.value} | {a.definition[:50]} | {a.day_value or 'N/A'} |")
        lines.append("")
    
    # Phase 1: Execution Types
    if data.execution_types:
        lines.extend([
            "## Execution Type Classifications",
            "",
        ])
        type_groups: Dict[str, List[str]] = {}
        for et in data.execution_types:
            t = et.execution_type.value
            if t not in type_groups:
                type_groups[t] = []
            type_groups[t].append(et.activity_id)
        
        for type_name, activities in type_groups.items():
            lines.append(f"**{type_name}:** {', '.join(activities[:10])}")
            if len(activities) > 10:
                lines.append(f"  *(and {len(activities) - 10} more)*")
        lines.append("")
    
    # Phase 2: Crossover
    if data.crossover_design and data.crossover_design.is_crossover:
        cd = data.crossover_design
        lines.extend([
            "## Crossover Design",
            "",
            f"- **Periods:** {cd.num_periods}",
            f"- **Sequences:** {', '.join(cd.sequences) if cd.sequences else 'N/A'}",
            f"- **Washout:** {cd.washout_duration or 'Not specified'}",
            "",
        ])
    
    # Phase 2: Traversal
    if data.traversal_constraints:
        lines.extend([
            "## Subject Traversal",
            "",
        ])
        for tc in data.traversal_constraints:
            lines.append(f"**Path:** {' → '.join(tc.required_sequence)}")
            if tc.mandatory_visits:
                lines.append(f"**Mandatory:** {', '.join(tc.mandatory_visits)}")
        lines.append("")
    
    # Phase 3: Endpoints
    if data.endpoint_algorithms:
        lines.extend([
            "## Endpoint Algorithms",
            "",
            "| Type | Name | Algorithm |",
            "|------|------|-----------|",
        ])
        for ep in data.endpoint_algorithms:
            alg = (ep.algorithm[:40] + "...") if ep.algorithm and len(ep.algorithm) > 40 else (ep.algorithm or "")
            lines.append(f"| {ep.endpoint_type.value} | {ep.name[:30]} | {alg} |")
        lines.append("")
    
    # Phase 3: Derived Variables
    if data.derived_variables:
        lines.extend([
            "## Derived Variables",
            "",
            "| Type | Name | Rule |",
            "|------|------|------|",
        ])
        for dv in data.derived_variables:
            rule = (dv.derivation_rule[:40] + "...") if dv.derivation_rule and len(dv.derivation_rule) > 40 else (dv.derivation_rule or "")
            lines.append(f"| {dv.variable_type.value} | {dv.name[:30]} | {rule} |")
        lines.append("")
    
    # Phase 3: State Machine
    if data.state_machine:
        sm = data.state_machine
        lines.extend([
            "## Subject State Machine",
            "",
            f"- **States:** {len(sm.states)}",
            f"- **Transitions:** {len(sm.transitions)}",
            f"- **Initial:** {sm.initial_state.value}",
            f"- **Terminal:** {', '.join(s.value for s in sm.terminal_states)}",
            "",
            "### Transitions",
            "",
            "| From | To | Trigger |",
            "|------|----|---------| ",
        ])
        for t in sm.transitions[:10]:
            trigger = (t.trigger[:40] + "...") if len(t.trigger) > 40 else t.trigger
            lines.append(f"| {t.from_state.value} | {t.to_state.value} | {trigger} |")
        if len(sm.transitions) > 10:
            lines.append(f"*...and {len(sm.transitions) - 10} more transitions*")
        lines.append("")
    
    # Validation results
    if validation_result:
        lines.extend([
            "## Validation",
            "",
            f"- **Valid:** {'✓' if validation_result.is_valid else '✗'}",
            f"- **Quality Score:** {validation_result.score:.0%}",
            f"- **Errors:** {len(validation_result.errors)}",
            f"- **Warnings:** {len(validation_result.warnings)}",
            "",
        ])
        
        if validation_result.errors:
            lines.append("### Errors")
            lines.append("")
            for e in validation_result.errors:
                lines.append(f"- **{e.component}:** {e.message}")
            lines.append("")
        
        if validation_result.warnings:
            lines.append("### Warnings")
            lines.append("")
            for w in validation_result.warnings:
                lines.append(f"- **{w.component}:** {w.message}")
            lines.append("")
    
    lines.extend([
        "---",
        "",
        "*Generated by Protocol2USDM Execution Model Extractor*",
    ])
    
    return "\n".join(lines)


def save_report(
    data: ExecutionModelData,
    output_path: str,
    protocol_name: str = "Protocol",
    confidence: float = 0.0,
    validation_result: Optional[Any] = None,
) -> str:
    """
    Save a Markdown report to file.
    
    Args:
        data: ExecutionModelData to report on
        output_path: Path to save the report
        protocol_name: Name of the protocol
        confidence: Overall extraction confidence
        validation_result: Optional validation results
        
    Returns:
        Path to saved report
    """
    report = generate_markdown_report(
        data=data,
        protocol_name=protocol_name,
        confidence=confidence,
        validation_result=validation_result,
    )
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"Saved report to {path}")
    return str(path)
