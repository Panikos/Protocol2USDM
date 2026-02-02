#!/usr/bin/env python3
"""
Extract Document Structure & Abbreviations from Protocol PDF.

Phase 7 of USDM Expansion - Narrative structure, sections, abbreviations.

Usage:
    python extract_narrative.py protocol.pdf
    python extract_narrative.py protocol.pdf --abbreviations-only
    python extract_narrative.py protocol.pdf --structure-only
"""

import argparse
import logging
import sys
from pathlib import Path

from extraction.narrative import (
    extract_narrative_structure,
    NarrativeExtractionResult,
)
from extraction.narrative.extractor import save_narrative_result

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract document structure and abbreviations from clinical protocol PDF"
    )
    parser.add_argument("pdf_path", help="Path to the clinical protocol PDF")
    parser.add_argument("--model", "-m", default="gemini-2.5-pro", help="LLM model to use")
    parser.add_argument("--pages", "-p", default=None, help="Comma-separated page numbers (0-indexed)")
    parser.add_argument("--output-dir", "-o", help="Output directory")
    parser.add_argument("--abbreviations-only", action="store_true", help="Only extract abbreviations")
    parser.add_argument("--structure-only", action="store_true", help="Only extract document structure")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    pages = [int(p.strip()) for p in args.pages.split(",")] if args.pages else None
    output_dir = Path(args.output_dir) if args.output_dir else Path("output") / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine what to extract
    extract_abbrev = not args.structure_only
    extract_struct = not args.abbreviations_only
    
    logger.info("=" * 60)
    logger.info("Protocol2USDM - Narrative Structure Extraction (Phase 7)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Extract abbreviations: {extract_abbrev}")
    logger.info(f"Extract structure: {extract_struct}")
    logger.info("=" * 60)
    
    result = extract_narrative_structure(
        pdf_path=str(pdf_path),
        model_name=args.model,
        pages=pages,
        extract_abbreviations=extract_abbrev,
        extract_sections=extract_struct,
    )
    
    output_path = output_dir / "7_narrative_structure.json"
    save_narrative_result(result, str(output_path))
    
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Narrative extraction successful!")
        logger.info("")
        
        data = result.data
        
        # Document info
        if data.document:
            logger.info(f"DOCUMENT: {data.document.name}")
            if data.document.version:
                logger.info(f"  Version: {data.document.version}")
        
        # Sections
        if data.sections:
            logger.info("")
            logger.info(f"SECTIONS ({len(data.sections)}):")
            for sec in data.sections[:10]:
                num = f"{sec.section_number}. " if sec.section_number else ""
                logger.info(f"  {num}{sec.section_title or sec.name}")
            if len(data.sections) > 10:
                logger.info(f"  ... and {len(data.sections) - 10} more")
        
        # Abbreviations
        if data.abbreviations:
            logger.info("")
            logger.info(f"ABBREVIATIONS ({len(data.abbreviations)}):")
            for abbr in data.abbreviations[:10]:
                logger.info(f"  {abbr.abbreviated_text} = {abbr.expanded_text}")
            if len(data.abbreviations) > 10:
                logger.info(f"  ... and {len(data.abbreviations) - 10} more")
    else:
        logger.error(f"❌ Extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
