#!/usr/bin/env python3
"""
Extract Study Design Structure from Protocol PDF.

Phase 4 of USDM Expansion - Study Design, Arms, Cells, Cohorts extraction.

Usage:
    python extract_studydesign.py protocol.pdf
    python extract_studydesign.py protocol.pdf --model gemini-2.5-pro
    python extract_studydesign.py protocol.pdf --pages 2,3,4,5
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from extraction.studydesign import (
    extract_study_design,
    StudyDesignExtractionResult,
)
from extraction.studydesign.extractor import save_study_design_result, find_study_design_pages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract study design structure from clinical protocol PDF"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the clinical protocol PDF"
    )
    parser.add_argument(
        "--model", "-m",
        default="gemini-2.5-pro",
        help="LLM model to use (default: gemini-2.5-pro)"
    )
    parser.add_argument(
        "--pages", "-p",
        default=None,
        help="Comma-separated page numbers (0-indexed). Auto-detected if not specified."
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: output/<protocol_name>)"
    )
    parser.add_argument(
        "--find-pages-only",
        action="store_true",
        help="Only find study design pages, don't extract"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate PDF path
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    # Find pages only mode
    if args.find_pages_only:
        logger.info(f"Scanning {pdf_path} for study design pages...")
        pages = find_study_design_pages(str(pdf_path))
        if pages:
            logger.info(f"Found study design content on pages: {[p+1 for p in pages]} (1-indexed)")
        else:
            logger.warning("No study design pages detected")
        sys.exit(0)
    
    # Parse pages
    pages = None
    if args.pages:
        try:
            pages = [int(p.strip()) for p in args.pages.split(",")]
        except ValueError:
            logger.error(f"Invalid pages format: {args.pages}")
            sys.exit(1)
    
    # Set up output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("output") / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("Protocol2USDM - Study Design Extraction (Phase 4)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Pages: {'auto-detect' if pages is None else pages}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 60)
    
    # Extract study design
    logger.info("Extracting study design structure...")
    result = extract_study_design(
        pdf_path=str(pdf_path),
        model_name=args.model,
        pages=pages,
    )
    
    # Save result
    output_path = output_dir / "5_study_design.json"
    save_study_design_result(result, str(output_path))
    
    # Display results
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Study design extraction successful!")
        logger.info("")
        
        data = result.data
        
        # Study design overview
        if data.study_design:
            sd = data.study_design
            logger.info("STUDY DESIGN:")
            logger.info(f"  Type: {sd.trial_type}")
            if sd.blinding_schema:
                logger.info(f"  Blinding: {sd.blinding_schema.value}")
            if sd.randomization_type:
                logger.info(f"  Randomization: {sd.randomization_type.value}")
            if sd.allocation_ratio:
                logger.info(f"  Allocation Ratio: {sd.allocation_ratio.ratio}")
            if sd.control_type:
                logger.info(f"  Control: {sd.control_type.value}")
            if sd.therapeutic_areas:
                logger.info(f"  Therapeutic Areas: {', '.join(sd.therapeutic_areas)}")
        
        # Arms
        if data.arms:
            logger.info("")
            logger.info(f"STUDY ARMS ({len(data.arms)}):")
            for arm in data.arms:
                logger.info(f"  • {arm.name} ({arm.arm_type.value})")
                if arm.description:
                    desc = arm.description[:60] + "..." if len(arm.description) > 60 else arm.description
                    logger.info(f"    {desc}")
        
        # Cohorts
        if data.cohorts:
            logger.info("")
            logger.info(f"STUDY COHORTS ({len(data.cohorts)}):")
            for cohort in data.cohorts:
                logger.info(f"  • {cohort.name}")
                if cohort.characteristic:
                    char = cohort.characteristic[:60] + "..." if len(cohort.characteristic) > 60 else cohort.characteristic
                    logger.info(f"    {char}")
        
        # Cells summary
        if data.cells:
            logger.info("")
            logger.info(f"STUDY CELLS: {len(data.cells)} (arm × epoch combinations)")
        
    else:
        logger.error(f"❌ Study design extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Pages scanned: {[p+1 for p in result.pages_used]} (1-indexed)")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
