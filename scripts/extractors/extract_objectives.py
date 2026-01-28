#!/usr/bin/env python3
"""
Extract Objectives & Endpoints from Protocol PDF.

Phase 3 of USDM Expansion - Objectives, Endpoints, and Estimands extraction.

Usage:
    python extract_objectives.py protocol.pdf
    python extract_objectives.py protocol.pdf --model gemini-2.5-pro
    python extract_objectives.py protocol.pdf --pages 2,3,4,5
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from extraction.objectives import (
    extract_objectives_endpoints,
    ObjectivesExtractionResult,
)
from extraction.objectives.extractor import save_objectives_result, find_objectives_pages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract objectives and endpoints from clinical protocol PDF"
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
        help="Only find objectives pages, don't extract"
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
        logger.info(f"Scanning {pdf_path} for objectives pages...")
        pages = find_objectives_pages(str(pdf_path))
        if pages:
            logger.info(f"Found objectives content on pages: {[p+1 for p in pages]} (1-indexed)")
        else:
            logger.warning("No objectives pages detected")
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
    logger.info("Protocol2USDM - Objectives & Endpoints Extraction (Phase 3)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Pages: {'auto-detect' if pages is None else pages}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 60)
    
    # Extract objectives and endpoints
    logger.info("Extracting objectives and endpoints...")
    result = extract_objectives_endpoints(
        pdf_path=str(pdf_path),
        model_name=args.model,
        pages=pages,
    )
    
    # Save result
    output_path = output_dir / "4_objectives_endpoints.json"
    save_objectives_result(result, str(output_path))
    
    # Display results
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Objectives extraction successful!")
        logger.info("")
        
        data = result.data
        
        # Primary objectives
        logger.info(f"PRIMARY OBJECTIVES ({data.primary_objectives_count}):")
        for obj in data.primary_objectives:
            text_preview = obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
            logger.info(f"  • {text_preview}")
            for ep_id in obj.endpoint_ids:
                ep = next((e for e in data.endpoints if e.id == ep_id), None)
                if ep:
                    ep_preview = ep.text[:60] + "..." if len(ep.text) > 60 else ep.text
                    logger.info(f"    → Endpoint: {ep_preview}")
        
        # Secondary objectives
        if data.secondary_objectives:
            logger.info("")
            logger.info(f"SECONDARY OBJECTIVES ({data.secondary_objectives_count}):")
            for obj in data.secondary_objectives[:3]:  # Show first 3
                text_preview = obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
                logger.info(f"  • {text_preview}")
            if data.secondary_objectives_count > 3:
                logger.info(f"  ... and {data.secondary_objectives_count - 3} more")
        
        # Exploratory objectives
        if data.exploratory_objectives:
            logger.info("")
            logger.info(f"EXPLORATORY OBJECTIVES ({data.exploratory_objectives_count}):")
            for obj in data.exploratory_objectives[:2]:  # Show first 2
                text_preview = obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
                logger.info(f"  • {text_preview}")
            if data.exploratory_objectives_count > 2:
                logger.info(f"  ... and {data.exploratory_objectives_count - 2} more")
        
        # Estimands
        if data.estimands:
            logger.info("")
            logger.info(f"ESTIMANDS ({len(data.estimands)}):")
            for est in data.estimands:
                logger.info(f"  • {est.name}: {est.summary_measure}")
        
        # Summary
        logger.info("")
        logger.info(f"Total Endpoints: {len(data.endpoints)}")
        
    else:
        logger.error(f"❌ Objectives extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Pages scanned: {[p+1 for p in result.pages_used]} (1-indexed)")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
