#!/usr/bin/env python3
"""
Standalone CLI for Execution Model Extraction

Extracts execution-level semantics from protocol PDFs:
- Time anchors (Day 1, First Dose, Randomization)
- Repetition patterns (daily, interval, cycles)
- Execution type classifications (WINDOW vs EPISODE)
- Sampling constraints

Usage:
    python extract_execution_model.py <pdf_path> [--output-dir <dir>] [--use-llm] [--model <model>]

Example:
    python extract_execution_model.py protocols/NCT12345.pdf --output-dir output/NCT12345 --use-llm
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extraction.execution import (
    extract_execution_model,
    create_execution_model_summary,
    ExecutionModelResult,
    validate_execution_model,
    create_validation_summary,
    export_to_csv,
    save_report,
    load_config,
    ExtractionConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract execution model from protocol PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction (heuristic only)
  python extract_execution_model.py protocol.pdf

  # With LLM enhancement
  python extract_execution_model.py protocol.pdf --use-llm

  # Save output to directory
  python extract_execution_model.py protocol.pdf --output-dir output/

  # Use specific model
  python extract_execution_model.py protocol.pdf --use-llm --model gemini-2.5-pro
        """
    )
    
    parser.add_argument(
        "pdf_path",
        help="Path to protocol PDF file"
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Directory to save output JSON"
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Run complete extraction with all options: LLM, validation, CSV export, and report"
    )
    parser.add_argument(
        "--sap",
        type=str,
        metavar="PATH",
        help="Path to SAP PDF for enhanced endpoint/variable extraction"
    )
    parser.add_argument(
        "--soa",
        type=str,
        metavar="PATH",
        help="Path to SOA extraction JSON for enhanced visit/encounter context"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for enhanced extraction (requires API key)"
    )
    parser.add_argument(
        "--model", "-m",
        default="gemini-2.5-pro",
        help="LLM model to use (default: gemini-2.5-pro)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output only JSON (no summary)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation checks on extracted data"
    )
    
    # Phase control flags
    phase_group = parser.add_argument_group("Phase Control", "Control which extraction phases to run")
    phase_group.add_argument(
        "--phase1-only",
        action="store_true",
        help="Run only Phase 1 (time anchors, repetitions, execution types)"
    )
    phase_group.add_argument(
        "--phase2-only",
        action="store_true",
        help="Run only Phase 2 (crossover, traversal, footnotes)"
    )
    phase_group.add_argument(
        "--phase3-only",
        action="store_true",
        help="Run only Phase 3 (endpoints, variables, state machine)"
    )
    phase_group.add_argument(
        "--skip-endpoints",
        action="store_true",
        help="Skip endpoint algorithm extraction"
    )
    phase_group.add_argument(
        "--skip-variables",
        action="store_true",
        help="Skip derived variable extraction"
    )
    phase_group.add_argument(
        "--skip-state-machine",
        action="store_true",
        help="Skip state machine generation"
    )
    
    # Export options
    export_group = parser.add_argument_group("Export Options", "Control output formats")
    export_group.add_argument(
        "--export-csv",
        action="store_true",
        help="Export data to CSV files (one per component)"
    )
    export_group.add_argument(
        "--report",
        action="store_true",
        help="Generate a Markdown summary report"
    )
    
    # Config options
    config_group = parser.add_argument_group("Configuration", "Load settings from file")
    config_group.add_argument(
        "--config", "-c",
        help="Path to config file (YAML or JSON)"
    )
    config_group.add_argument(
        "--create-config",
        metavar="PATH",
        help="Create a default config file at the specified path and exit"
    )
    config_group.add_argument(
        "--therapeutic-area",
        choices=["diabetes", "oncology", "cardiovascular", "immunology", "neurology", 
                 "respiratory", "infectious_disease", "psychiatry", "rare_disease", "dermatology"],
        help="Therapeutic area for enhanced pattern matching"
    )
    
    args = parser.parse_args()
    
    # Handle --create-config
    if args.create_config:
        from extraction.execution import create_default_config
        create_default_config(args.create_config)
        print(f"Created default config at: {args.create_config}")
        return 0
    
    # Load config if specified
    config = ExtractionConfig()
    if args.config:
        config = load_config(args.config)
        logger.info(f"Loaded config from: {args.config}")
    
    # Handle --complete flag (enables all options)
    if args.complete:
        args.use_llm = True
        args.validate = True
        args.export_csv = True
        args.report = True
        if args.sap:
            logger.info(f"Complete mode: enabling LLM, validation, CSV export, report + SAP ({args.sap})")
        else:
            logger.info("Complete mode: enabling LLM, validation, CSV export, and report")
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate PDF path
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.suffix.lower() == '.pdf':
        logger.warning(f"File may not be a PDF: {pdf_path}")
    
    # Create output directory if specified
    output_dir = None
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load SOA data if provided
    soa_data = None
    if args.soa:
        soa_path = Path(args.soa)
        if soa_path.exists():
            with open(soa_path, 'r', encoding='utf-8') as f:
                soa_data = json.load(f)
            logger.info(f"Loaded SOA data from: {soa_path}")
        else:
            logger.warning(f"SOA file not found: {soa_path}")
    
    # Run extraction
    logger.info(f"Extracting execution model from: {pdf_path}")
    
    result: ExecutionModelResult = extract_execution_model(
        pdf_path=str(pdf_path),
        model=args.model,
        use_llm=args.use_llm,
        output_dir=str(output_dir) if output_dir else None,
        sap_path=args.sap,
        soa_data=soa_data,
    )
    
    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        # Print summary
        print("\n" + "=" * 60)
        if result.success and result.data:
            print(create_execution_model_summary(result.data))
            print("\n" + "=" * 60)
            print(f"Pages analyzed: {len(result.pages_used)}")
            print(f"Model: {result.model_used}")
            
            if output_dir:
                print(f"\nOutput saved to: {output_dir / '11_execution_model.json'}")
        else:
            print("❌ Extraction failed")
            if result.error:
                print(f"Error: {result.error}")
            sys.exit(1)
        
        # Run validation if requested
        if args.validate and result.data:
            print("\n" + "=" * 60)
            validation_result = validate_execution_model(result.data)
            print(create_validation_summary(validation_result))
            
            # Save validation result
            if output_dir:
                validation_path = output_dir / "11_execution_model_validation.json"
                with open(validation_path, 'w', encoding='utf-8') as f:
                    json.dump(validation_result.to_dict(), f, indent=2)
                print(f"\nValidation saved to: {validation_path}")
        
        # Export to CSV if requested
        if args.export_csv and result.data and output_dir:
            print("\n" + "=" * 60)
            print("Exporting to CSV...")
            csv_files = export_to_csv(result.data, str(output_dir))
            print(f"Created {len(csv_files)} CSV files:")
            for name, path in csv_files.items():
                print(f"  • {name}: {Path(path).name}")
        
        # Generate report if requested
        if args.report and result.data and output_dir:
            print("\n" + "=" * 60)
            print("Generating report...")
            validation_for_report = None
            if args.validate:
                validation_for_report = validation_result
            report_path = save_report(
                data=result.data,
                output_path=str(output_dir / "11_execution_model_report.md"),
                protocol_name=pdf_path.stem,
                validation_result=validation_for_report,
            )
            print(f"Report saved to: {report_path}")
    
    # Return success
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
