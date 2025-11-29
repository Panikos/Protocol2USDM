#!/usr/bin/env python3
"""
Step-by-Step Pipeline Testing Script

Tests each module of the extraction pipeline independently,
allowing quality inspection at each stage.

Usage - SoA Pipeline (Steps 1-9):
    python test_pipeline_steps.py protocol.pdf --step 1        # Find SoA pages
    python test_pipeline_steps.py protocol.pdf --step 3        # Header analysis
    python test_pipeline_steps.py protocol.pdf --step all      # All SoA steps

Usage - USDM Expansion (Steps M/E/O/D/I/N/A/P/S/DS/AD):
    python test_pipeline_steps.py protocol.pdf --step M        # Metadata
    python test_pipeline_steps.py protocol.pdf --step E        # Eligibility
    python test_pipeline_steps.py protocol.pdf --step O        # Objectives
    python test_pipeline_steps.py protocol.pdf --step D        # Study Design
    python test_pipeline_steps.py protocol.pdf --step I        # Interventions
    python test_pipeline_steps.py protocol.pdf --step N        # Narrative/Abbreviations
    python test_pipeline_steps.py protocol.pdf --step A        # Advanced (amendments, sites)
    python test_pipeline_steps.py protocol.pdf --step P        # Procedures & Devices (Phase 10)
    python test_pipeline_steps.py protocol.pdf --step S        # Scheduling Logic (Phase 11)
    python test_pipeline_steps.py protocol.pdf --step DS       # Document Structure (Phase 12)
    python test_pipeline_steps.py protocol.pdf --step AD       # Amendment Details (Phase 13)
    python test_pipeline_steps.py protocol.pdf --step expand   # All expansion phases

Usage - Conditional Sources:
    python test_pipeline_steps.py protocol.pdf --step SAP --sap sap.pdf    # SAP Analysis Populations
    python test_pipeline_steps.py protocol.pdf --step SITES --sites sites.xlsx  # Study Sites
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import fitz  # PyMuPDF


def step1_find_soa_pages(pdf_path: str, output_dir: str) -> dict:
    """
    STEP 1: Find Schedule of Activities pages
    
    Tests: extraction/soa_finder.py
    Quality metrics:
    - Are the correct pages identified?
    - Are non-SoA pages excluded?
    """
    print("\n" + "=" * 60)
    print("STEP 1: Find SoA Pages")
    print("=" * 60)
    
    from extraction.soa_finder import find_soa_pages_heuristic
    
    # Run heuristic detection
    pages = find_soa_pages_heuristic(pdf_path, top_n=10)
    
    result = {
        "step": 1,
        "name": "SoA Page Detection",
        "pdf": pdf_path,
        "detected_pages": pages,
        "detected_pages_1indexed": [p + 1 for p in pages],
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"\nDetected SoA pages (0-indexed): {pages}")
    print(f"Detected SoA pages (1-indexed): {[p+1 for p in pages]}")
    
    # Show page text samples
    print("\n--- Page Samples ---")
    doc = fitz.open(pdf_path)
    for p in pages[:5]:  # Show first 5
        text = doc[p].get_text()[:300].replace('\n', ' ')
        print(f"\nPage {p+1}: {text}...")
    doc.close()
    
    # Save result
    output_path = Path(output_dir) / "step1_soa_pages.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Saved to: {output_path}")
    
    print("\n--- QUALITY CHECK ---")
    print("Review the detected pages. Are they the actual SoA tables?")
    print("If not, manually specify pages with: --pages 45,46,47")
    
    return result


def step2_extract_text_and_images(pdf_path: str, output_dir: str, pages: list = None) -> dict:
    """
    STEP 2: Extract text and images from SoA pages
    
    Tests: PDF text extraction quality
    Quality metrics:
    - Is the text readable?
    - Are tables preserved?
    - Are images clear enough for vision analysis?
    """
    print("\n" + "=" * 60)
    print("STEP 2: Extract Text and Images")
    print("=" * 60)
    
    doc = fitz.open(pdf_path)
    
    if pages is None:
        # Use step 1 result
        step1_path = Path(output_dir) / "step1_soa_pages.json"
        if step1_path.exists():
            with open(step1_path) as f:
                step1 = json.load(f)
                pages = step1["detected_pages"]
        else:
            print("ERROR: No pages specified and step 1 not run")
            return {}
    
    print(f"\nExtracting from pages: {[p+1 for p in pages]}")
    
    # Extract text
    texts = []
    for p in pages:
        if 0 <= p < len(doc):
            text = doc[p].get_text()
            texts.append({"page": p + 1, "text": text, "length": len(text)})
    
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join(t["text"] for t in texts)
    
    # Extract images
    images_dir = Path(output_dir) / "step2_images"
    images_dir.mkdir(exist_ok=True)
    
    image_paths = []
    for p in pages:
        if 0 <= p < len(doc):
            pix = doc[p].get_pixmap(dpi=150)
            img_path = images_dir / f"page_{p+1:03d}.png"
            pix.save(str(img_path))
            image_paths.append(str(img_path))
    
    doc.close()
    
    result = {
        "step": 2,
        "name": "Text and Image Extraction",
        "pages_extracted": [p + 1 for p in pages],
        "total_text_chars": len(combined_text),
        "per_page_stats": [{"page": t["page"], "chars": t["length"]} for t in texts],
        "images_extracted": len(image_paths),
        "image_paths": image_paths,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save text
    text_path = Path(output_dir) / "step2_extracted_text.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(combined_text)
    
    # Save result
    output_path = Path(output_dir) / "step2_extraction.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✓ Extracted {len(combined_text)} characters of text")
    print(f"✓ Created {len(image_paths)} page images")
    print(f"✓ Text saved to: {text_path}")
    print(f"✓ Images saved to: {images_dir}")
    
    print("\n--- QUALITY CHECK ---")
    print("1. Open step2_extracted_text.txt - is the table text readable?")
    print("2. Open the PNG images - are they clear enough?")
    print("3. Can you see all columns and rows in the SoA table?")
    
    return result


def step3_analyze_headers(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP 3: Vision-based header structure analysis
    
    Tests: extraction/header_analyzer.py
    Quality metrics:
    - Are all epochs identified?
    - Are all encounters/visits identified?
    - Are timepoint names correct?
    """
    print("\n" + "=" * 60)
    print("STEP 3: Header Structure Analysis (Vision)")
    print("=" * 60)
    
    from extraction.header_analyzer import analyze_soa_headers
    
    # Get images from step 2
    images_dir = Path(output_dir) / "step2_images"
    image_paths = sorted(images_dir.glob("*.png"))
    
    if not image_paths:
        print("ERROR: No images found. Run step 2 first.")
        return {}
    
    print(f"\nAnalyzing {len(image_paths)} images with {model}...")
    print("This may take a minute...")
    
    # Run header analysis
    header_result = analyze_soa_headers(
        image_paths=[str(p) for p in image_paths],
        model_name=model
    )
    
    # Access structure from result
    structure = header_result.structure
    
    # Convert to dicts for JSON serialization
    epochs = [e.to_dict() if hasattr(e, 'to_dict') else e for e in structure.epochs]
    encounters = [e.to_dict() if hasattr(e, 'to_dict') else e for e in structure.encounters]
    timepoints = [t.to_dict() if hasattr(t, 'to_dict') else t for t in structure.plannedTimepoints]
    activity_groups = [g.to_dict() if hasattr(g, 'to_dict') else g for g in structure.activityGroups]
    
    result = {
        "step": 3,
        "name": "Header Structure Analysis",
        "model": model,
        "epochs": epochs,
        "encounters": encounters,
        "timepoints": timepoints,
        "activity_groups": activity_groups,
        "raw_response": header_result.raw_response,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save result
    output_path = Path(output_dir) / "step3_header_structure.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n✓ Epochs found: {len(epochs)}")
    for e in epochs:
        print(f"    - {e.get('id')}: {e.get('name')}")
    
    print(f"\n✓ Encounters/Visits found: {len(encounters)}")
    for e in encounters[:10]:
        print(f"    - {e.get('id')}: {e.get('name')}")
    if len(encounters) > 10:
        print(f"    ... and {len(encounters) - 10} more")
    
    print(f"\n✓ Activity Groups found: {len(activity_groups)}")
    for g in activity_groups[:5]:
        print(f"    - {g.get('id')}: {g.get('name')}")
    
    print(f"\n✓ Saved to: {output_path}")
    
    print("\n--- QUALITY CHECK ---")
    print("1. Are all study phases (epochs) identified?")
    print("2. Are all visits/encounters listed with correct names?")
    print("3. Compare with the actual PDF - any missing columns?")
    
    return result


def step4_extract_text_data(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP 4: Text-based data extraction using header structure
    
    Tests: extraction/text_extractor.py
    Quality metrics:
    - Are all activities extracted?
    - Are tick marks (X) correctly identified?
    - Do activity IDs match header IDs?
    """
    print("\n" + "=" * 60)
    print("STEP 4: Text Data Extraction")
    print("=" * 60)
    
    from extraction.text_extractor import extract_soa_from_text
    from core.usdm_types import HeaderStructure
    
    # Load text from step 2
    text_path = Path(output_dir) / "step2_extracted_text.txt"
    if not text_path.exists():
        print("ERROR: Text file not found. Run step 2 first.")
        return {}
    
    with open(text_path, 'r', encoding='utf-8') as f:
        soa_text = f.read()
    
    # Load header structure from step 3
    header_path = Path(output_dir) / "step3_header_structure.json"
    if not header_path.exists():
        print("ERROR: Header structure not found. Run step 3 first.")
        return {}
    
    with open(header_path) as f:
        header_data = json.load(f)
    
    # Build header structure for extractor (convert to HeaderStructure object)
    header_dict = {
        "columnHierarchy": {
            "epochs": header_data.get("epochs", []),
            "encounters": header_data.get("encounters", []),
            "plannedTimepoints": header_data.get("timepoints", []),
        },
        "rowGroups": header_data.get("activity_groups", [])
    }
    header_structure = HeaderStructure.from_dict(header_dict)
    
    print(f"\nExtracting data with {model}...")
    print(f"Text length: {len(soa_text)} chars")
    print(f"Header has {len(header_structure.encounters)} encounters")
    print("This may take a minute...")
    
    # Run extraction
    extraction_result = extract_soa_from_text(
        protocol_text=soa_text,
        header_structure=header_structure,
        model_name=model
    )
    
    # Convert to dicts for JSON
    activities = [a.to_dict() if hasattr(a, 'to_dict') else a for a in extraction_result.activities]
    ticks = [t.to_dict() if hasattr(t, 'to_dict') else t for t in extraction_result.activity_timepoints]
    
    result = {
        "step": 4,
        "name": "Text Data Extraction",
        "model": model,
        "activities_count": len(activities),
        "activities": activities,
        "tick_matrix": ticks,
        "ticks_count": len(ticks),
        "raw_response": extraction_result.raw_response,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save result
    output_path = Path(output_dir) / "step4_text_extraction.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n✓ Activities extracted: {len(activities)}")
    for a in activities[:10]:
        print(f"    - {a.get('id')}: {a.get('name')}")
    if len(activities) > 10:
        print(f"    ... and {len(activities) - 10} more")
    
    print(f"\n✓ Tick marks found: {len(ticks)}")
    
    # Show sample ticks
    print("\nSample ticks:")
    for tick in ticks[:5]:
        print(f"    Activity {tick.get('activityId')} @ Timepoint {tick.get('plannedTimepointId')}")
    
    print(f"\n✓ Saved to: {output_path}")
    
    print("\n--- QUALITY CHECK ---")
    print("1. Are all activities from the SoA listed?")
    print("2. Count the tick marks - does it seem reasonable?")
    print("3. Open the PDF and verify a few ticks manually")
    
    return result


def step5_validate_with_vision(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP 5: Vision-based validation of text extraction
    
    Tests: extraction/validator.py
    Quality metrics:
    - How many ticks confirmed by vision?
    - How many potential hallucinations flagged?
    - How many missed ticks found?
    """
    print("\n" + "=" * 60)
    print("STEP 5: Vision Validation")
    print("=" * 60)
    
    from extraction.validator import validate_extraction
    
    # Load text extraction from step 4
    step4_path = Path(output_dir) / "step4_text_extraction.json"
    if not step4_path.exists():
        print("ERROR: Text extraction not found. Run step 4 first.")
        return {}
    
    with open(step4_path) as f:
        step4_data = json.load(f)
    
    # Get images from step 2
    images_dir = Path(output_dir) / "step2_images"
    image_paths = sorted(images_dir.glob("*.png"))
    
    # Load header structure
    header_path = Path(output_dir) / "step3_header_structure.json"
    with open(header_path) as f:
        header_data = json.load(f)
    
    print(f"\nValidating {len(step4_data['tick_matrix'])} ticks against {len(image_paths)} images...")
    print(f"Using model: {model}")
    print("This may take a minute...")
    
    # Build HeaderStructure from header data
    from core.usdm_types import HeaderStructure, PlannedTimepoint, Encounter, Epoch
    
    header_structure = HeaderStructure(
        epochs=[Epoch.from_dict(e) for e in header_data.get("epochs", [])],
        encounters=[Encounter.from_dict(e) for e in header_data.get("encounters", [])],
        plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in header_data.get("timepoints", [])]
    )
    
    # Run validation
    validation_result = validate_extraction(
        text_activities=step4_data["activities"],
        text_ticks=step4_data["tick_matrix"],
        header_structure=header_structure,
        image_paths=[str(p) for p in image_paths],
        model_name=model
    )
    
    result = {
        "step": 5,
        "name": "Vision Validation",
        "model": model,
        "confirmed_ticks": validation_result.confirmed_ticks,
        "hallucinations_flagged": validation_result.hallucination_count,
        "missed_ticks_found": validation_result.missed_count,
        "issues": [i.to_dict() for i in validation_result.issues] if validation_result.issues else [],
        "timestamp": datetime.now().isoformat()
    }
    
    # Save result
    output_path = Path(output_dir) / "step5_validation.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n✓ Confirmed ticks: {validation_result.confirmed_ticks}")
    print(f"⚠ Hallucinations flagged: {validation_result.hallucination_count}")
    print(f"+ Missed ticks found: {validation_result.missed_count}")
    
    if validation_result.issues:
        print("\nIssues found:")
        for issue in validation_result.issues[:5]:
            print(f"    - [{issue.issue_type.value}] {issue.activity_name} @ {issue.timepoint_name}")
    
    print(f"\n✓ Saved to: {output_path}")
    
    print("\n--- QUALITY CHECK ---")
    print("1. Is the hallucination rate acceptable (<5%)?")
    print("2. Review flagged items - are they really incorrect?")
    print("3. Were missed ticks actually in the PDF?")
    
    return result


def step6_build_final_output(pdf_path: str, output_dir: str) -> dict:
    """
    STEP 6: Build final USDM JSON output
    
    Tests: Final assembly and normalization
    Quality metrics:
    - Is the JSON schema-compliant?
    - Are all entities properly linked?
    - Is provenance tracked?
    """
    print("\n" + "=" * 60)
    print("STEP 6: Build Final USDM Output")
    print("=" * 60)
    
    from core import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION
    from processing import ensure_required_fields, normalize_names_vs_timing
    from core.provenance import ProvenanceTracker, ProvenanceSource
    
    # Load previous steps
    step3_path = Path(output_dir) / "step3_header_structure.json"
    step4_path = Path(output_dir) / "step4_text_extraction.json"
    
    with open(step3_path) as f:
        header_data = json.load(f)
    with open(step4_path) as f:
        text_data = json.load(f)
    
    # Build USDM structure
    timeline = {
        "activities": text_data["activities"],
        "plannedTimepoints": header_data.get("timepoints", []),
        "encounters": header_data.get("encounters", []),
        "epochs": header_data.get("epochs", []),
        "activityGroups": header_data.get("activity_groups", []),
        "activityTimepoints": text_data["tick_matrix"]
    }
    
    usdm_output = {
        "usdmVersion": USDM_VERSION,
        "systemName": SYSTEM_NAME,
        "systemVersion": SYSTEM_VERSION,
        "study": {
            "versions": [{
                "timeline": timeline
            }]
        }
    }
    
    # Apply normalizations
    ensure_required_fields(usdm_output)
    normalize_names_vs_timing(timeline)
    
    # Build provenance - start with text extraction
    provenance = ProvenanceTracker()
    for act in text_data["activities"]:
        provenance.tag_entity("activities", act.get("id", ""), ProvenanceSource.TEXT)
    for tick in text_data["tick_matrix"]:
        # Use plannedTimepointId (correct field) with fallback to timepointId
        tp_id = tick.get("plannedTimepointId") or tick.get("timepointId", "")
        provenance.tag_cell(tick.get("activityId", ""), tp_id, ProvenanceSource.TEXT)
    
    # Also tag header-derived entities
    for pt in header_data.get("timepoints", []):
        provenance.tag_entity("plannedTimepoints", pt.get("id", ""), ProvenanceSource.HEADER)
    for enc in header_data.get("encounters", []):
        provenance.tag_entity("encounters", enc.get("id", ""), ProvenanceSource.HEADER)
    for epoch in header_data.get("epochs", []):
        provenance.tag_entity("epochs", epoch.get("id", ""), ProvenanceSource.HEADER)
    for grp in header_data.get("activity_groups", []):
        provenance.tag_entity("activityGroups", grp.get("id", ""), ProvenanceSource.HEADER)
    
    # Load vision validation results if available and merge into provenance
    step5_path = Path(output_dir) / "step5_validation.json"
    if step5_path.exists():
        with open(step5_path) as f:
            validation_data = json.load(f)
        
        # Build set of flagged cells (hallucinations or missed ticks that need review)
        flagged_cells = set()
        for issue in validation_data.get("issues", []):
            act_id = issue.get("activity_id", "")
            tp_id = issue.get("timepoint_id", "")
            if act_id and tp_id:
                flagged_cells.add(f"{act_id}|{tp_id}")
        
        confirmed_count = validation_data.get("confirmed_ticks", 0)
        hallucination_count = validation_data.get("hallucinations_flagged", 0)
        missed_count = validation_data.get("missed_ticks_found", 0)
        
        print(f"    Vision validation: {confirmed_count} confirmed, {hallucination_count} flagged, {missed_count} missed")
        
        # Mark ticks based on validation status
        for tick in text_data["tick_matrix"]:
            act_id = tick.get("activityId", "")
            tp_id = tick.get("plannedTimepointId") or tick.get("timepointId", "")
            if not tp_id:
                continue
            
            cell_key = f"{act_id}|{tp_id}"
            if cell_key in flagged_cells:
                # Flagged as possible hallucination - needs human review
                provenance.cells[cell_key] = ProvenanceSource.NEEDS_REVIEW.value
            else:
                # Confirmed by vision - mark as both
                provenance.tag_cell(act_id, tp_id, ProvenanceSource.VISION)
        
        # Also mark missed ticks (found by vision but not text) as needing review
        for issue in validation_data.get("issues", []):
            if issue.get("issue_type") == "missed_tick":
                act_id = issue.get("activity_id", "")
                tp_id = issue.get("timepoint_id", "")
                if act_id and tp_id:
                    provenance.cells[f"{act_id}|{tp_id}"] = ProvenanceSource.NEEDS_REVIEW.value
    
    # Save outputs
    final_path = Path(output_dir) / "step6_final_soa.json"
    with open(final_path, 'w') as f:
        json.dump(usdm_output, f, indent=2)
    
    provenance_path = Path(output_dir) / "step6_provenance.json"
    provenance.save(str(provenance_path))
    
    result = {
        "step": 6,
        "name": "Final USDM Output",
        "usdm_version": USDM_VERSION,
        "activities_count": len(timeline["activities"]),
        "timepoints_count": len(timeline["plannedTimepoints"]),
        "encounters_count": len(timeline["encounters"]),
        "ticks_count": len(timeline["activityTimepoints"]),
        "output_path": str(final_path),
        "provenance_path": str(provenance_path),
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"\n✓ USDM Version: {USDM_VERSION}")
    print(f"✓ Activities: {len(timeline['activities'])}")
    print(f"✓ Timepoints: {len(timeline['plannedTimepoints'])}")
    print(f"✓ Encounters: {len(timeline['encounters'])}")
    print(f"✓ Ticks: {len(timeline['activityTimepoints'])}")
    print(f"\n✓ Final output: {final_path}")
    print(f"✓ Provenance: {provenance_path}")
    
    print("\n--- QUALITY CHECK ---")
    print("1. Open in Streamlit viewer: streamlit run soa_streamlit_viewer.py -- " + str(final_path))
    print("2. Compare visually with the PDF")
    print("3. Check that all activities and visits are present")
    
    return result


def step7_enrich_terminology(pdf_path: str, output_dir: str) -> dict:
    """
    STEP 7: Enrich activities with terminology codes
    
    Uses a curated mapping of common clinical terms to NCI codes.
    """
    print("\n" + "=" * 60)
    print("STEP 7: Terminology Enrichment")
    print("=" * 60)
    
    # Common clinical procedure NCI codes
    KNOWN_CODES = {
        "informed consent": ("C16735", "Informed Consent"),
        "physical exam": ("C20989", "Physical Examination"),
        "vital signs": ("C25714", "Vital Signs"),
        "ecg": ("C38054", "Electrocardiogram"),
        "blood pressure": ("C54706", "Blood Pressure Measurement"),
        "weight": ("C25208", "Weight"),
        "height": ("C25347", "Height"),
        "randomization": ("C15417", "Randomization"),
        "laboratory": ("C49286", "Laboratory Test"),
        "urinalysis": ("C79430", "Urinalysis"),
        "hba1c": ("C64849", "Hemoglobin A1c Measurement"),
        "adverse event": ("C41331", "Adverse Event"),
        "concomitant medication": ("C53630", "Concomitant Medication"),
        "medical history": ("C18772", "Medical History"),
    }
    
    # Load final SoA
    step6_path = Path(output_dir) / "step6_final_soa.json"
    if not step6_path.exists():
        print("ERROR: step6_final_soa.json not found. Run step 6 first.")
        return {"error": "Missing step 6 output"}
    
    with open(step6_path) as f:
        soa_data = json.load(f)
    
    timeline = soa_data.get("study", {}).get("versions", [{}])[0].get("timeline", {})
    activities = timeline.get("activities", [])
    
    enriched_count = 0
    print(f"\nEnriching {len(activities)} activities...")
    
    for activity in activities:
        name = activity.get("name", activity.get("label", ""))
        if not name:
            continue
        
        # Match against known codes
        name_lower = name.lower()
        for term, (code, decode) in KNOWN_CODES.items():
            if term in name_lower:
                activity["definedProcedures"] = [{
                    "id": f"proc_{activity.get('id', '')}",
                    "code": {"code": code, "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl", "decode": decode},
                    "instanceType": "Procedure"
                }]
                enriched_count += 1
                print(f"    ✓ {name} -> {code}")
                break
    
    # Save enriched version
    enriched_path = Path(output_dir) / "step7_enriched_soa.json"
    with open(enriched_path, 'w') as f:
        json.dump(soa_data, f, indent=2)
    
    print(f"\n✓ Enriched: {enriched_count}/{len(activities)} activities")
    print(f"✓ Saved to: {enriched_path}")
    
    return {"step": 7, "enriched": enriched_count, "total": len(activities), "output_path": str(enriched_path)}


def step8_validate_schema(pdf_path: str, output_dir: str) -> dict:
    """
    STEP 8: Validate JSON structure against USDM schema
    
    Checks that all required fields are present and properly linked.
    """
    print("\n" + "=" * 60)
    print("STEP 8: Schema Validation")
    print("=" * 60)
    
    # Load final SoA (or enriched if available)
    step7_path = Path(output_dir) / "step7_enriched_soa.json"
    step6_path = Path(output_dir) / "step6_final_soa.json"
    
    if step7_path.exists():
        soa_path = step7_path
    elif step6_path.exists():
        soa_path = step6_path
    else:
        print("ERROR: No SoA file found. Run step 6 first.")
        return {"error": "Missing SoA output"}
    
    with open(soa_path) as f:
        soa_data = json.load(f)
    
    issues = []
    warnings = []
    
    # Check wrapper-level fields
    print("\nChecking USDM Wrapper structure...")
    required_wrapper = ["usdmVersion", "study"]
    for field in required_wrapper:
        if field not in soa_data:
            issues.append(f"Missing required field: {field}")
    
    # Check study structure
    study = soa_data.get("study", {})
    versions = study.get("versions", [])
    
    if not versions:
        issues.append("Missing study.versions array")
    else:
        timeline = versions[0].get("timeline", {})
        
        # Check timeline arrays
        required_timeline = ["activities", "plannedTimepoints", "activityTimepoints"]
        for field in required_timeline:
            if field not in timeline:
                issues.append(f"Missing timeline.{field}")
            elif not timeline[field]:
                warnings.append(f"Empty timeline.{field}")
        
        # Check entity linkage
        print("Checking entity linkage...")
        activities = {a.get("id"): a for a in timeline.get("activities", [])}
        timepoints = {t.get("id"): t for t in timeline.get("plannedTimepoints", [])}
        encounters = {e.get("id"): e for e in timeline.get("encounters", [])}
        
        # Check activityTimepoints reference valid IDs
        for at in timeline.get("activityTimepoints", []):
            act_id = at.get("activityId")
            tp_id = at.get("plannedTimepointId")
            
            if act_id and act_id not in activities:
                issues.append(f"activityTimepoint references invalid activityId: {act_id}")
            if tp_id and tp_id not in timepoints:
                issues.append(f"activityTimepoint references invalid plannedTimepointId: {tp_id}")
        
        # Check timepoints reference valid encounters
        for tp in timeline.get("plannedTimepoints", []):
            enc_id = tp.get("encounterId")
            if enc_id and enc_id not in encounters:
                warnings.append(f"plannedTimepoint {tp.get('id')} references missing encounterId: {enc_id}")
    
    # Save validation report
    report = {
        "step": 8,
        "name": "Schema Validation",
        "source_file": str(soa_path),
        "issues": issues,
        "warnings": warnings,
        "valid": len(issues) == 0,
        "timestamp": datetime.now().isoformat()
    }
    
    report_path = Path(output_dir) / "step8_schema_validation.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print results
    if issues:
        print(f"\n❌ VALIDATION FAILED - {len(issues)} issues found:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n✓ Schema validation PASSED")
    
    if warnings:
        print(f"\n⚠ {len(warnings)} warnings:")
        for warn in warnings[:5]:
            print(f"    - {warn}")
        if len(warnings) > 5:
            print(f"    ... and {len(warnings) - 5} more")
    
    print(f"\n✓ Report saved to: {report_path}")
    
    return report


def step9_cdisc_conformance(pdf_path: str, output_dir: str) -> dict:
    """
    STEP 9: Run CDISC CORE conformance rules
    
    Validates against official USDM 4.0 conformance rules.
    Requires CDISC CORE engine to be installed in tools/core/
    """
    print("\n" + "=" * 60)
    print("STEP 9: CDISC CORE Conformance")
    print("=" * 60)
    
    import subprocess
    
    # Check for CORE engine
    core_exe = Path("tools/core/core/core.exe")
    if not core_exe.exists():
        print("⚠ CDISC CORE engine not found at tools/core/core/core.exe")
        print("  Download from: https://github.com/cdisc-org/cdisc-rules-engine/releases")
        return {"error": "CORE engine not installed", "step": 9}
    
    # Find SoA file
    step7_path = Path(output_dir) / "step7_enriched_soa.json"
    step6_path = Path(output_dir) / "step6_final_soa.json"
    
    if step7_path.exists():
        soa_path = step7_path
    elif step6_path.exists():
        soa_path = step6_path
    else:
        print("ERROR: No SoA file found. Run step 6 first.")
        return {"error": "Missing SoA output"}
    
    print(f"Validating: {soa_path}")
    print("Running USDM 4.0 conformance rules...")
    
    output_path = Path(output_dir) / "step9_conformance"
    
    # Run CORE validation
    try:
        result = subprocess.run(
            [
                str(core_exe),
                "validate",
                "-s", "usdm",
                "-v", "4-0",
                "-dp", str(soa_path.absolute()),
                "-o", str(output_path.absolute()),
                "-of", "JSON"
            ],
            capture_output=True,
            text=True,
            cwd=str(core_exe.parent),
            timeout=300
        )
        
        if result.returncode == 0:
            print("\n✓ CDISC CORE validation completed")
            
            # Load and summarize results
            result_file = Path(str(output_path) + ".json")
            if result_file.exists():
                with open(result_file) as f:
                    conformance = json.load(f)
                
                # Count issues by severity
                issues = conformance.get("issues", [])
                by_severity = {}
                for issue in issues:
                    sev = issue.get("severity", "unknown")
                    by_severity[sev] = by_severity.get(sev, 0) + 1
                
                print(f"\nConformance Results:")
                for sev, count in sorted(by_severity.items()):
                    print(f"    {sev}: {count}")
                
                return {
                    "step": 9,
                    "name": "CDISC CORE Conformance",
                    "success": True,
                    "issues_by_severity": by_severity,
                    "output_path": str(result_file),
                    "timestamp": datetime.now().isoformat()
                }
        else:
            print(f"\n⚠ CORE validation returned errors:")
            print(result.stderr[:500] if result.stderr else result.stdout[:500])
            
            return {
                "step": 9,
                "name": "CDISC CORE Conformance",
                "success": False,
                "error": result.stderr or result.stdout,
                "timestamp": datetime.now().isoformat()
            }
            
    except subprocess.TimeoutExpired:
        print("⚠ CORE validation timed out (5 min limit)")
        return {"step": 9, "error": "Timeout"}
    except Exception as e:
        print(f"⚠ CORE validation failed: {e}")
        return {"step": 9, "error": str(e)}


# ============================================================================
# USDM EXPANSION STEPS (v6.0)
# ============================================================================

def step_metadata(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP M: Extract Study Metadata
    
    Tests: extraction/metadata/extractor.py
    Extracts: StudyTitle, StudyIdentifier, Organization, StudyRole, Indication
    """
    print("\n" + "=" * 60)
    print("STEP M: Study Metadata Extraction (Phase 2)")
    print("=" * 60)
    
    from extraction.metadata import extract_study_metadata
    from extraction.metadata.extractor import save_metadata_result
    from extraction.confidence import calculate_metadata_confidence
    
    print(f"Extracting metadata with {model}...")
    result = extract_study_metadata(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "2_study_metadata.json"
    save_metadata_result(result, str(output_path))
    
    if result.success and result.metadata:
        md = result.metadata
        print(f"\n✓ Titles: {len(md.titles)}")
        print(f"✓ Identifiers: {len(md.identifiers)}")
        print(f"✓ Organizations: {len(md.organizations)}")
        if md.study_phase:
            print(f"✓ Phase: {md.study_phase.phase}")
        if md.indications:
            print(f"✓ Indication: {md.indications[0].name}")
        
        # Calculate confidence
        confidence = calculate_metadata_confidence(md)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "M", "success": result.success}


def step_eligibility(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP E: Extract Eligibility Criteria
    
    Tests: extraction/eligibility/extractor.py
    Extracts: EligibilityCriterion, EligibilityCriterionItem, StudyDesignPopulation
    """
    print("\n" + "=" * 60)
    print("STEP E: Eligibility Criteria Extraction (Phase 1)")
    print("=" * 60)
    
    from extraction.eligibility import extract_eligibility_criteria
    from extraction.eligibility.extractor import save_eligibility_result
    from extraction.confidence import calculate_eligibility_confidence
    
    print(f"Extracting eligibility criteria with {model}...")
    result = extract_eligibility_criteria(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "3_eligibility_criteria.json"
    save_eligibility_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Inclusion Criteria: {data.inclusion_count}")
        print(f"✓ Exclusion Criteria: {data.exclusion_count}")
        if data.population:
            print(f"✓ Population defined: Yes")
        
        # Calculate confidence
        confidence = calculate_eligibility_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "E", "success": result.success}


def step_objectives(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP O: Extract Objectives & Endpoints
    
    Tests: extraction/objectives/extractor.py
    Extracts: Objective, Endpoint, Estimand, IntercurrentEvent
    """
    print("\n" + "=" * 60)
    print("STEP O: Objectives & Endpoints Extraction (Phase 3)")
    print("=" * 60)
    
    from extraction.objectives import extract_objectives_endpoints
    from extraction.objectives.extractor import save_objectives_result
    
    print(f"Extracting objectives with {model}...")
    result = extract_objectives_endpoints(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "4_objectives_endpoints.json"
    save_objectives_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Primary Objectives: {data.primary_objectives_count}")
        print(f"✓ Secondary Objectives: {data.secondary_objectives_count}")
        print(f"✓ Exploratory Objectives: {data.exploratory_objectives_count}")
        print(f"✓ Total Endpoints: {len(data.endpoints)}")
        
        # Calculate confidence
        from extraction.confidence import calculate_objectives_confidence
        confidence = calculate_objectives_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "O", "success": result.success}


def step_studydesign(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP D: Extract Study Design Structure
    
    Tests: extraction/studydesign/extractor.py
    Extracts: InterventionalStudyDesign, StudyArm, StudyCell, StudyCohort
    """
    print("\n" + "=" * 60)
    print("STEP D: Study Design Extraction (Phase 4)")
    print("=" * 60)
    
    from extraction.studydesign import extract_study_design
    from extraction.studydesign.extractor import save_study_design_result
    from extraction.confidence import calculate_studydesign_confidence
    
    print(f"Extracting study design with {model}...")
    result = extract_study_design(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "5_study_design.json"
    save_study_design_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Study Arms: {len(data.arms)}")
        print(f"✓ Study Cohorts: {len(data.cohorts)}")
        if data.study_design:
            sd = data.study_design
            if sd.blinding_schema:
                print(f"✓ Blinding: {sd.blinding_schema.value}")
            if sd.randomization_type:
                print(f"✓ Randomization: {sd.randomization_type.value}")
        
        # Calculate confidence
        confidence = calculate_studydesign_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "D", "success": result.success}


def step_interventions(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP I: Extract Interventions & Products
    
    Tests: extraction/interventions/extractor.py
    Extracts: StudyIntervention, AdministrableProduct, Administration, Substance
    """
    print("\n" + "=" * 60)
    print("STEP I: Interventions & Products Extraction (Phase 5)")
    print("=" * 60)
    
    from extraction.interventions import extract_interventions
    from extraction.interventions.extractor import save_interventions_result
    from extraction.confidence import calculate_interventions_confidence
    
    print(f"Extracting interventions with {model}...")
    result = extract_interventions(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "6_interventions.json"
    save_interventions_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Interventions: {len(data.interventions)}")
        print(f"✓ Products: {len(data.products)}")
        print(f"✓ Administrations: {len(data.administrations)}")
        print(f"✓ Substances: {len(data.substances)}")
        
        # Calculate confidence
        confidence = calculate_interventions_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "I", "success": result.success}


def step_narrative(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP N: Extract Document Structure & Abbreviations
    
    Tests: extraction/narrative/extractor.py
    Extracts: NarrativeContent, Abbreviation, StudyDefinitionDocument
    """
    print("\n" + "=" * 60)
    print("STEP N: Document Structure Extraction (Phase 7)")
    print("=" * 60)
    
    from extraction.narrative import extract_narrative_structure
    from extraction.narrative.extractor import save_narrative_result
    from extraction.confidence import calculate_narrative_confidence
    
    print(f"Extracting narrative structure with {model}...")
    result = extract_narrative_structure(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "7_narrative_structure.json"
    save_narrative_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Sections: {len(data.sections)}")
        print(f"✓ Abbreviations: {len(data.abbreviations)}")
        if data.document:
            print(f"✓ Document: {data.document.name[:50]}...")
        
        # Calculate confidence
        confidence = calculate_narrative_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "N", "success": result.success}


def step_advanced(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP A: Extract Advanced Entities
    
    Tests: extraction/advanced/extractor.py
    Extracts: StudyAmendment, GeographicScope, Country, StudySite
    """
    print("\n" + "=" * 60)
    print("STEP A: Advanced Entities Extraction (Phase 8)")
    print("=" * 60)
    
    from extraction.advanced import extract_advanced_entities
    from extraction.advanced.extractor import save_advanced_result
    from extraction.confidence import calculate_advanced_confidence
    
    print(f"Extracting advanced entities with {model}...")
    result = extract_advanced_entities(pdf_path, model_name=model)
    
    output_path = Path(output_dir) / "8_advanced_entities.json"
    save_advanced_result(result, str(output_path))
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Amendments: {len(data.amendments)}")
        print(f"✓ Countries: {len(data.countries)}")
        print(f"✓ Sites: {len(data.sites)}")
        
        # Calculate confidence
        confidence = calculate_advanced_confidence(data)
        print(f"📊 Confidence: {confidence.overall:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "A", "success": result.success}


def step_procedures(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP P: Extract Procedures & Medical Devices
    
    Tests: extraction/procedures/extractor.py
    Extracts: Procedure, MedicalDevice, MedicalDeviceIdentifier, Ingredient, Strength
    """
    print("\n" + "=" * 60)
    print("STEP P: Procedures & Devices Extraction (Phase 10)")
    print("=" * 60)
    
    from extraction.procedures import extract_procedures_devices
    
    print(f"Extracting procedures with {model}...")
    result = extract_procedures_devices(pdf_path, model=model, output_dir=output_dir)
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Procedures: {len(data.procedures)}")
        print(f"✓ Medical Devices: {len(data.devices)}")
        print(f"✓ Ingredients: {len(data.ingredients)}")
        
        # Show sample procedures
        for proc in data.procedures[:5]:
            print(f"    - {proc.name}")
        
        print(f"📊 Confidence: {result.confidence:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "9_procedures_devices.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "P", "success": result.success}


def step_scheduling(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP S: Extract Scheduling Logic
    
    Tests: extraction/scheduling/extractor.py
    Extracts: Timing, Condition, TransitionRule, ScheduleTimelineExit, ScheduledDecisionInstance
    """
    print("\n" + "=" * 60)
    print("STEP S: Scheduling Logic Extraction (Phase 11)")
    print("=" * 60)
    
    from extraction.scheduling import extract_scheduling
    
    print(f"Extracting scheduling logic with {model}...")
    result = extract_scheduling(pdf_path, model=model, output_dir=output_dir)
    
    if result.success and result.data:
        data = result.data
        summary = data.to_dict()['summary']
        print(f"\n✓ Timings: {summary['timingCount']}")
        print(f"✓ Conditions: {summary['conditionCount']}")
        print(f"✓ Transition Rules: {summary['transitionRuleCount']}")
        
        # Show sample timings
        for timing in data.timings[:5]:
            print(f"    - {timing.name}: {timing.value} {timing.unit}")
        
        print(f"📊 Confidence: {result.confidence:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "10_scheduling_logic.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "S", "success": result.success}


def step_docstructure(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP DS: Extract Document Structure
    
    Tests: extraction/document_structure/extractor.py
    Extracts: DocumentContentReference, CommentAnnotation, StudyDefinitionDocumentVersion
    """
    print("\n" + "=" * 60)
    print("STEP DS: Document Structure Extraction (Phase 12)")
    print("=" * 60)
    
    from extraction.document_structure import extract_document_structure
    
    print(f"Extracting document structure with {model}...")
    result = extract_document_structure(pdf_path, model=model, output_dir=output_dir)
    
    if result.success and result.data:
        data = result.data
        summary = data.to_dict()['summary']
        print(f"\n✓ Content References: {summary['referenceCount']}")
        print(f"✓ Annotations: {summary['annotationCount']}")
        print(f"✓ Document Versions: {summary['versionCount']}")
        
        # Show document versions
        for ver in data.document_versions:
            amend = f" ({ver.amendment_number})" if ver.amendment_number else ""
            print(f"    - Version {ver.version_number}{amend} - {ver.status}")
        
        print(f"📊 Confidence: {result.confidence:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "13_document_structure.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "DS", "success": result.success}


def step_amendmentdetails(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP AD: Extract Amendment Details
    
    Tests: extraction/amendments/extractor.py
    Extracts: StudyAmendmentImpact, StudyAmendmentReason, StudyChange
    """
    print("\n" + "=" * 60)
    print("STEP AD: Amendment Details Extraction (Phase 13)")
    print("=" * 60)
    
    from extraction.amendments import extract_amendment_details
    
    print(f"Extracting amendment details with {model}...")
    result = extract_amendment_details(pdf_path, model=model, output_dir=output_dir)
    
    if result.success and result.data:
        data = result.data
        summary = data.to_dict()['summary']
        print(f"\n✓ Amendment Impacts: {summary['impactCount']}")
        print(f"✓ Amendment Reasons: {summary['reasonCount']}")
        print(f"✓ Study Changes: {summary['changeCount']}")
        
        # Show amendment reasons
        for reason in data.reasons[:3]:
            primary = " ⭐" if reason.is_primary else ""
            print(f"    - [{reason.category.value}]{primary} {reason.reason_text[:60]}...")
        
        print(f"📊 Confidence: {result.confidence:.0%}")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "14_amendment_details.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "AD", "success": result.success}


def step_sap(pdf_path: str, output_dir: str, sap_path: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP SAP: Extract Analysis Populations from SAP
    
    Tests: extraction/conditional/sap_extractor.py
    Extracts: AnalysisPopulation, Characteristic
    """
    print("\n" + "=" * 60)
    print("STEP SAP: SAP Analysis Populations (Phase 14)")
    print("=" * 60)
    
    if not sap_path:
        print("❌ No SAP file provided. Use --sap <path>")
        return {"step": "SAP", "success": False, "error": "No SAP file"}
    
    from extraction.conditional import extract_from_sap
    
    print(f"Extracting from SAP: {sap_path}")
    print(f"Using model: {model}...")
    result = extract_from_sap(sap_path, model=model, output_dir=output_dir)
    
    if result.success and result.data:
        data = result.data
        print(f"\n✓ Analysis Populations: {len(data.analysis_populations)}")
        print(f"✓ Baseline Characteristics: {len(data.characteristics)}")
        
        # Show populations
        for pop in data.analysis_populations:
            print(f"    - {pop.label or pop.name} ({pop.population_type})")
        
        print("📊 Extraction successful!")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "11_sap_populations.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "SAP", "success": result.success}


def step_sites(pdf_path: str, output_dir: str, sites_path: str, model: str = "gemini-2.5-pro") -> dict:
    """
    STEP SITES: Extract Study Sites from site list
    
    Tests: extraction/conditional/sites_extractor.py
    Extracts: StudySite, StudyRole, AssignedPerson
    """
    print("\n" + "=" * 60)
    print("STEP SITES: Study Sites Extraction (Phase 15)")
    print("=" * 60)
    
    if not sites_path:
        print("❌ No sites file provided. Use --sites <path>")
        return {"step": "SITES", "success": False, "error": "No sites file"}
    
    from extraction.conditional import extract_from_sites
    
    print(f"Extracting from sites file: {sites_path}")
    result = extract_from_sites(sites_path, output_dir=output_dir)
    
    if result.success and result.sites_data:
        data = result.sites_data
        print(f"\n✓ Study Sites: {len(data.get('studySites', []))}")
        print(f"✓ Study Roles: {len(data.get('studyRoles', []))}")
        print(f"✓ Assigned Persons: {len(data.get('assignedPersons', []))}")
        
        # Show sample sites
        for site in data.get('studySites', [])[:5]:
            print(f"    - {site.get('siteNumber', 'N/A')}: {site.get('name', 'N/A')} ({site.get('country', 'N/A')})")
    else:
        print(f"❌ Failed: {result.error}")
    
    output_path = Path(output_dir) / "12_study_sites.json"
    print(f"\n✓ Saved to: {output_path}")
    return {"step": "SITES", "success": result.success}


def step_all_expansion(pdf_path: str, output_dir: str, model: str = "gemini-2.5-pro", 
                       sap_path: str = None, sites_path: str = None) -> dict:
    """
    Run all USDM expansion steps (Phases 1-5, 7-8, 10-13, and conditional).
    """
    print("\n" + "=" * 60)
    print("RUNNING ALL USDM EXPANSION STEPS")
    print("=" * 60)
    
    results = {}
    
    # Core protocol phases
    results["metadata"] = step_metadata(pdf_path, output_dir, model)
    results["eligibility"] = step_eligibility(pdf_path, output_dir, model)
    results["objectives"] = step_objectives(pdf_path, output_dir, model)
    results["studydesign"] = step_studydesign(pdf_path, output_dir, model)
    results["interventions"] = step_interventions(pdf_path, output_dir, model)
    results["narrative"] = step_narrative(pdf_path, output_dir, model)
    results["advanced"] = step_advanced(pdf_path, output_dir, model)
    
    # New phases (10-13)
    results["procedures"] = step_procedures(pdf_path, output_dir, model)
    results["scheduling"] = step_scheduling(pdf_path, output_dir, model)
    results["docstructure"] = step_docstructure(pdf_path, output_dir, model)
    results["amendmentdetails"] = step_amendmentdetails(pdf_path, output_dir, model)
    
    # Conditional phases (if sources provided)
    if sap_path:
        results["sap"] = step_sap(pdf_path, output_dir, sap_path, model)
    if sites_path:
        results["sites"] = step_sites(pdf_path, output_dir, sites_path, model)
    
    success_count = sum(1 for r in results.values() if r.get("success"))
    total_count = len(results)
    print(f"\n{'='*60}")
    print(f"EXPANSION COMPLETE: {success_count}/{total_count} steps successful")
    print(f"{'='*60}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Step-by-step pipeline testing",
        epilog="""
Step Options:
  SoA Pipeline: 1-9 (or 'all' for all SoA steps)
  USDM Expansion: 
    M (metadata), E (eligibility), O (objectives), D (design), I (interventions), 
    N (narrative), A (advanced), P (procedures), S (scheduling), 
    DS (doc structure), AD (amendment details)
  Conditional: SAP, SITES
  Run all expansion: 'expand'
  
Examples:
  python test_pipeline_steps.py protocol.pdf --step 3          # Header analysis
  python test_pipeline_steps.py protocol.pdf --step E          # Eligibility
  python test_pipeline_steps.py protocol.pdf --step P          # Procedures & Devices
  python test_pipeline_steps.py protocol.pdf --step DS         # Document Structure
  python test_pipeline_steps.py protocol.pdf --step SAP --sap sap.pdf  # SAP populations
  python test_pipeline_steps.py protocol.pdf --step expand     # All expansion phases
  python test_pipeline_steps.py protocol.pdf --step expand --sap sap.pdf  # All + SAP
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pdf", help="Path to protocol PDF")
    parser.add_argument("--step", default="all", 
                        help="Step: 1-9 (SoA), M/E/O/D/I/N/A/P/S/DS/AD (expansion), SAP/SITES (conditional), 'all', or 'expand'")
    parser.add_argument("--pages", help="Comma-separated page numbers (1-indexed)")
    parser.add_argument("--model", default="gemini-2.5-pro", help="Model to use")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--sap", help="Path to SAP PDF for analysis population extraction")
    parser.add_argument("--sites", help="Path to site list (CSV/Excel) for site extraction")
    
    args = parser.parse_args()
    
    # Setup output directory
    if args.output:
        output_dir = args.output
    else:
        pdf_name = Path(args.pdf).stem
        output_dir = f"output/{pdf_name}_test"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Parse pages if provided
    pages = None
    if args.pages:
        pages = [int(p) - 1 for p in args.pages.split(",")]  # Convert to 0-indexed
    
    print(f"\n{'='*60}")
    print(f"PIPELINE STEP-BY-STEP TESTING")
    print(f"{'='*60}")
    print(f"PDF: {args.pdf}")
    print(f"Output: {output_dir}")
    print(f"Model: {args.model}")
    if pages:
        print(f"Pages: {[p+1 for p in pages]} (1-indexed)")
    
    # Run requested steps
    step_arg = args.step.upper()
    
    if step_arg == "ALL":
        steps = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    elif step_arg == "EXPAND":
        step_all_expansion(args.pdf, output_dir, args.model, args.sap, args.sites)
        return
    else:
        steps = [step_arg]
    
    for step in steps:
        if step == "1":
            step1_find_soa_pages(args.pdf, output_dir)
        elif step == "2":
            step2_extract_text_and_images(args.pdf, output_dir, pages)
        elif step == "3":
            step3_analyze_headers(args.pdf, output_dir, args.model)
        elif step == "4":
            step4_extract_text_data(args.pdf, output_dir, args.model)
        elif step == "5":
            step5_validate_with_vision(args.pdf, output_dir, args.model)
        elif step == "6":
            step6_build_final_output(args.pdf, output_dir)
        elif step == "7":
            step7_enrich_terminology(args.pdf, output_dir)
        elif step == "8":
            step8_validate_schema(args.pdf, output_dir)
        elif step == "9":
            step9_cdisc_conformance(args.pdf, output_dir)
        # USDM Expansion steps (Phase 1-8)
        elif step == "M":
            step_metadata(args.pdf, output_dir, args.model)
        elif step == "E":
            step_eligibility(args.pdf, output_dir, args.model)
        elif step == "O":
            step_objectives(args.pdf, output_dir, args.model)
        elif step == "D":
            step_studydesign(args.pdf, output_dir, args.model)
        elif step == "I":
            step_interventions(args.pdf, output_dir, args.model)
        elif step == "N":
            step_narrative(args.pdf, output_dir, args.model)
        elif step == "A":
            step_advanced(args.pdf, output_dir, args.model)
        # New expansion steps (Phase 10-13)
        elif step == "P":
            step_procedures(args.pdf, output_dir, args.model)
        elif step == "S":
            step_scheduling(args.pdf, output_dir, args.model)
        elif step == "DS":
            step_docstructure(args.pdf, output_dir, args.model)
        elif step == "AD":
            step_amendmentdetails(args.pdf, output_dir, args.model)
        # Conditional sources
        elif step == "SAP":
            step_sap(args.pdf, output_dir, args.sap, args.model)
        elif step == "SITES":
            step_sites(args.pdf, output_dir, args.sites, args.model)
        else:
            print(f"Unknown step: {step}")
            print("Valid steps: 1-9 (SoA), M/E/O/D/I/N/A/P/S/DS/AD (expansion), SAP/SITES (conditional), 'all', 'expand'")
            continue
        
        if args.step.upper() not in ["ALL", "EXPAND"]:
            print("\n" + "="*60)
            print("Step complete. Review output before proceeding to next step.")
            print("="*60)


if __name__ == "__main__":
    main()
