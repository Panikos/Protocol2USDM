"""
Simplified SoA Extraction Pipeline

This module provides a clean, simple pipeline that follows the original design:
1. Vision extracts STRUCTURE (headers, groups)
2. Text extracts DATA (activities, ticks) using structure as anchor
3. Vision validates text extraction

Usage:
    from extraction.pipeline import run_extraction_pipeline
    
    result = run_extraction_pipeline(
        pdf_path="protocol.pdf",
        output_dir="output/protocol",
        model_name="gemini-2.5-pro"
    )
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

from .header_analyzer import analyze_soa_headers, load_header_structure, save_header_structure
from .text_extractor import extract_soa_from_text, build_usdm_output, save_extraction_result
from .validator import validate_extraction, apply_validation_fixes, save_validation_result

from core.provenance import ProvenanceTracker, get_provenance_path
from core.constants import USDM_VERSION

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the extraction pipeline."""
    model_name: str = "gemini-2.5-pro"
    validate_with_vision: bool = True
    remove_hallucinations: bool = False  # Keep all text-extracted cells; use provenance for confidence
    hallucination_confidence_threshold: float = 0.7
    save_intermediate: bool = True
    use_table_extraction: bool = True  # Use table-aware PDF extraction (vs raw text)


@dataclass
class PipelineResult:
    """Result of the full pipeline."""
    success: bool
    output_path: Optional[str] = None
    provenance_path: Optional[str] = None
    
    # Statistics
    activities_count: int = 0
    ticks_count: int = 0
    timepoints_count: int = 0
    
    # Validation results
    validated: bool = False
    hallucinations_removed: int = 0
    missed_ticks_found: int = 0
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'success': self.success,
            'output_path': self.output_path,
            'provenance_path': self.provenance_path,
            'statistics': {
                'activities': self.activities_count,
                'ticks': self.ticks_count,
                'timepoints': self.timepoints_count,
            },
            'validation': {
                'validated': self.validated,
                'hallucinations_removed': self.hallucinations_removed,
                'missed_ticks_found': self.missed_ticks_found,
            },
            'errors': self.errors,
        }


def _resolve_activity_group_links(activities, activity_groups):
    """
    Post-process activity groups to link activities by various strategies.
    
    Strategy 1: Use activityGroupId from text extraction (if present)
    Strategy 2: Use activity_names from header analyzer (name matching)
    Strategy 3: Keep empty (let viewer handle flat display)
    
    Args:
        activities: List of Activity objects from text extraction
        activity_groups: List of ActivityGroup objects from header analyzer
        
    Returns:
        Updated activity_groups with activity_ids populated
    """
    if not activity_groups:
        return activity_groups
    
    # Build activity name -> id mapping
    activity_name_to_id = {}
    activity_id_to_group = {}
    
    for act in activities:
        act_dict = act.to_dict() if hasattr(act, 'to_dict') else act
        act_id = act_dict.get('id') or (act.id if hasattr(act, 'id') else None)
        act_name = act_dict.get('name') or (act.name if hasattr(act, 'name') else '')
        
        if act_id and act_name:
            activity_name_to_id[act_name.lower().strip()] = act_id
        
        # Track existing activityGroupId assignments
        group_id = act_dict.get('activityGroupId')
        if group_id:
            activity_id_to_group[act_id] = group_id
    
    # Update each group's activity_ids
    for group in activity_groups:
        child_ids = []
        
        # Strategy 1: Find activities that reference this group via activityGroupId
        for act_id, grp_id in activity_id_to_group.items():
            if grp_id == group.id:
                child_ids.append(act_id)
        
        # Strategy 2: Match by activity_names from header analyzer
        if not child_ids and hasattr(group, 'activity_names') and group.activity_names:
            for act_name in group.activity_names:
                act_name_lower = act_name.lower().strip()
                if act_name_lower in activity_name_to_id:
                    child_ids.append(activity_name_to_id[act_name_lower])
        
        # Update the group's activity_ids
        if child_ids:
            group.activity_ids = child_ids
            logger.debug(f"Group '{group.name}' linked to {len(child_ids)} activities")
    
    return activity_groups


def run_extraction_pipeline(
    protocol_text: str,
    soa_images: List[str],
    output_dir: str,
    config: Optional[PipelineConfig] = None,
) -> PipelineResult:
    """
    Run the complete SoA extraction pipeline.
    
    Pipeline steps:
    1. Analyze SoA headers from images (Vision → Structure)
    2. Extract SoA data from text using header structure (Text → Data)
    3. Validate extraction against images (Vision validates Text)
    4. Build and save USDM output
    
    Args:
        protocol_text: Text content from protocol (SoA pages)
        soa_images: List of paths to SoA table images
        output_dir: Directory for output files
        config: Pipeline configuration
        
    Returns:
        PipelineResult with output paths and statistics
    """
    if config is None:
        config = PipelineConfig()
    
    result = PipelineResult(success=False)
    os.makedirs(output_dir, exist_ok=True)
    
    # Define output paths
    paths = {
        'header': os.path.join(output_dir, "4_header_structure.json"),
        'raw_text': os.path.join(output_dir, "5_raw_text_soa.json"),
        'validation': os.path.join(output_dir, "6_validation_result.json"),
        'final': os.path.join(output_dir, "9_final_soa.json"),
    }
    
    try:
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Vision extracts STRUCTURE
        # ═══════════════════════════════════════════════════════════════
        logger.info("Step 1: Analyzing SoA header structure from images...")
        
        header_result = analyze_soa_headers(
            image_paths=soa_images,
            model_name=config.model_name,
        )
        
        if not header_result.success:
            result.errors.append(f"Header analysis failed: {header_result.error}")
            return result
        
        header_structure = header_result.structure
        result.timepoints_count = len(header_structure.plannedTimepoints)
        
        if config.save_intermediate:
            save_header_structure(header_structure, paths['header'])
        
        logger.info(f"  Found {result.timepoints_count} timepoints, "
                   f"{len(header_structure.epochs)} epochs, "
                   f"{len(header_structure.activityGroups)} groups")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Text extracts DATA using header structure as anchor
        # ═══════════════════════════════════════════════════════════════
        logger.info("Step 2: Extracting SoA data from text...")
        
        text_result = extract_soa_from_text(
            protocol_text=protocol_text,
            header_structure=header_structure,
            model_name=config.model_name,
        )
        
        if not text_result.success:
            result.errors.append(f"Text extraction failed: {text_result.error}")
            return result
        
        result.activities_count = len(text_result.activities)
        result.ticks_count = len(text_result.activity_timepoints)
        
        if config.save_intermediate:
            usdm_output = build_usdm_output(text_result, header_structure)
            with open(paths['raw_text'], 'w', encoding='utf-8') as f:
                json.dump(usdm_output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"  Extracted {result.activities_count} activities, "
                   f"{result.ticks_count} ticks")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Vision validates text extraction
        # ═══════════════════════════════════════════════════════════════
        final_ticks = [at.to_dict() for at in text_result.activity_timepoints]
        provenance = text_result.provenance
        
        if config.validate_with_vision and soa_images:
            logger.info("Step 3: Validating extraction against images...")
            
            # Extract footnotes from header structure if available
            footnotes_text = ""
            if hasattr(header_structure, 'footnotes') and header_structure.footnotes:
                footnotes_text = "\n".join(header_structure.footnotes)
            
            validation = validate_extraction(
                text_activities=[a.to_dict() for a in text_result.activities],
                text_ticks=final_ticks,
                header_structure=header_structure,
                image_paths=soa_images,
                model_name=config.model_name,
                protocol_text=protocol_text,
                footnotes=footnotes_text,
            )
            
            if validation.success:
                result.validated = True
                result.hallucinations_removed = validation.hallucination_count
                result.missed_ticks_found = validation.missed_count
                
                if config.save_intermediate:
                    save_validation_result(validation, paths['validation'])
                
                # Apply validation fixes and update provenance
                # Always run to tag validated ticks as "both" (confirmed by vision)
                final_ticks, val_provenance = apply_validation_fixes(
                    final_ticks,
                    validation,
                    remove_hallucinations=config.remove_hallucinations,
                    confidence_threshold=config.hallucination_confidence_threshold,
                )
                provenance.merge(val_provenance)
                result.ticks_count = len(final_ticks)
                
                logger.info(f"  Validation complete: {validation.confirmed_ticks} confirmed, "
                           f"{validation.hallucination_count} possible hallucinations, "
                           f"{validation.missed_count} possibly missed")
            else:
                logger.warning(f"  Validation failed: {validation.error}")
                result.errors.append(f"Validation failed (non-fatal): {validation.error}")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 4: Build and save final USDM output
        # ═══════════════════════════════════════════════════════════════
        logger.info("Step 4: Building final USDM output...")
        
        # Rebuild timeline with validated ticks
        from core.usdm_types import Timeline, ActivityTimepoint, create_wrapper_input
        
        # Post-process: Link activities to groups if not already linked
        activity_groups = _resolve_activity_group_links(
            text_result.activities, 
            header_structure.activityGroups
        )
        
        final_timeline = Timeline(
            activities=text_result.activities,
            plannedTimepoints=header_structure.plannedTimepoints,
            encounters=header_structure.encounters,
            epochs=header_structure.epochs,
            activityGroups=activity_groups,
            activityTimepoints=[ActivityTimepoint.from_dict(t) for t in final_ticks],
            footnotes=header_structure.footnotes,  # SoA table footnotes
        )
        
        final_output = create_wrapper_input(final_timeline)
        
        # Save final output
        with open(paths['final'], 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        
        result.output_path = paths['final']
        
        # Save provenance separately
        provenance_path = get_provenance_path(paths['final'])
        provenance.save(provenance_path)
        result.provenance_path = provenance_path
        
        result.success = True
        logger.info(f"Pipeline complete! Output: {paths['final']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        result.errors.append(str(e))
        return result


def extract_tables_from_pages(doc, page_nums: List[int]) -> str:
    """
    Extract text from PDF pages using table-aware extraction.
    
    Uses PyMuPDF's built-in table detection to preserve table structure.
    Falls back to raw text for non-table content.
    
    Args:
        doc: PyMuPDF document object
        page_nums: List of 0-indexed page numbers
        
    Returns:
        Formatted text with tables preserved as markdown
    """
    all_text_parts = []
    
    for page_num in sorted(page_nums):
        if not (0 <= page_num < len(doc)):
            continue
            
        page = doc[page_num]
        page_text_parts = []
        
        # Try to find tables on this page
        try:
            tables = page.find_tables()
            
            if tables and len(tables.tables) > 0:
                # Found tables - extract as structured markdown
                for table in tables.tables:
                    # Convert table to markdown format
                    md_rows = []
                    for row_idx, row in enumerate(table.extract()):
                        # Clean cells
                        cells = [str(cell).strip() if cell else "" for cell in row]
                        md_row = "| " + " | ".join(cells) + " |"
                        md_rows.append(md_row)
                        
                        # Add header separator after first row
                        if row_idx == 0:
                            separator = "|" + "|".join(["---" for _ in cells]) + "|"
                            md_rows.append(separator)
                    
                    if md_rows:
                        page_text_parts.append("\n".join(md_rows))
                
                # Also get any non-table text
                non_table_text = page.get_text().strip()
                if non_table_text:
                    # Add context text that's not part of tables
                    page_text_parts.append(f"\n[Additional text from page {page_num + 1}:]\n{non_table_text[:500]}...")
                    
                logger.debug(f"Page {page_num + 1}: Extracted {len(tables.tables)} table(s)")
            else:
                # No tables found - use raw text
                page_text_parts.append(page.get_text())
                logger.debug(f"Page {page_num + 1}: No tables found, using raw text")
                
        except Exception as e:
            # Fallback to raw text if table extraction fails
            logger.warning(f"Table extraction failed on page {page_num + 1}: {e}, using raw text")
            page_text_parts.append(page.get_text())
        
        if page_text_parts:
            all_text_parts.append(f"\n\n--- PAGE {page_num + 1} ---\n\n" + "\n\n".join(page_text_parts))
    
    result = "\n".join(all_text_parts)
    logger.info(f"Table extraction: processed {len(page_nums)} pages")
    return result


def run_from_files(
    pdf_path: str,
    output_dir: str,
    soa_pages: Optional[List[int]] = None,
    config: Optional[PipelineConfig] = None,
) -> PipelineResult:
    """
    Run pipeline from PDF file.
    
    This is a convenience wrapper that handles:
    - Finding SoA pages (if not provided)
    - Extracting text and images
    - Running the pipeline
    
    Args:
        pdf_path: Path to protocol PDF
        output_dir: Directory for output files
        soa_pages: Optional list of SoA page numbers (0-indexed). If not provided,
                   will automatically detect SoA pages.
        config: Pipeline configuration
        
    Returns:
        PipelineResult
    """
    import fitz  # PyMuPDF
    from .soa_finder import find_soa_pages
    
    if config is None:
        config = PipelineConfig()
    
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Open PDF
    doc = fitz.open(pdf_path)
    
    # Find SoA pages if not provided
    if soa_pages is None:
        logger.info("Finding SoA pages...")
        # Use enhanced finder with title detection and adjacent page expansion
        soa_pages = find_soa_pages(pdf_path, model_name=config.model_name, use_llm=True)
        
        if not soa_pages:
            logger.warning("Could not find SoA pages. Using first 10 pages as fallback.")
            soa_pages = list(range(min(10, len(doc))))
        else:
            # Log pages in human-readable format (1-indexed)
            logger.info(f"Found SoA pages: {[p+1 for p in sorted(soa_pages)]} (PDF viewer numbering)")
    
    # Extract text from SoA pages
    if config.use_table_extraction:
        text = extract_tables_from_pages(doc, soa_pages)
    else:
        # Fallback: raw text extraction
        text = "\n\n--- PAGE BREAK ---\n\n".join(
            doc[p].get_text() for p in soa_pages if 0 <= p < len(doc)
        )
    
    # Extract images from SoA pages only
    images_dir = os.path.join(output_dir, "3_soa_images")
    os.makedirs(images_dir, exist_ok=True)
    
    image_paths = []
    for page_num in soa_pages:
        if 0 <= page_num < len(doc):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            img_path = os.path.join(images_dir, f"soa_page_{page_num + 1:03d}.png")  # 1-indexed for human readability
            pix.save(img_path)
            image_paths.append(img_path)
            logger.debug(f"Extracted page {page_num} as image")
    
    doc.close()
    
    logger.info(f"Extracted {len(image_paths)} SoA page images")
    
    # Run pipeline
    return run_extraction_pipeline(
        protocol_text=text,
        soa_images=image_paths,
        output_dir=output_dir,
        config=config,
    )


# ═══════════════════════════════════════════════════════════════════════════
# POST-PROCESSING STEPS (Steps 7-9)
# ═══════════════════════════════════════════════════════════════════════════

def enrich_terminology(soa_path: str) -> dict:
    """
    Step 7: Enrich activities with NCI terminology codes.
    
    Uses a curated mapping of common clinical terms to NCI codes.
    """
    import json
    
    # Common clinical procedure NCI codes
    KNOWN_CODES = {
        "informed consent": ("C16735", "Informed Consent"),
        "physical exam": ("C20989", "Physical Examination"),
        "vital signs": ("C25714", "Vital Signs"),
        "ecg": ("C38054", "Electrocardiogram"),
        "blood pressure": ("C54706", "Blood Pressure Measurement"),
        "weight": ("C25208", "Weight"),
        "height": ("C25347", "Height"),
        "randomization": ("C15417", "Randomization"),
        "laboratory": ("C49286", "Laboratory Test"),
        "urinalysis": ("C79430", "Urinalysis"),
        "hba1c": ("C64849", "Hemoglobin A1c Measurement"),
        "adverse event": ("C41331", "Adverse Event"),
        "concomitant medication": ("C53630", "Concomitant Medication"),
        "medical history": ("C18772", "Medical History"),
    }
    
    with open(soa_path) as f:
        soa_data = json.load(f)
    
    timeline = soa_data.get("study", {}).get("versions", [{}])[0].get("timeline", {})
    activities = timeline.get("activities", [])
    
    enriched_count = 0
    for activity in activities:
        name = activity.get("name", activity.get("label", "")).lower()
        for term, (code, decode) in KNOWN_CODES.items():
            if term in name:
                activity["definedProcedures"] = [{
                    "id": f"proc_{activity.get('id', '')}",
                    "code": {"code": code, "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl", "decode": decode},
                    "instanceType": "Procedure"
                }]
                enriched_count += 1
                break
    
    # Save back
    with open(soa_path, 'w') as f:
        json.dump(soa_data, f, indent=2)
    
    logger.info(f"Enriched {enriched_count}/{len(activities)} activities with terminology codes")
    return {"enriched": enriched_count, "total": len(activities)}


def validate_schema(soa_path: str) -> dict:
    """
    Step 8: Validate JSON structure against USDM requirements.
    """
    import json
    
    with open(soa_path) as f:
        soa_data = json.load(f)
    
    issues = []
    warnings = []
    
    # Check wrapper fields
    for field in ["usdmVersion", "study"]:
        if field not in soa_data:
            issues.append(f"Missing: {field}")
    
    # Check timeline
    study = soa_data.get("study", {})
    versions = study.get("versions", [])
    if versions:
        timeline = versions[0].get("timeline", {})
        activities = {a.get("id"): a for a in timeline.get("activities", [])}
        timepoints = {t.get("id"): t for t in timeline.get("plannedTimepoints", [])}
        
        # Check linkage
        for at in timeline.get("activityTimepoints", []):
            if at.get("activityId") not in activities:
                issues.append(f"Invalid activityId: {at.get('activityId')}")
            if at.get("plannedTimepointId") not in timepoints:
                issues.append(f"Invalid plannedTimepointId: {at.get('plannedTimepointId')}")
    
    valid = len(issues) == 0
    logger.info(f"Schema validation: {'PASSED' if valid else 'FAILED'} ({len(issues)} issues)")
    
    return {"valid": valid, "issues": issues, "warnings": warnings}


def run_cdisc_conformance(soa_path: str, output_dir: str) -> dict:
    """
    Step 9: Run CDISC CORE conformance rules.
    """
    import subprocess
    from pathlib import Path
    
    core_exe = Path("tools/core/core/core.exe")
    if not core_exe.exists():
        logger.warning("CDISC CORE engine not installed")
        return {"error": "CORE not installed"}
    
    output_path = Path(output_dir) / "conformance_report"
    
    try:
        result = subprocess.run(
            [str(core_exe), "validate", "-s", "usdm", "-v", "4-0",
             "-dp", str(Path(soa_path).absolute()),
             "-o", str(output_path.absolute()), "-of", "JSON"],
            capture_output=True, text=True, cwd=str(core_exe.parent), timeout=300
        )
        
        if result.returncode == 0:
            logger.info("CDISC CORE validation completed")
            return {"success": True, "output": str(output_path) + ".json"}
        else:
            logger.warning(f"CORE validation failed: {result.stderr[:200]}")
            return {"success": False, "error": result.stderr[:500]}
    except Exception as e:
        logger.error(f"CORE validation error: {e}")
        return {"error": str(e)}
