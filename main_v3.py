#!/usr/bin/env python3
"""
Protocol2USDM v3 - Refactored Pipeline with Phase Registry

This is a cleaner implementation using the phase registry pattern.
It maintains full backward compatibility with main_v2.py while:
- Eliminating duplicated phase-handling code
- Using a registry pattern for extensibility
- Cleaner separation of concerns

Usage:
    python main_v3.py protocol.pdf [--model gemini-2.5-pro] [--no-validate]
    python main_v3.py protocol.pdf --complete --sap sap.pdf --sites sites.csv
"""

import argparse
import logging
import os
import sys
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from core.logging_config import configure_logging

# Logging is configured later in main() after arg parsing.
# Provide a module-level logger that will inherit the root config.
logger = logging.getLogger(__name__)

from extraction import run_from_files, PipelineConfig
from core.constants import DEFAULT_MODEL, SYSTEM_NAME, SYSTEM_VERSION
from llm_providers import usage_tracker

# Import pipeline module (triggers phase registration)
from pipeline import PipelineOrchestrator, phase_registry
from pipeline.orchestrator import combine_to_full_usdm
from pipeline.phases import *  # noqa - triggers registration

# Import validation functions from core module
from core.validation import (
    validate_and_fix_schema,
    convert_ids_to_uuids,
    convert_provenance_to_uuids,
)
from extraction.execution.pipeline_integration import get_processing_warnings


def main():
    parser = argparse.ArgumentParser(
        description="Extract Schedule of Activities from clinical protocol PDF (v3 - Refactored)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main_v3.py protocol.pdf                    # SoA extraction only
    python main_v3.py protocol.pdf --soa              # SoA + validation + conformance
    python main_v3.py protocol.pdf --full-protocol    # Everything (SoA + all expansions + validation)
    python main_v3.py protocol.pdf --expansion-only --full-protocol  # Expansions only, no SoA
    python main_v3.py protocol.pdf --eligibility --objectives  # SoA + selected phases
        """
    )
    
    parser.add_argument("pdf_path", nargs="?", help="Path to the clinical protocol PDF")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"LLM model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--output-dir", "-o", help="Output directory (default: output/<protocol_name>_<timestamp>)")
    parser.add_argument("--pages", "-p", help="Comma-separated SoA page numbers (1-indexed)")
    parser.add_argument("--no-validate", action="store_true", help="Skip vision validation step")
    parser.add_argument("--remove-hallucinations", action="store_true", help="Remove cells not confirmed by vision")
    parser.add_argument("--confidence-threshold", type=float, default=0.7, help="Confidence threshold (default: 0.7)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--enrich", action="store_true", help="Enrich entities with NCI terminology codes")
    parser.add_argument("--update-evs-cache", action="store_true", help="Update the EVS terminology cache")
    parser.add_argument("--validate-schema", action="store_true", help="Validate output against USDM schema")
    parser.add_argument("--conformance", action="store_true", help="Run CDISC CORE conformance rules")
    parser.add_argument("--update-cache", action="store_true", help="Update CDISC CORE rules cache")
    parser.add_argument("--soa", action="store_true", help="Run full SoA pipeline including enrichment, validation, and conformance")
    
    # USDM Expansion flags
    expansion_group = parser.add_argument_group('USDM Expansion')
    expansion_group.add_argument("--metadata", action="store_true", help="Extract study metadata")
    expansion_group.add_argument("--eligibility", action="store_true", help="Extract eligibility criteria")
    expansion_group.add_argument("--objectives", action="store_true", help="Extract objectives & endpoints")
    expansion_group.add_argument("--studydesign", action="store_true", help="Extract study design structure")
    expansion_group.add_argument("--interventions", action="store_true", help="Extract interventions & products")
    expansion_group.add_argument("--narrative", action="store_true", help="Extract narrative structure")
    expansion_group.add_argument("--advanced", action="store_true", help="Extract amendments & geographic scope")
    expansion_group.add_argument("--full-protocol", action="store_true", help="Extract EVERYTHING")
    expansion_group.add_argument("--expansion-only", action="store_true", help="Run expansion phases only, skip SoA")
    expansion_group.add_argument("--procedures", action="store_true", help="Extract procedures & medical devices")
    expansion_group.add_argument("--scheduling", action="store_true", help="Extract scheduling logic & timing")
    expansion_group.add_argument("--docstructure", action="store_true", help="Extract document structure")
    expansion_group.add_argument("--amendmentdetails", action="store_true", help="Extract amendment details")
    expansion_group.add_argument("--execution", action="store_true", help="Extract execution model semantics")
    expansion_group.add_argument("--complete", action="store_true", help="Run COMPLETE extraction")
    expansion_group.add_argument("--parallel", action="store_true", help="Run independent phases in parallel")
    expansion_group.add_argument("--max-workers", type=int, default=4, help="Max parallel workers (default: 4)")
    
    # Logging options
    log_group = parser.add_argument_group('Logging')
    log_group.add_argument("--json-log", action="store_true", help="Emit structured JSON log lines to stderr")
    log_group.add_argument("--log-file", type=str, metavar="PATH", help="Write JSON logs to file")
    
    # Conditional sources
    conditional_group = parser.add_argument_group('Conditional Sources')
    conditional_group.add_argument("--sap", type=str, metavar="PATH", help="Path to SAP PDF")
    conditional_group.add_argument("--sites", type=str, metavar="PATH", help="Path to site list (CSV/Excel)")
    
    args = parser.parse_args()
    
    # Configure logging (must happen before any log output)
    configure_logging(
        json_mode=getattr(args, 'json_log', False),
        log_file=getattr(args, 'log_file', None),
        level=logging.DEBUG if getattr(args, 'verbose', False) else logging.INFO,
    )
    
    # Handle --update-cache
    if args.update_cache:
        _handle_cache_update()
        if not args.pdf_path:
            sys.exit(0)
    
    # Validate PDF path
    if not args.pdf_path:
        logger.error("PDF path is required. Use --help for usage.")
        sys.exit(1)
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    # Set up output directory
    protocol_name = Path(args.pdf_path).stem
    if args.output_dir:
        output_dir = args.output_dir
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("output", f"{protocol_name}_{timestamp}")
    
    # Parse page numbers
    soa_pages = None
    if args.pages:
        try:
            soa_pages = [int(p.strip()) - 1 for p in args.pages.split(",")]
            logger.info(f"Using specified SoA pages: {[p+1 for p in soa_pages]}")
        except ValueError:
            logger.error(f"Invalid page numbers: {args.pages}")
            sys.exit(1)
    
    # Configure pipeline
    config = PipelineConfig(
        model_name=args.model,
        validate_with_vision=not args.no_validate,
        remove_hallucinations=args.remove_hallucinations,
        hallucination_confidence_threshold=args.confidence_threshold,
        save_intermediate=True,
    )
    
    # Determine if any specific phases were requested
    any_specific_phase = any([
        args.metadata, args.eligibility, args.objectives, args.studydesign,
        args.interventions, args.narrative, args.advanced, args.procedures,
        args.scheduling, args.docstructure, args.amendmentdetails, args.execution,
        args.full_protocol, args.complete,
    ])
    
    # Default to --complete mode if no specific phases requested
    if not any_specific_phase and not args.expansion_only:
        args.complete = True
        logger.info("No specific phases requested - defaulting to complete mode")
    
    # Handle --complete flag
    if args.complete:
        args.full_protocol = True
        args.soa = True
        args.enrich = True
        args.validate_schema = True
        args.conformance = True
        logger.info("Complete mode: full protocol extraction + validation + conformance")
    
    # Build phases_to_run dict from registered phases
    phases_to_run = {}
    for phase_name in phase_registry.get_names():
        phase_name_lower = phase_name.lower()
        arg_name = phase_name_lower.replace('_', '')
        phases_to_run[phase_name_lower] = args.full_protocol or getattr(args, arg_name, False)
    
    run_any_expansion = any(phases_to_run.values())
    run_soa = not args.expansion_only
    
    # Print configuration
    logger.info("="*60)
    logger.info(f"{SYSTEM_NAME} v{SYSTEM_VERSION} - Refactored Pipeline (v3)")
    logger.info("="*60)
    logger.info(f"Input PDF: {args.pdf_path}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"SoA Extraction: {'Enabled' if run_soa else 'Disabled'}")
    if run_any_expansion:
        enabled = [k for k, v in phases_to_run.items() if v]
        logger.info(f"Expansion Phases: {', '.join(enabled)}")
    logger.info("="*60)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Write run manifest for reproducibility
    _write_run_manifest(output_dir, args, config, phases_to_run)
    
    # Run pipeline
    try:
        result = None
        soa_data = None
        
        # Run SoA extraction
        if run_soa:
            logger.info("\n" + "="*60)
            logger.info("SCHEDULE OF ACTIVITIES EXTRACTION")
            logger.info("="*60)
            usage_tracker.set_phase("SoA_Extraction")
            result = run_from_files(
                pdf_path=args.pdf_path,
                output_dir=output_dir,
                soa_pages=soa_pages,
                config=config,
            )
            
            if result.success and result.output_path:
                with open(result.output_path, 'r', encoding='utf-8') as f:
                    soa_data = json.load(f)
        else:
            existing_soa = os.path.join(output_dir, "9_final_soa.json")
            if os.path.exists(existing_soa):
                logger.info(f"Loading existing SoA from {existing_soa}")
                with open(existing_soa, 'r', encoding='utf-8') as f:
                    soa_data = json.load(f)
        
        # Add footnotes from header to soa_data
        soa_data = _merge_header_footnotes(soa_data, output_dir, args.pdf_path)
        
        # Print SoA results
        if result:
            _print_soa_results(result)
        
        # Run expansion phases using orchestrator
        expansion_results = {}
        if run_any_expansion:
            logger.info("\n" + "="*60)
            logger.info("USDM EXPANSION PHASES")
            logger.info("="*60)
            
            orchestrator = PipelineOrchestrator(usage_tracker=usage_tracker)
            
            if args.parallel:
                logger.info(f"Parallel mode enabled (max {args.max_workers} workers)")
                expansion_results = orchestrator.run_phases_parallel(
                    pdf_path=args.pdf_path,
                    output_dir=output_dir,
                    model=config.model_name,
                    phases_to_run=phases_to_run,
                    soa_data=soa_data,
                    max_workers=args.max_workers,
                )
            else:
                expansion_results = orchestrator.run_phases(
                    pdf_path=args.pdf_path,
                    output_dir=output_dir,
                    model=config.model_name,
                    phases_to_run=phases_to_run,
                    soa_data=soa_data,
                )
            
            # Print expansion summary
            success_count = sum(1 for k, r in expansion_results.items() 
                              if k != '_pipeline_context' and hasattr(r, 'success') and r.success)
            total_count = sum(1 for k in expansion_results if k != '_pipeline_context')
            logger.info(f"\n✓ Expansion phases: {success_count}/{total_count} successful")
        
        # Run conditional source extraction
        expansion_results = _run_conditional_sources(
            args, expansion_results, config, output_dir
        )
        
        # Combine outputs
        combined_usdm_path = None
        schema_validation_result = None
        schema_fixer_result = None
        usdm_result = None
        
        if args.full_protocol or run_any_expansion or soa_data:
            logger.info("\n" + "="*60)
            logger.info("COMBINING OUTPUTS")
            logger.info("="*60)
            combined_data, combined_usdm_path = combine_to_full_usdm(
                output_dir, soa_data, expansion_results, args.pdf_path
            )
            
            # Schema validation
            logger.info("\n" + "="*60)
            logger.info("SCHEMA VALIDATION & AUTO-FIX")
            logger.info("="*60)
            
            use_llm_for_fixes = not args.no_validate
            fixed_data, schema_validation_result, schema_fixer_result, usdm_result, id_map = validate_and_fix_schema(
                combined_data,
                output_dir,
                model=config.model_name,
                use_llm=use_llm_for_fixes,
            )
            
            # Save fixed data
            with open(combined_usdm_path, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            logger.info(f"  ✓ USDM output saved to: {combined_usdm_path}")
            
            prov_path = os.path.join(output_dir, "protocol_usdm_provenance.json")
            if os.path.exists(prov_path):
                logger.info(f"  ✓ Provenance file: protocol_usdm_provenance.json")
            
            combined_data = fixed_data
            
            # Render M11 DOCX
            try:
                from rendering.m11_renderer import render_m11_docx
                m11_docx_path = os.path.join(output_dir, "m11_protocol.docx")
                m11_mapping = combined_data.get("m11Mapping")
                m11_result = render_m11_docx(combined_data, m11_docx_path, m11_mapping)
                if m11_result.success:
                    logger.info(
                        f"  ✓ M11 DOCX rendered: m11_protocol.docx "
                        f"({m11_result.sections_with_content}/{m11_result.sections_rendered} sections, "
                        f"{m11_result.total_words} words)"
                    )
                else:
                    logger.warning(f"  ⚠ M11 DOCX rendering failed: {m11_result.error}")
            except Exception as e:
                logger.warning(f"  ⚠ M11 DOCX rendering skipped: {e}")
            
            # Save schema validation results
            _save_schema_validation(output_dir, schema_validation_result, schema_fixer_result, usdm_result)
        
        # Run post-processing
        validation_target = combined_usdm_path or (result.output_path if result else None)
        if validation_target:
            _run_post_processing(args, validation_target, output_dir, config, 
                               schema_validation_result, usdm_result)
            
            # Update computational execution status
            if combined_usdm_path and args.validate_schema and schema_validation_result is not None:
                _update_execution_status(combined_usdm_path, schema_validation_result)
        
        # Final summary
        _print_final_summary(result, expansion_results, schema_validation_result, 
                           schema_fixer_result, combined_usdm_path, output_dir, config,
                           run_soa, run_any_expansion)
        
        # Determine success
        soa_success = result.success if result else True
        expansion_success = all(r.success for k, r in expansion_results.items() 
                               if k != '_pipeline_context' and hasattr(r, 'success')) if expansion_results else True
        sys.exit(0 if (soa_success and expansion_success) else 1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _handle_cache_update():
    """Handle CDISC CORE cache update."""
    logger.info("Updating CDISC CORE rules cache...")
    from validation.cdisc_conformance import CORE_ENGINE_PATH
    import subprocess
    
    core_dir = CORE_ENGINE_PATH.parent
    api_key = os.environ.get('CDISC_LIBRARY_API_KEY') or os.environ.get('CDISC_API_KEY')
    
    if not api_key:
        logger.error("CDISC_API_KEY not found in .env file")
        sys.exit(1)
    
    try:
        result = subprocess.run(
            [str(CORE_ENGINE_PATH), "update-cache", "--apikey", api_key],
            capture_output=True, text=True, timeout=300, cwd=str(core_dir),
        )
        if result.returncode == 0:
            logger.info("✓ CDISC CORE cache updated successfully")
        else:
            logger.error(f"Cache update failed: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Cache update error: {e}")
        sys.exit(1)


def _merge_header_footnotes(soa_data, output_dir, pdf_path):
    """Merge footnotes from header structure into soa_data."""
    import re
    
    header_path = os.path.join(output_dir, "4_header_structure.json")
    header_data = None
    
    if os.path.exists(header_path):
        try:
            with open(header_path, 'r', encoding='utf-8') as f:
                header_data = json.load(f)
        except Exception:
            pass
    
    if soa_data and header_data and header_data.get('footnotes'):
        soa_data['footnotes'] = header_data['footnotes']
    
    # Hybrid footnote extraction
    try:
        from extraction.execution.footnote_condition_extractor import _extract_footnote_text
        from core.pdf_utils import extract_text_from_pages, get_page_count
        
        vision_footnotes = header_data.get('footnotes', []) if header_data else []
        vision_footnote_markers = set()
        
        for fn in vision_footnotes:
            marker_match = re.match(r'^([a-z])[\.\)]', fn.strip().lower())
            if marker_match:
                vision_footnote_markers.add(marker_match.group(1))
        
        # Find SoA pages
        soa_pages_list = []
        soa_images_dir = os.path.join(output_dir, "3_soa_images")
        if os.path.exists(soa_images_dir):
            for img_file in os.listdir(soa_images_dir):
                page_match = re.search(r'page_(\d+)', img_file)
                if page_match:
                    soa_pages_list.append(int(page_match.group(1)))
        
        if soa_pages_list:
            min_page = max(0, min(soa_pages_list) - 2)
            max_page = min(get_page_count(pdf_path), max(soa_pages_list) + 10)
            pages_to_scan = list(range(min_page, max_page))
            
            pdf_text = extract_text_from_pages(pdf_path, pages_to_scan)
            if pdf_text:
                pdf_footnotes = _extract_footnote_text(pdf_text)
                
                merged_footnotes = list(vision_footnotes)
                added_count = 0
                
                for marker, content in pdf_footnotes:
                    marker_clean = marker.lower().strip('[]().^')
                    if marker_clean not in vision_footnote_markers and len(marker_clean) == 1:
                        formatted = f"{marker_clean}. {content}"
                        merged_footnotes.append(formatted)
                        vision_footnote_markers.add(marker_clean)
                        added_count += 1
                
                if added_count > 0:
                    logger.info(f"Hybrid footnote extraction: added {added_count} footnotes")
                    if soa_data:
                        soa_data['footnotes'] = merged_footnotes
                    if header_data:
                        header_data['footnotes'] = merged_footnotes
                        with open(header_path, 'w', encoding='utf-8') as f:
                            json.dump(header_data, f, indent=2)
    except Exception as e:
        logger.debug(f"Hybrid footnote extraction skipped: {e}")
    
    return soa_data


def _write_run_manifest(output_dir, args, config, phases_to_run):
    """Write a run manifest for reproducibility and auditing."""
    import hashlib
    
    # Compute input file hash
    input_hash = None
    if args.pdf_path and os.path.exists(args.pdf_path):
        try:
            with open(args.pdf_path, 'rb') as f:
                input_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass
    
    # Get schema version info if available
    schema_info = None
    try:
        from core.usdm_schema_loader import USDMSchemaLoader
        schema_info = USDMSchemaLoader.get_schema_version_info()
    except Exception:
        pass
    
    manifest = {
        "tool": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
        "timestamp": datetime.now().isoformat(),
        "input": {
            "pdf_path": os.path.abspath(args.pdf_path) if args.pdf_path else None,
            "pdf_sha256": input_hash,
            "sap_path": os.path.abspath(args.sap) if getattr(args, 'sap', None) else None,
            "sites_path": os.path.abspath(args.sites) if getattr(args, 'sites', None) else None,
        },
        "configuration": {
            "model": config.model_name,
            "parallel": getattr(args, 'parallel', False),
            "max_workers": getattr(args, 'max_workers', 4),
            "validate_with_vision": not getattr(args, 'no_validate', False),
        },
        "phases": {name: enabled for name, enabled in phases_to_run.items()},
        "schema": schema_info,
    }
    
    manifest_path = os.path.join(output_dir, "run_manifest.json")
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        logger.info(f"Run manifest: {manifest_path}")
    except Exception as e:
        logger.warning(f"Failed to write run manifest: {e}")


def _print_soa_results(result):
    """Print SoA extraction results."""
    print()
    logger.info("="*60)
    if result.success:
        logger.info("SOA EXTRACTION COMPLETED SUCCESSFULLY")
    else:
        logger.error("SOA EXTRACTION COMPLETED WITH ERRORS")
    logger.info("="*60)
    
    logger.info(f"Activities extracted: {result.activities_count}")
    logger.info(f"Timepoints: {result.timepoints_count}")
    logger.info(f"Ticks: {result.ticks_count}")
    
    if result.validated:
        logger.info(f"Hallucinations removed: {result.hallucinations_removed}")
        logger.info(f"Possibly missed ticks: {result.missed_ticks_found}")
    
    if result.output_path:
        logger.info(f"Output: {result.output_path}")
    if result.provenance_path:
        logger.info(f"Provenance: {result.provenance_path}")
    
    if result.errors:
        logger.warning("Errors encountered:")
        for err in result.errors:
            logger.warning(f"  - {err}")
    
    logger.info("="*60)


def _run_conditional_sources(args, expansion_results, config, output_dir):
    """Run conditional source extraction (SAP, sites)."""
    if args.sap:
        logger.info("\n--- Conditional: SAP Analysis Populations ---")
        try:
            from extraction.conditional import extract_from_sap
            sap_result = extract_from_sap(args.sap, model=config.model_name, output_dir=output_dir)
            if sap_result.success:
                expansion_results['sap'] = sap_result
                logger.info(f"  ✓ SAP extraction ({sap_result.data.to_dict()['summary']['populationCount']} populations)")
            else:
                logger.warning(f"  ✗ SAP extraction failed: {sap_result.error}")
        except Exception as e:
            logger.warning(f"  ✗ SAP extraction error: {e}")
    
    if args.sites:
        logger.info("\n--- Conditional: Study Sites ---")
        try:
            from extraction.conditional import extract_from_sites
            sites_result = extract_from_sites(args.sites, output_dir=output_dir)
            if sites_result.success:
                expansion_results['sites'] = sites_result
                logger.info(f"  ✓ Sites extraction ({sites_result.data.to_dict()['summary']['siteCount']} sites)")
            else:
                logger.warning(f"  ✗ Sites extraction failed: {sites_result.error}")
        except Exception as e:
            logger.warning(f"  ✗ Sites extraction error: {e}")
    
    return expansion_results


def _save_schema_validation(output_dir, schema_validation_result, schema_fixer_result, usdm_result):
    """Save schema validation results."""
    schema_output_path = os.path.join(output_dir, "schema_validation.json")
    schema_output = {
        "valid": usdm_result.valid if usdm_result else (schema_validation_result.valid if schema_validation_result else False),
        "schemaVersion": "4.0",
        "validator": "usdm_pydantic" if usdm_result else "openapi_custom",
        "summary": {
            "errorsCount": usdm_result.error_count if usdm_result else 0,
            "warningsCount": usdm_result.warning_count if usdm_result else 0,
        },
        "issues": [i.to_dict() for i in (usdm_result.issues if usdm_result else 
                                        (schema_validation_result.issues if schema_validation_result else []))],
    }
    
    if schema_fixer_result:
        schema_output["fixerSummary"] = {
            "originalIssues": schema_fixer_result.original_issues,
            "fixedIssues": schema_fixer_result.fixed_issues,
            "remainingIssues": schema_fixer_result.remaining_issues,
            "iterations": schema_fixer_result.iterations,
        }
        schema_output["fixesApplied"] = [f.to_dict() for f in schema_fixer_result.fixes_applied]
        schema_output["unfixableIssues"] = [i.to_dict() for i in schema_fixer_result.unfixable_issues]
    
    with open(schema_output_path, 'w', encoding='utf-8') as f:
        json.dump(schema_output, f, indent=2, ensure_ascii=False)
    logger.info(f"  Schema validation report: {schema_output_path}")


def _run_post_processing(args, validation_target, output_dir, config, 
                        schema_validation_result, usdm_result):
    """Run post-processing steps (enrichment, validation, conformance)."""
    run_enrich = args.enrich or args.soa or args.full_protocol
    run_validate = args.validate_schema or args.soa or args.full_protocol
    run_conform = args.conformance or args.soa or args.full_protocol
    
    if run_enrich:
        logger.info("\n--- Step 7: Terminology Enrichment ---")
        from enrichment.terminology import enrich_terminology as enrich_fn, update_evs_cache
        
        if args.update_evs_cache:
            logger.info("  Updating EVS terminology cache...")
            cache_result = update_evs_cache()
            logger.info(f"  Cache updated: {cache_result.get('success', 0)} codes fetched")
        
        enrich_result = enrich_fn(validation_target, output_dir=output_dir)
        enriched = enrich_result.get('enriched', 0)
        total = enrich_result.get('total_entities', 0)
        if enriched > 0:
            logger.info(f"  ✓ Enriched {enriched}/{total} entities with NCI codes")
        else:
            logger.info(f"  No entities required enrichment")
    
    if run_validate:
        if schema_validation_result is not None:
            logger.info("\n--- Step 8: Schema Validation (already completed) ---")
            if usdm_result and usdm_result.valid:
                logger.info(f"  ✓ Schema validation PASSED")
            elif usdm_result:
                logger.warning(f"  Schema validation: {usdm_result.error_count} errors, {usdm_result.warning_count} warnings")
        else:
            logger.info("\n--- Step 8: Schema Validation ---")
            with open(validation_target, 'r', encoding='utf-8') as f:
                target_data = json.load(f)
            
            fixed_data, _, _, usdm_result, _ = validate_and_fix_schema(
                target_data, output_dir, model=config.model_name, use_llm=not args.no_validate
            )
            
            with open(validation_target, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            
            if usdm_result and usdm_result.valid:
                logger.info(f"  ✓ Schema validation PASSED")
            else:
                logger.warning(f"  Schema validation found issues")
    
    if run_conform:
        logger.info("\n--- Step 9: CDISC Conformance ---")
        from validation.cdisc_conformance import run_cdisc_conformance as conform_fn
        conform_result = conform_fn(validation_target, output_dir)
        if conform_result.get('success'):
            issues = conform_result.get('issues', 0)
            warnings = conform_result.get('warnings', 0)
            if issues == 0 and warnings == 0:
                logger.info(f"  ✓ Conformance passed - no issues found")
            else:
                logger.info(f"  Conformance: {issues} errors, {warnings} warnings")
            logger.info(f"  ✓ Conformance report: {output_dir}/conformance_report.json")
        else:
            error_msg = conform_result.get('error', 'Unknown error')
            logger.warning(f"  ✗ CDISC CORE failed: {error_msg}")


def _update_execution_status(combined_usdm_path, schema_validation_result):
    """Update computational execution status."""
    with open(combined_usdm_path, 'r', encoding='utf-8') as f:
        final_data = json.load(f)
    
    if "computationalExecution" not in final_data:
        final_data["computationalExecution"] = {}
    
    final_data["computationalExecution"]["validationStatus"] = \
        "complete" if schema_validation_result.valid else "issues_found"
    
    with open(combined_usdm_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)


def _print_final_summary(result, expansion_results, schema_validation_result, 
                        schema_fixer_result, combined_usdm_path, output_dir, config,
                        run_soa, run_any_expansion):
    """Print final extraction summary."""
    logger.info("\n" + "="*60)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*60)
    
    if run_soa:
        logger.info(f"SoA: {'✓ Success' if (result and result.success) else '✗ Failed'}")
    
    if run_any_expansion:
        exp_success = sum(1 for k, r in expansion_results.items() 
                        if k != '_pipeline_context' and hasattr(r, 'success') and r.success)
        exp_total = sum(1 for k in expansion_results if k != '_pipeline_context')
        logger.info(f"Expansion: {exp_success}/{exp_total} phases successful")
    
    # Schema validation summary
    if schema_validation_result is not None:
        if schema_validation_result.valid:
            logger.info(f"Schema: ✓ Valid (USDM {schema_validation_result.usdm_version_expected})")
        else:
            logger.info(f"Schema: ⚠ {schema_validation_result.error_count} errors, "
                       f"{schema_validation_result.warning_count} warnings")
        if schema_fixer_result and schema_fixer_result.fixed_issues > 0:
            logger.info(f"  Auto-fixed: {schema_fixer_result.fixed_issues} issues")
    
    # Processing issues
    all_processing_issues = []
    if result and hasattr(result, 'processing_issues') and result.processing_issues:
        all_processing_issues.extend(result.processing_issues)
    
    execution_warnings = get_processing_warnings()
    
    all_issues_for_report = []
    for issue in all_processing_issues:
        all_issues_for_report.append({
            'phase': issue.phase,
            'issue_type': issue.issue_type,
            'message': issue.message,
            'is_known_limitation': issue.is_known_limitation,
            'fallback_used': issue.fallback_used,
        })
    
    for warn in execution_warnings:
        all_issues_for_report.append({
            'phase': warn.get('phase', 'execution_model'),
            'issue_type': warn.get('issue_type', 'warning'),
            'message': warn.get('message', ''),
            'is_known_limitation': False,
            'fallback_used': None,
            'details': warn.get('details', {}),
        })
    
    if all_issues_for_report:
        logger.info("")
        logger.warning("⚠ PROCESSING ISSUES (non-blocking):")
        for issue in all_issues_for_report:
            known_tag = " [KNOWN LIMITATION]" if issue.get('is_known_limitation') else ""
            logger.warning(f"  • {issue['phase']}: {issue['issue_type']}{known_tag}")
            logger.warning(f"    {issue['message']}")
        
        processing_report_path = os.path.join(output_dir, "processing_report.json")
        with open(processing_report_path, 'w') as f:
            json.dump({
                'processing_issues': all_issues_for_report,
                'total_issues': len(all_issues_for_report),
                'known_limitations': sum(1 for i in all_issues_for_report if i.get('is_known_limitation')),
            }, f, indent=2)
        logger.info(f"  Processing report: {processing_report_path}")
    
    if combined_usdm_path:
        logger.info(f"Golden Standard Output: {combined_usdm_path}")
    logger.info("="*60)
    
    # Token usage
    if usage_tracker.call_count > 0:
        usage_tracker.print_summary(model=config.model_name)
        usage_file = os.path.join(output_dir, "token_usage.json")
        with open(usage_file, 'w') as f:
            json.dump(usage_tracker.get_summary(), f, indent=2)
        logger.info(f"Token usage saved to: {usage_file}")


if __name__ == "__main__":
    main()
