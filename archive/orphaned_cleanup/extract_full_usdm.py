#!/usr/bin/env python3
"""
Full USDM Extraction Pipeline

Runs all extraction modules and combines results into a single USDM v4.0 JSON.

This integrates:
- SoA extraction (Schedule of Activities)
- Phase 1: Eligibility Criteria
- Phase 2: Study Metadata
- Phase 3: Objectives & Endpoints
- Phase 4: Study Design Structure
- Phase 5: Interventions & Products
- Phase 7: Narrative Structure
- Phase 8: Advanced Entities

Usage:
    python extract_full_usdm.py protocol.pdf
    python extract_full_usdm.py protocol.pdf --skip-soa    # Skip SoA, use existing
    python extract_full_usdm.py protocol.pdf --model gemini-2.5-pro
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Import extraction modules
from extraction.metadata import extract_study_metadata
from extraction.eligibility import extract_eligibility_criteria
from extraction.objectives import extract_objectives_endpoints
from extraction.studydesign import extract_study_design
from extraction.interventions import extract_interventions
from extraction.narrative import extract_narrative_structure
from extraction.advanced import extract_advanced_entities


def run_soa_pipeline(pdf_path: str, output_dir: str, model: str) -> Optional[Dict]:
    """Run the SoA extraction pipeline."""
    from extraction import run_from_files, PipelineConfig
    
    config = PipelineConfig(
        model_name=model,
        validate_with_vision=True,
        remove_hallucinations=True,
        save_intermediate=True,
    )
    
    result = run_from_files(
        pdf_path=pdf_path,
        output_dir=output_dir,
        config=config,
    )
    
    if result.success and result.output_path:
        with open(result.output_path, 'r') as f:
            return json.load(f)
    return None


def combine_usdm_outputs(
    soa_data: Optional[Dict],
    metadata_result,
    eligibility_result,
    objectives_result,
    studydesign_result,
    interventions_result,
    narrative_result,
    advanced_result,
) -> Dict[str, Any]:
    """Combine all extraction results into a single USDM structure."""
    
    # Start with base structure
    combined = {
        "usdmVersion": "4.0",
        "generatedAt": datetime.now().isoformat(),
        "generator": "Protocol2USDM v6.0",
        "study": {},
        "studyDesigns": [],
    }
    
    # Add Study Metadata (Phase 2)
    if metadata_result and metadata_result.success and metadata_result.metadata:
        md = metadata_result.metadata
        combined["study"] = {
            "studyTitles": [t.to_dict() for t in md.titles],
            "studyIdentifiers": [i.to_dict() for i in md.identifiers],
            "organizations": [o.to_dict() for o in md.organizations],
        }
        if md.study_phase:
            combined["study"]["studyPhase"] = md.study_phase.to_dict()
        if md.indications:
            combined["study"]["indications"] = [i.to_dict() for i in md.indications]
    
    # Create StudyDesign container
    study_design = {
        "id": "sd_1",
        "instanceType": "InterventionalStudyDesign",
    }
    
    # Add Study Design Structure (Phase 4)
    if studydesign_result and studydesign_result.success and studydesign_result.data:
        sd = studydesign_result.data
        if sd.study_design:
            design = sd.study_design
            if design.blinding_schema:
                study_design["blindingSchema"] = {"code": design.blinding_schema.value}
            if design.randomization_type:
                study_design["randomizationType"] = {"code": design.randomization_type.value}
            if design.trial_type:
                study_design["trialType"] = [{"code": design.trial_type.value}]
        study_design["studyArms"] = [a.to_dict() for a in sd.arms]
        study_design["studyCohorts"] = [c.to_dict() for c in sd.cohorts]
        study_design["studyCells"] = [c.to_dict() for c in sd.cells]
    
    # Add Eligibility Criteria (Phase 1)
    if eligibility_result and eligibility_result.success and eligibility_result.data:
        ed = eligibility_result.data
        study_design["eligibilityCriteria"] = [c.to_dict() for c in ed.criteria]
        if ed.population:
            study_design["studyDesignPopulation"] = ed.population.to_dict()
    
    # Add Objectives & Endpoints (Phase 3)
    if objectives_result and objectives_result.success and objectives_result.data:
        od = objectives_result.data
        study_design["objectives"] = [o.to_dict() for o in od.objectives]
        study_design["endpoints"] = [e.to_dict() for e in od.endpoints]
        if od.estimands:
            study_design["estimands"] = [e.to_dict() for e in od.estimands]
    
    # Add Interventions (Phase 5)
    if interventions_result and interventions_result.success and interventions_result.data:
        iv = interventions_result.data
        study_design["studyInterventions"] = [i.to_dict() for i in iv.interventions]
        combined["administrableProducts"] = [p.to_dict() for p in iv.products]
        combined["administrations"] = [a.to_dict() for a in iv.administrations]
        combined["substances"] = [s.to_dict() for s in iv.substances]
    
    # Add SoA data (existing pipeline)
    if soa_data:
        # Extract scheduleTimelines from SoA
        if "studyDesigns" in soa_data and soa_data["studyDesigns"]:
            soa_design = soa_data["studyDesigns"][0]
            if "scheduleTimelines" in soa_design:
                study_design["scheduleTimelines"] = soa_design["scheduleTimelines"]
            if "encounters" in soa_design:
                study_design["encounters"] = soa_design["encounters"]
            if "activities" in soa_design:
                study_design["activities"] = soa_design["activities"]
    
    combined["studyDesigns"] = [study_design]
    
    # Add Narrative Content (Phase 7)
    if narrative_result and narrative_result.success and narrative_result.data:
        nd = narrative_result.data
        combined["narrativeContents"] = [s.to_dict() for s in nd.sections]
        combined["abbreviations"] = [a.to_dict() for a in nd.abbreviations]
        if nd.document:
            combined["studyDefinitionDocument"] = nd.document.to_dict()
    
    # Add Advanced Entities (Phase 8)
    if advanced_result and advanced_result.success and advanced_result.data:
        ad = advanced_result.data
        if ad.amendments:
            combined["studyAmendments"] = [a.to_dict() for a in ad.amendments]
        if ad.geographic_scope:
            combined["geographicScope"] = ad.geographic_scope.to_dict()
        if ad.countries:
            combined["countries"] = [c.to_dict() for c in ad.countries]
    
    return combined


def main():
    parser = argparse.ArgumentParser(
        description="Extract full USDM content from clinical protocol PDF"
    )
    parser.add_argument("pdf_path", help="Path to the clinical protocol PDF")
    parser.add_argument("--model", "-m", default="gemini-2.5-pro", help="LLM model")
    parser.add_argument("--output-dir", "-o", help="Output directory")
    parser.add_argument("--skip-soa", action="store_true", help="Skip SoA extraction (use existing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir) if args.output_dir else Path("output") / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("Protocol2USDM - Full USDM Extraction Pipeline")
    logger.info("=" * 70)
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 70)
    
    results = {}
    
    # Phase 2: Study Metadata
    logger.info("\n[1/8] Extracting Study Metadata...")
    results['metadata'] = extract_study_metadata(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Metadata: {results['metadata'].success}")
    
    # Phase 1: Eligibility Criteria
    logger.info("\n[2/8] Extracting Eligibility Criteria...")
    results['eligibility'] = extract_eligibility_criteria(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Eligibility: {results['eligibility'].success}")
    
    # Phase 3: Objectives & Endpoints
    logger.info("\n[3/8] Extracting Objectives & Endpoints...")
    results['objectives'] = extract_objectives_endpoints(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Objectives: {results['objectives'].success}")
    
    # Phase 4: Study Design
    logger.info("\n[4/8] Extracting Study Design...")
    results['studydesign'] = extract_study_design(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Study Design: {results['studydesign'].success}")
    
    # Phase 5: Interventions
    logger.info("\n[5/8] Extracting Interventions...")
    results['interventions'] = extract_interventions(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Interventions: {results['interventions'].success}")
    
    # Phase 7: Narrative
    logger.info("\n[6/8] Extracting Narrative Structure...")
    results['narrative'] = extract_narrative_structure(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Narrative: {results['narrative'].success}")
    
    # Phase 8: Advanced
    logger.info("\n[7/8] Extracting Advanced Entities...")
    results['advanced'] = extract_advanced_entities(str(pdf_path), model_name=args.model)
    logger.info(f"  ✓ Advanced: {results['advanced'].success}")
    
    # SoA Pipeline
    soa_data = None
    if args.skip_soa:
        existing_soa = output_dir / "9_final_soa.json"
        if existing_soa.exists():
            logger.info("\n[8/8] Loading existing SoA...")
            with open(existing_soa, 'r') as f:
                soa_data = json.load(f)
            logger.info(f"  ✓ SoA loaded from {existing_soa}")
        else:
            logger.warning("\n[8/8] No existing SoA found, skipping...")
    else:
        logger.info("\n[8/8] Extracting Schedule of Activities...")
        soa_data = run_soa_pipeline(str(pdf_path), str(output_dir), args.model)
        logger.info(f"  ✓ SoA: {soa_data is not None}")
    
    # Combine all outputs
    logger.info("\n" + "=" * 70)
    logger.info("Combining outputs into unified USDM JSON...")
    
    combined = combine_usdm_outputs(
        soa_data=soa_data,
        metadata_result=results['metadata'],
        eligibility_result=results['eligibility'],
        objectives_result=results['objectives'],
        studydesign_result=results['studydesign'],
        interventions_result=results['interventions'],
        narrative_result=results['narrative'],
        advanced_result=results['advanced'],
    )
    
    # Save combined output
    output_path = output_dir / "full_usdm.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    # Summary
    logger.info("=" * 70)
    logger.info("✅ EXTRACTION COMPLETE")
    logger.info("=" * 70)
    
    success_count = sum(1 for r in results.values() if r.success)
    logger.info(f"Phases successful: {success_count}/7")
    logger.info(f"SoA included: {soa_data is not None}")
    logger.info("")
    
    # Content summary
    if combined.get("study"):
        logger.info(f"Study Titles: {len(combined['study'].get('studyTitles', []))}")
        logger.info(f"Study Identifiers: {len(combined['study'].get('studyIdentifiers', []))}")
    
    if combined.get("studyDesigns"):
        sd = combined["studyDesigns"][0]
        logger.info(f"Study Arms: {len(sd.get('studyArms', []))}")
        logger.info(f"Eligibility Criteria: {len(sd.get('eligibilityCriteria', []))}")
        logger.info(f"Objectives: {len(sd.get('objectives', []))}")
        logger.info(f"Endpoints: {len(sd.get('endpoints', []))}")
        logger.info(f"Interventions: {len(sd.get('studyInterventions', []))}")
        logger.info(f"Activities: {len(sd.get('activities', []))}")
    
    logger.info(f"Abbreviations: {len(combined.get('abbreviations', []))}")
    logger.info(f"Amendments: {len(combined.get('studyAmendments', []))}")
    
    logger.info("")
    logger.info(f"Output: {output_path}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
