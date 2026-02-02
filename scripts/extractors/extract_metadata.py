#!/usr/bin/env python3
"""
Extract Study Metadata from Protocol PDF.

Phase 2 of USDM Expansion - Study Identity & Metadata extraction.

Usage:
    python extract_metadata.py protocol.pdf
    python extract_metadata.py protocol.pdf --model gemini-2.5-pro
    python extract_metadata.py protocol.pdf --pages 0,1,2
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from extraction.metadata import extract_study_metadata, MetadataExtractionResult
from extraction.metadata.extractor import save_metadata_result
from core.pdf_utils import render_pages_to_images

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract study metadata from clinical protocol PDF"
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
        default="0,1,2",
        help="Comma-separated page numbers to extract from (0-indexed, default: 0,1,2)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: output/<protocol_name>)"
    )
    parser.add_argument(
        "--use-vision",
        action="store_true",
        help="Use vision model on rendered page images"
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
    
    # Parse pages
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
    logger.info("Protocol2USDM - Metadata Extraction (Phase 2)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Pages: {pages}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 60)
    
    # Optionally render title pages to images for vision
    title_images = None
    if args.use_vision:
        logger.info("Rendering title pages for vision extraction...")
        images_dir = output_dir / "title_pages"
        title_images = render_pages_to_images(
            str(pdf_path),
            pages,
            str(images_dir),
            prefix="title_page"
        )
        if title_images:
            logger.info(f"  Rendered {len(title_images)} images")
    
    # Extract metadata
    logger.info("Extracting study metadata...")
    result = extract_study_metadata(
        pdf_path=str(pdf_path),
        model_name=args.model,
        title_page_images=title_images,
        pages=pages,
    )
    
    # Save result
    output_path = output_dir / "2_study_metadata.json"
    save_metadata_result(result, str(output_path))
    
    # Display results
    logger.info("=" * 60)
    if result.success and result.metadata:
        logger.info("✅ Metadata extraction successful!")
        logger.info("")
        
        md = result.metadata
        
        # Titles
        if md.titles:
            logger.info("STUDY TITLES:")
            for t in md.titles:
                logger.info(f"  [{t.type.value}] {t.text[:80]}...")
        
        # Identifiers
        if md.identifiers:
            logger.info("")
            logger.info("IDENTIFIERS:")
            for i in md.identifiers:
                logger.info(f"  {i.text}")
        
        # Organizations
        if md.organizations:
            logger.info("")
            logger.info("ORGANIZATIONS:")
            for o in md.organizations:
                logger.info(f"  {o.name} ({o.type.value})")
        
        # Phase
        if md.study_phase:
            logger.info("")
            logger.info(f"STUDY PHASE: {md.study_phase.phase}")
        
        # Indication
        if md.indications:
            logger.info("")
            logger.info("INDICATIONS:")
            for ind in md.indications:
                rare = " [RARE DISEASE]" if ind.is_rare_disease else ""
                logger.info(f"  {ind.name}{rare}")
        
        # Study type
        if md.study_type:
            logger.info("")
            logger.info(f"STUDY TYPE: {md.study_type}")
        
    else:
        logger.error(f"❌ Metadata extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
