#!/usr/bin/env python3
"""
Protocol2USDM v2 - Simplified Pipeline

This is a cleaner, modular implementation of the SoA extraction pipeline.
It follows the original architectural intent:
- Vision extracts STRUCTURE (headers, groups)
- Text extracts DATA (activities, ticks) using structure as anchor
- Vision validates text extraction
- Output is schema-compliant USDM JSON

Usage:
    python main_v2.py protocol.pdf [--model gemini-2.5-pro] [--no-validate]
    
Compared to main.py, this version:
- Uses modular extraction components from extraction/
- Has cleaner separation of concerns
- Produces simpler, more debuggable output
- Follows the original design intent
"""

import argparse
import logging
import os
import sys
import json
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Import from new modular structure
from extraction import run_from_files, PipelineConfig, PipelineResult
from core.constants import DEFAULT_MODEL

# Import expansion modules
from extraction.metadata import extract_study_metadata
from extraction.metadata.extractor import save_metadata_result
from extraction.eligibility import extract_eligibility_criteria
from extraction.eligibility.extractor import save_eligibility_result
from extraction.objectives import extract_objectives_endpoints
from extraction.objectives.extractor import save_objectives_result
from extraction.studydesign import extract_study_design
from extraction.studydesign.extractor import save_study_design_result
from extraction.interventions import extract_interventions
from extraction.interventions.extractor import save_interventions_result
from extraction.narrative import extract_narrative_structure
from extraction.narrative.extractor import save_narrative_result
from extraction.advanced import extract_advanced_entities
from extraction.advanced.extractor import save_advanced_result
from extraction.confidence import (
    calculate_metadata_confidence,
    calculate_eligibility_confidence,
    calculate_objectives_confidence,
    calculate_studydesign_confidence,
    calculate_interventions_confidence,
    calculate_narrative_confidence,
    calculate_advanced_confidence,
)


def run_expansion_phases(
    pdf_path: str,
    output_dir: str,
    model: str,
    phases: dict,
) -> dict:
    """
    Run requested expansion phases.
    
    Args:
        pdf_path: Path to protocol PDF
        output_dir: Output directory
        model: LLM model name
        phases: Dict of phase_name -> bool indicating which to run
    
    Returns:
        Dict of phase_name -> extraction result
    """
    results = {}
    
    if phases.get('metadata'):
        logger.info("\n--- Expansion: Study Metadata (Phase 2) ---")
        result = extract_study_metadata(pdf_path, model_name=model)
        save_metadata_result(result, os.path.join(output_dir, "2_study_metadata.json"))
        results['metadata'] = result
        if result.success and result.metadata:
            conf = calculate_metadata_confidence(result.metadata)
            logger.info(f"  ✓ Metadata extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Metadata extraction failed")
    
    if phases.get('eligibility'):
        logger.info("\n--- Expansion: Eligibility Criteria (Phase 1) ---")
        result = extract_eligibility_criteria(pdf_path, model_name=model)
        save_eligibility_result(result, os.path.join(output_dir, "3_eligibility_criteria.json"))
        results['eligibility'] = result
        if result.success and result.data:
            conf = calculate_eligibility_confidence(result.data)
            logger.info(f"  ✓ Eligibility extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Eligibility extraction failed")
    
    if phases.get('objectives'):
        logger.info("\n--- Expansion: Objectives & Endpoints (Phase 3) ---")
        result = extract_objectives_endpoints(pdf_path, model_name=model)
        save_objectives_result(result, os.path.join(output_dir, "4_objectives_endpoints.json"))
        results['objectives'] = result
        if result.success and result.data:
            conf = calculate_objectives_confidence(result.data)
            logger.info(f"  ✓ Objectives extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Objectives extraction failed")
    
    if phases.get('studydesign'):
        logger.info("\n--- Expansion: Study Design (Phase 4) ---")
        result = extract_study_design(pdf_path, model_name=model)
        save_study_design_result(result, os.path.join(output_dir, "5_study_design.json"))
        results['studydesign'] = result
        if result.success and result.data:
            conf = calculate_studydesign_confidence(result.data)
            logger.info(f"  ✓ Study design extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Study design extraction failed")
    
    if phases.get('interventions'):
        logger.info("\n--- Expansion: Interventions (Phase 5) ---")
        result = extract_interventions(pdf_path, model_name=model)
        save_interventions_result(result, os.path.join(output_dir, "6_interventions.json"))
        results['interventions'] = result
        if result.success and result.data:
            conf = calculate_interventions_confidence(result.data)
            logger.info(f"  ✓ Interventions extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Interventions extraction failed")
    
    if phases.get('narrative'):
        logger.info("\n--- Expansion: Narrative Structure (Phase 7) ---")
        result = extract_narrative_structure(pdf_path, model_name=model)
        save_narrative_result(result, os.path.join(output_dir, "7_narrative_structure.json"))
        results['narrative'] = result
        if result.success and result.data:
            conf = calculate_narrative_confidence(result.data)
            logger.info(f"  ✓ Narrative extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Narrative extraction failed")
    
    if phases.get('advanced'):
        logger.info("\n--- Expansion: Advanced Entities (Phase 8) ---")
        result = extract_advanced_entities(pdf_path, model_name=model)
        save_advanced_result(result, os.path.join(output_dir, "8_advanced_entities.json"))
        results['advanced'] = result
        if result.success and result.data:
            conf = calculate_advanced_confidence(result.data)
            logger.info(f"  ✓ Advanced extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Advanced extraction failed")
    
    return results


def combine_to_full_usdm(
    output_dir: str,
    soa_data: dict = None,
    expansion_results: dict = None,
) -> dict:
    """
    Combine SoA and expansion results into unified USDM JSON.
    """
    from datetime import datetime
    
    combined = {
        "usdmVersion": "4.0",
        "generatedAt": datetime.now().isoformat(),
        "generator": "Protocol2USDM v6.0",
        "study": {},
        "studyDesigns": [],
    }
    
    # Add Study Metadata
    if expansion_results and expansion_results.get('metadata'):
        r = expansion_results['metadata']
        if r.success and r.metadata:
            md = r.metadata
            combined["study"] = {
                "studyTitles": [t.to_dict() for t in md.titles],
                "studyIdentifiers": [i.to_dict() for i in md.identifiers],
                "organizations": [o.to_dict() for o in md.organizations],
            }
            if md.study_phase:
                combined["study"]["studyPhase"] = md.study_phase.to_dict()
            if md.indications:
                combined["study"]["indications"] = [i.to_dict() for i in md.indications]
    
    # Build StudyDesign container
    study_design = {"id": "sd_1", "instanceType": "InterventionalStudyDesign"}
    
    # Add Study Design Structure
    if expansion_results and expansion_results.get('studydesign'):
        r = expansion_results['studydesign']
        if r.success and r.data:
            sd = r.data
            if sd.study_design:
                if sd.study_design.blinding_schema:
                    study_design["blindingSchema"] = {"code": sd.study_design.blinding_schema.value}
                if sd.study_design.randomization_type:
                    study_design["randomizationType"] = {"code": sd.study_design.randomization_type.value}
            study_design["studyArms"] = [a.to_dict() for a in sd.arms]
            study_design["studyCohorts"] = [c.to_dict() for c in sd.cohorts]
            study_design["studyCells"] = [c.to_dict() for c in sd.cells]
    
    # Add Eligibility Criteria
    if expansion_results and expansion_results.get('eligibility'):
        r = expansion_results['eligibility']
        if r.success and r.data:
            study_design["eligibilityCriteria"] = [c.to_dict() for c in r.data.criteria]
            if r.data.population:
                study_design["studyDesignPopulation"] = r.data.population.to_dict()
    
    # Add Objectives & Endpoints
    if expansion_results and expansion_results.get('objectives'):
        r = expansion_results['objectives']
        if r.success and r.data:
            study_design["objectives"] = [o.to_dict() for o in r.data.objectives]
            study_design["endpoints"] = [e.to_dict() for e in r.data.endpoints]
            if r.data.estimands:
                study_design["estimands"] = [e.to_dict() for e in r.data.estimands]
    
    # Add Interventions
    if expansion_results and expansion_results.get('interventions'):
        r = expansion_results['interventions']
        if r.success and r.data:
            study_design["studyInterventions"] = [i.to_dict() for i in r.data.interventions]
            combined["administrableProducts"] = [p.to_dict() for p in r.data.products]
            combined["administrations"] = [a.to_dict() for a in r.data.administrations]
            combined["substances"] = [s.to_dict() for s in r.data.substances]
    
    # Add SoA data
    if soa_data:
        if "studyDesigns" in soa_data and soa_data["studyDesigns"]:
            soa_design = soa_data["studyDesigns"][0]
            for key in ["scheduleTimelines", "encounters", "activities"]:
                if key in soa_design:
                    study_design[key] = soa_design[key]
    
    combined["studyDesigns"] = [study_design]
    
    # Add Narrative Content
    if expansion_results and expansion_results.get('narrative'):
        r = expansion_results['narrative']
        if r.success and r.data:
            combined["narrativeContents"] = [s.to_dict() for s in r.data.sections]
            combined["abbreviations"] = [a.to_dict() for a in r.data.abbreviations]
            if r.data.document:
                combined["studyDefinitionDocument"] = r.data.document.to_dict()
    
    # Add Advanced Entities
    if expansion_results and expansion_results.get('advanced'):
        r = expansion_results['advanced']
        if r.success and r.data:
            if r.data.amendments:
                combined["studyAmendments"] = [a.to_dict() for a in r.data.amendments]
            if r.data.geographic_scope:
                combined["geographicScope"] = r.data.geographic_scope.to_dict()
            if r.data.countries:
                combined["countries"] = [c.to_dict() for c in r.data.countries]
    
    # Add computational execution metadata
    combined["computationalExecution"] = {
        "ready": True,
        "supportedSystems": ["EDC", "ePRO", "CTMS", "RTSM"],
        "validationStatus": "pending",
    }
    
    # Save combined output as protocol_usdm.json (golden standard)
    output_path = os.path.join(output_dir, "protocol_usdm.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Combined USDM saved to: {output_path}")
    return combined, output_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract Schedule of Activities from clinical protocol PDF (v2 - Simplified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main_v2.py protocol.pdf                    # SoA only (default)
    python main_v2.py protocol.pdf --metadata         # SoA + study metadata
    python main_v2.py protocol.pdf --full-protocol    # Everything (SoA + all expansions)
    python main_v2.py protocol.pdf --expansion-only   # All expansions, no SoA
    python main_v2.py protocol.pdf --eligibility --objectives  # SoA + selected phases
        """
    )
    
    parser.add_argument(
        "pdf_path",
        help="Path to the clinical protocol PDF"
    )
    
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"LLM model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: output/<protocol_name>)"
    )
    
    parser.add_argument(
        "--pages", "-p",
        help="Comma-separated SoA page numbers (0-indexed). If not provided, will analyze all pages."
    )
    
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip vision validation step"
    )
    
    parser.add_argument(
        "--keep-hallucinations",
        action="store_true",
        help="Don't remove probable hallucinations from output"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for removing hallucinations (default: 0.7)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--view",
        action="store_true",
        help="Launch Streamlit viewer after extraction"
    )
    
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Don't launch Streamlit viewer (default behavior)"
    )
    
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich activities with NCI terminology codes (Step 7)"
    )
    
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate output against USDM schema (Step 8)"
    )
    
    parser.add_argument(
        "--conformance",
        action="store_true",
        help="Run CDISC CORE conformance rules (Step 9)"
    )
    
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline including enrichment, validation, and conformance (Steps 7-9)"
    )
    
    # USDM Expansion flags (v6.0)
    expansion_group = parser.add_argument_group('USDM Expansion (v6.0)')
    expansion_group.add_argument(
        "--metadata",
        action="store_true",
        help="Extract study metadata (Phase 2)"
    )
    expansion_group.add_argument(
        "--eligibility",
        action="store_true",
        help="Extract eligibility criteria (Phase 1)"
    )
    expansion_group.add_argument(
        "--objectives",
        action="store_true",
        help="Extract objectives & endpoints (Phase 3)"
    )
    expansion_group.add_argument(
        "--studydesign",
        action="store_true",
        help="Extract study design structure (Phase 4)"
    )
    expansion_group.add_argument(
        "--interventions",
        action="store_true",
        help="Extract interventions & products (Phase 5)"
    )
    expansion_group.add_argument(
        "--narrative",
        action="store_true",
        help="Extract narrative structure & abbreviations (Phase 7)"
    )
    expansion_group.add_argument(
        "--advanced",
        action="store_true",
        help="Extract amendments & geographic scope (Phase 8)"
    )
    expansion_group.add_argument(
        "--full-protocol",
        action="store_true",
        help="Extract EVERYTHING: SoA + all expansion phases"
    )
    expansion_group.add_argument(
        "--expansion-only",
        action="store_true",
        help="Run expansion phases only, skip SoA extraction"
    )
    
    args = parser.parse_args()
    
    # Validate PDF path
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    # Set up output directory
    protocol_name = Path(args.pdf_path).stem
    output_dir = args.output_dir or os.path.join("output", protocol_name)
    
    # Parse page numbers if provided
    soa_pages = None
    if args.pages:
        try:
            soa_pages = [int(p.strip()) for p in args.pages.split(",")]
            logger.info(f"Using specified SoA pages: {soa_pages}")
        except ValueError:
            logger.error(f"Invalid page numbers: {args.pages}")
            sys.exit(1)
    
    # Configure pipeline
    config = PipelineConfig(
        model_name=args.model,
        validate_with_vision=not args.no_validate,
        remove_hallucinations=not args.keep_hallucinations,
        hallucination_confidence_threshold=args.confidence_threshold,
        save_intermediate=True,
    )
    
    # Determine which expansion phases to run
    run_any_expansion = (args.full_protocol or args.expansion_only or 
                         args.metadata or args.eligibility or args.objectives or
                         args.studydesign or args.interventions or args.narrative or args.advanced)
    
    expansion_phases = {
        'metadata': args.full_protocol or args.metadata,
        'eligibility': args.full_protocol or args.eligibility,
        'objectives': args.full_protocol or args.objectives,
        'studydesign': args.full_protocol or args.studydesign,
        'interventions': args.full_protocol or args.interventions,
        'narrative': args.full_protocol or args.narrative,
        'advanced': args.full_protocol or args.advanced,
    }
    
    run_soa = not args.expansion_only
    
    # Print configuration
    logger.info("="*60)
    logger.info("Protocol2USDM v6.0 - Full Protocol Extraction")
    logger.info("="*60)
    logger.info(f"Input PDF: {args.pdf_path}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"SoA Extraction: {'Enabled' if run_soa else 'Disabled'}")
    if run_any_expansion:
        enabled = [k for k, v in expansion_phases.items() if v]
        logger.info(f"Expansion Phases: {', '.join(enabled)}")
    logger.info("="*60)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Run pipeline
    try:
        result = None
        soa_data = None
        
        # Run SoA extraction if not skipped
        if run_soa:
            logger.info("\n" + "="*60)
            logger.info("SCHEDULE OF ACTIVITIES EXTRACTION")
            logger.info("="*60)
            result = run_from_files(
                pdf_path=args.pdf_path,
                output_dir=output_dir,
                soa_pages=soa_pages,
                config=config,
            )
            
            # Load SoA data for combining
            if result.success and result.output_path:
                with open(result.output_path, 'r') as f:
                    soa_data = json.load(f)
        else:
            # Check for existing SoA
            existing_soa = os.path.join(output_dir, "9_final_soa.json")
            if os.path.exists(existing_soa):
                logger.info(f"Loading existing SoA from {existing_soa}")
                with open(existing_soa, 'r') as f:
                    soa_data = json.load(f)
        
        # Print SoA results
        if result:
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
        
        # Run expansion phases if requested
        expansion_results = {}
        if run_any_expansion:
            logger.info("\n" + "="*60)
            logger.info("USDM EXPANSION PHASES")
            logger.info("="*60)
            
            expansion_results = run_expansion_phases(
                pdf_path=args.pdf_path,
                output_dir=output_dir,
                model=config.model_name,
                phases=expansion_phases,
            )
            
            # Print expansion summary
            success_count = sum(1 for r in expansion_results.values() if r.success)
            total_count = len(expansion_results)
            logger.info(f"\n✓ Expansion phases: {success_count}/{total_count} successful")
        
        # Combine outputs if full-protocol
        combined_usdm_path = None
        if args.full_protocol or (run_any_expansion and soa_data):
            logger.info("\n" + "="*60)
            logger.info("COMBINING OUTPUTS")
            logger.info("="*60)
            combined_data, combined_usdm_path = combine_to_full_usdm(output_dir, soa_data, expansion_results)
        
        # Determine which output to validate
        # For full-protocol: validate combined output
        # For SoA-only: validate SoA output
        validation_target = combined_usdm_path if combined_usdm_path else (result.output_path if result else None)
        
        # Run post-processing steps if requested
        if validation_target:
            run_enrich = args.enrich or args.full or args.full_protocol
            run_validate = args.validate_schema or args.full or args.full_protocol
            run_conform = args.conformance or args.full or args.full_protocol
            
            if run_enrich:
                logger.info("\n--- Step 7: Terminology Enrichment ---")
                from enrichment.terminology import enrich_terminology as enrich_fn
                enrich_result = enrich_fn(validation_target)
                logger.info(f"  Enriched {enrich_result.get('enriched', 0)} entities")
            
            if run_validate:
                logger.info("\n--- Step 8: Schema Validation ---")
                from validation.schema_validator import validate_schema as validate_fn
                schema_result = validate_fn(validation_target)
                if schema_result.get('valid'):
                    logger.info(f"  ✓ Schema validation PASSED ({schema_result.get('entityCount', 0)} entities)")
                else:
                    logger.warning(f"  Schema validation found {len(schema_result.get('issues', []))} issues")
                # Save result
                schema_path = os.path.join(output_dir, "schema_validation.json")
                with open(schema_path, 'w') as f:
                    json.dump(schema_result, f, indent=2)
            
            if run_conform:
                logger.info("\n--- Step 9: CDISC Conformance ---")
                from validation.cdisc_conformance import run_cdisc_conformance as conform_fn
                conform_result = conform_fn(validation_target, output_dir)
                if conform_result.get('success'):
                    logger.info(f"  ✓ Conformance report: {conform_result.get('output')}")
                elif conform_result.get('error'):
                    logger.warning(f"  Conformance check skipped: {conform_result.get('error')}")
            
            # Update computational execution status if full protocol
            if combined_usdm_path and run_validate:
                with open(combined_usdm_path, 'r') as f:
                    final_data = json.load(f)
                final_data["computationalExecution"]["validationStatus"] = "complete" if schema_result.get('valid') else "issues_found"
                with open(combined_usdm_path, 'w') as f:
                    json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        # Launch Streamlit viewer if requested
        if args.view:
            if combined_usdm_path and os.path.exists(combined_usdm_path):
                launch_viewer(combined_usdm_path)
            elif result and result.success and result.output_path:
                launch_viewer(result.output_path)
        
        # Determine overall success
        soa_success = result.success if result else True  # If no SoA, consider it OK
        expansion_success = all(r.success for r in expansion_results.values()) if expansion_results else True
        overall_success = soa_success and expansion_success
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("="*60)
        if run_soa:
            logger.info(f"SoA: {'✓ Success' if (result and result.success) else '✗ Failed'}")
        if run_any_expansion:
            exp_success = sum(1 for r in expansion_results.values() if r.success)
            logger.info(f"Expansion: {exp_success}/{len(expansion_results)} phases successful")
        if combined_usdm_path:
            logger.info(f"Golden Standard Output: {combined_usdm_path}")
        logger.info("="*60)
        
        sys.exit(0 if overall_success else 1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def launch_viewer(soa_path: str):
    """Launch the Streamlit SoA viewer."""
    import subprocess
    
    viewer_script = os.path.join(os.path.dirname(__file__), "soa_streamlit_viewer.py")
    
    if not os.path.exists(viewer_script):
        logger.warning(f"Viewer not found: {viewer_script}")
        return
    
    logger.info(f"Launching SoA viewer...")
    
    try:
        subprocess.Popen(
            ["streamlit", "run", viewer_script, "--", soa_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning(f"Could not launch viewer: {e}")
        logger.info(f"Run manually: streamlit run soa_viewer.py -- {soa_path}")


if __name__ == "__main__":
    main()
