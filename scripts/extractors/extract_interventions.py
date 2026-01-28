#!/usr/bin/env python3
"""
Extract Interventions & Products from Protocol PDF.

Phase 5 of USDM Expansion - Interventions, Products, Administration extraction.

Usage:
    python extract_interventions.py protocol.pdf
    python extract_interventions.py protocol.pdf --model gemini-2.5-pro
"""

import argparse
import logging
import sys
from pathlib import Path

from extraction.interventions import (
    extract_interventions,
    InterventionsExtractionResult,
)
from extraction.interventions.extractor import save_interventions_result, find_intervention_pages

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract interventions and products from clinical protocol PDF"
    )
    parser.add_argument("pdf_path", help="Path to the clinical protocol PDF")
    parser.add_argument("--model", "-m", default="gemini-2.5-pro", help="LLM model to use")
    parser.add_argument("--pages", "-p", default=None, help="Comma-separated page numbers (0-indexed)")
    parser.add_argument("--output-dir", "-o", help="Output directory")
    parser.add_argument("--find-pages-only", action="store_true", help="Only find intervention pages")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    if args.find_pages_only:
        pages = find_intervention_pages(str(pdf_path))
        if pages:
            logger.info(f"Found intervention content on pages: {[p+1 for p in pages]} (1-indexed)")
        sys.exit(0)
    
    pages = [int(p.strip()) for p in args.pages.split(",")] if args.pages else None
    output_dir = Path(args.output_dir) if args.output_dir else Path("output") / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("Protocol2USDM - Interventions Extraction (Phase 5)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info("=" * 60)
    
    result = extract_interventions(pdf_path=str(pdf_path), model_name=args.model, pages=pages)
    
    output_path = output_dir / "6_interventions.json"
    save_interventions_result(result, str(output_path))
    
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Interventions extraction successful!")
        logger.info("")
        
        data = result.data
        
        if data.interventions:
            logger.info(f"STUDY INTERVENTIONS ({len(data.interventions)}):")
            for int_ in data.interventions:
                logger.info(f"  • {int_.name} ({int_.role.value})")
        
        if data.products:
            logger.info("")
            logger.info(f"PRODUCTS ({len(data.products)}):")
            for prod in data.products:
                form = f" - {prod.dose_form.value}" if prod.dose_form else ""
                strength = f" {prod.strength}" if prod.strength else ""
                logger.info(f"  • {prod.name}{form}{strength}")
        
        if data.administrations:
            logger.info("")
            logger.info(f"ADMINISTRATIONS ({len(data.administrations)}):")
            for admin in data.administrations:
                route = f" ({admin.route.value})" if admin.route else ""
                logger.info(f"  • {admin.dose} {admin.dose_frequency}{route}")
        
        if data.substances:
            logger.info("")
            logger.info(f"SUBSTANCES ({len(data.substances)}):")
            for sub in data.substances:
                logger.info(f"  • {sub.name}")
    else:
        logger.error(f"❌ Extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
