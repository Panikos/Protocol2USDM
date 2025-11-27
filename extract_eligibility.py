#!/usr/bin/env python3
"""
Extract Eligibility Criteria from Protocol PDF.

Phase 1 of USDM Expansion - Inclusion/Exclusion criteria extraction.

Usage:
    python extract_eligibility.py protocol.pdf
    python extract_eligibility.py protocol.pdf --model gemini-2.5-pro
    python extract_eligibility.py protocol.pdf --pages 10,11,12,13
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from extraction.eligibility import (
    extract_eligibility_criteria,
    EligibilityExtractionResult,
)
from extraction.eligibility.extractor import save_eligibility_result, find_eligibility_pages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract eligibility criteria from clinical protocol PDF"
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
        help="Only find eligibility pages, don't extract"
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
        logger.info(f"Scanning {pdf_path} for eligibility pages...")
        pages = find_eligibility_pages(str(pdf_path))
        if pages:
            logger.info(f"Found eligibility content on pages: {[p+1 for p in pages]} (1-indexed)")
        else:
            logger.warning("No eligibility pages detected")
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
    logger.info("Protocol2USDM - Eligibility Criteria Extraction (Phase 1)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Pages: {'auto-detect' if pages is None else pages}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 60)
    
    # Extract eligibility criteria
    logger.info("Extracting eligibility criteria...")
    result = extract_eligibility_criteria(
        pdf_path=str(pdf_path),
        model_name=args.model,
        pages=pages,
    )
    
    # Save result
    output_path = output_dir / "3_eligibility_criteria.json"
    save_eligibility_result(result, str(output_path))
    
    # Display results
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Eligibility extraction successful!")
        logger.info("")
        
        data = result.data
        
        # Inclusion criteria summary
        logger.info(f"INCLUSION CRITERIA ({data.inclusion_count}):")
        for crit in data.inclusion_criteria[:5]:  # Show first 5
            item = next((i for i in data.criterion_items if i.id == crit.criterion_item_id), None)
            if item:
                text_preview = item.text[:80] + "..." if len(item.text) > 80 else item.text
                logger.info(f"  [{crit.identifier}] {text_preview}")
        if data.inclusion_count > 5:
            logger.info(f"  ... and {data.inclusion_count - 5} more")
        
        # Exclusion criteria summary
        logger.info("")
        logger.info(f"EXCLUSION CRITERIA ({data.exclusion_count}):")
        for crit in data.exclusion_criteria[:5]:  # Show first 5
            item = next((i for i in data.criterion_items if i.id == crit.criterion_item_id), None)
            if item:
                text_preview = item.text[:80] + "..." if len(item.text) > 80 else item.text
                logger.info(f"  [{crit.identifier}] {text_preview}")
        if data.exclusion_count > 5:
            logger.info(f"  ... and {data.exclusion_count - 5} more")
        
        # Population info
        if data.population:
            logger.info("")
            logger.info("POPULATION:")
            pop = data.population
            if pop.planned_enrollment_number:
                logger.info(f"  Planned Enrollment: {pop.planned_enrollment_number}")
            if pop.planned_minimum_age:
                logger.info(f"  Minimum Age: {pop.planned_minimum_age}")
            if pop.planned_maximum_age:
                logger.info(f"  Maximum Age: {pop.planned_maximum_age}")
            if pop.planned_sex:
                logger.info(f"  Sex: {', '.join(pop.planned_sex)}")
            logger.info(f"  Healthy Subjects: {'Yes' if pop.includes_healthy_subjects else 'No'}")
        
    else:
        logger.error(f"❌ Eligibility extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Pages scanned: {[p+1 for p in result.pages_used]} (1-indexed)")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
