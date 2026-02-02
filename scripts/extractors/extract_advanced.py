#!/usr/bin/env python3
"""
Extract Advanced Entities from Protocol PDF.

Phase 8 of USDM Expansion - Amendments, Geographic Scope, Sites.

Usage:
    python extract_advanced.py protocol.pdf
"""

import argparse
import logging
import sys
from pathlib import Path

from extraction.advanced import (
    extract_advanced_entities,
    AdvancedExtractionResult,
)
from extraction.advanced.extractor import save_advanced_result

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract amendments, geographic scope, and sites from clinical protocol PDF"
    )
    parser.add_argument("pdf_path", help="Path to the clinical protocol PDF")
    parser.add_argument("--model", "-m", default="gemini-2.5-pro", help="LLM model to use")
    parser.add_argument("--pages", "-p", default=None, help="Comma-separated page numbers (0-indexed)")
    parser.add_argument("--output-dir", "-o", help="Output directory")
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
    
    logger.info("=" * 60)
    logger.info("Protocol2USDM - Advanced Entities Extraction (Phase 8)")
    logger.info("=" * 60)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info("=" * 60)
    
    result = extract_advanced_entities(
        pdf_path=str(pdf_path),
        model_name=args.model,
        pages=pages,
    )
    
    output_path = output_dir / "8_advanced_entities.json"
    save_advanced_result(result, str(output_path))
    
    logger.info("=" * 60)
    if result.success and result.data:
        logger.info("✅ Advanced extraction successful!")
        logger.info("")
        
        data = result.data
        
        # Amendments
        if data.amendments:
            logger.info(f"AMENDMENTS ({len(data.amendments)}):")
            for amend in data.amendments:
                date = f" ({amend.effective_date})" if amend.effective_date else ""
                logger.info(f"  Amendment {amend.number}{date}")
                if amend.summary:
                    summary = amend.summary[:60] + "..." if len(amend.summary) > 60 else amend.summary
                    logger.info(f"    {summary}")
        
        # Geographic scope
        if data.geographic_scope:
            logger.info("")
            logger.info(f"GEOGRAPHIC SCOPE: {data.geographic_scope.scope_type}")
            if data.geographic_scope.regions:
                logger.info(f"  Regions: {', '.join(data.geographic_scope.regions)}")
        
        # Countries
        if data.countries:
            logger.info("")
            logger.info(f"COUNTRIES ({len(data.countries)}):")
            for country in data.countries[:10]:
                code = f" ({country.code})" if country.code else ""
                logger.info(f"  • {country.name}{code}")
            if len(data.countries) > 10:
                logger.info(f"  ... and {len(data.countries) - 10} more")
        
        # Sites
        if data.sites:
            logger.info("")
            logger.info(f"SITES ({len(data.sites)}):")
            for site in data.sites[:5]:
                logger.info(f"  • {site.name}")
            if len(data.sites) > 5:
                logger.info(f"  ... and {len(data.sites) - 5} more")
    else:
        logger.error(f"❌ Extraction failed: {result.error}")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Output saved to: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
