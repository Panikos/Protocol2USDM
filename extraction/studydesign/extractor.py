"""
Study Design Structure Extractor - Phase 4 of USDM Expansion

Extracts study design structure from protocol.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    StudyDesignData,
    InterventionalStudyDesign,
    StudyArm,
    StudyCell,
    StudyCohort,
    StudyElement,
    DoseEpoch,
    ArmType,
    BlindingSchema,
    RandomizationType,
    ControlType,
    AllocationRatio,
)
from .prompts import build_study_design_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class StudyDesignExtractionResult:
    """Result of study design extraction."""
    success: bool
    data: Optional[StudyDesignData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_study_design_pages(
    pdf_path: str,
    max_pages_to_scan: int = 30,
) -> List[int]:
    """
    Find pages containing study design information using heuristics.
    
    Args:
        pdf_path: Path to the protocol PDF
        max_pages_to_scan: Maximum pages to scan from start
        
    Returns:
        List of 0-indexed page numbers likely containing study design
    """
    import fitz
    
    design_keywords = [
        r'study\s+design',
        r'trial\s+design',
        r'randomization',
        r'randomisation',
        r'blinding',
        r'double.?blind',
        r'open.?label',
        r'treatment\s+arms?',
        r'study\s+arms?',
        r'allocation\s+ratio',
        r'stratification',
        r'interventional',
        r'parallel\s+group',
        r'crossover',
    ]
    
    pattern = re.compile('|'.join(design_keywords), re.IGNORECASE)
    
    design_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            if pattern.search(text):
                design_pages.append(page_num)
                logger.debug(f"Found design keywords on page {page_num + 1}")
        
        doc.close()
        
        # If we found pages, also include adjacent pages for context
        if design_pages:
            expanded = set()
            for p in design_pages:
                expanded.add(p)
                if p > 0:
                    expanded.add(p - 1)
                if p < total_pages - 1:
                    expanded.add(p + 1)
            design_pages = sorted(expanded)
        
        logger.info(f"Found {len(design_pages)} potential study design pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        
    return design_pages


def extract_study_design(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
    existing_arms: Optional[List[Dict[str, Any]]] = None,
) -> StudyDesignExtractionResult:
    """
    Extract study design structure from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model_name: LLM model to use
        pages: Specific pages to use (0-indexed), auto-detected if None
        protocol_text: Optional pre-extracted text
        existing_epochs: Epochs from SoA extraction for reference
        existing_arms: Arms from prior extraction for reference
        
    Returns:
        StudyDesignExtractionResult with extracted data
    """
    result = StudyDesignExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect study design pages if not specified
        if pages is None:
            pages = find_study_design_pages(pdf_path)
            if not pages:
                # Fallback to first 15 pages (synopsis usually has design info)
                logger.warning("No design pages detected, scanning first 15 pages")
                pages = list(range(min(15, get_page_count(pdf_path))))
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Call LLM for extraction
        logger.info("Extracting study design with LLM...")
        
        # Build context hints from existing SoA data
        context_hints = ""
        if existing_epochs:
            epoch_names = [e.get('name', '') for e in existing_epochs if e.get('name')]
            if epoch_names:
                context_hints += f"\nKnown study epochs from SoA: {', '.join(epoch_names)}"
        if existing_arms:
            arm_names = [a.get('name', '') for a in existing_arms if a.get('name')]
            if arm_names:
                context_hints += f"\nKnown treatment arms from SoA: {', '.join(arm_names)}"
        
        prompt = build_study_design_extraction_prompt(protocol_text, context_hints=context_hints)
        
        response = call_llm(
            prompt=prompt,
            model_name=model_name,
            json_mode=True,
            extractor_name="studydesign",
        )
        
        if 'error' in response:
            result.error = response['error']
            return result
        
        # Parse response
        raw_response = _parse_json_response(response.get('response', ''))
        if not raw_response:
            result.error = "Failed to parse LLM response as JSON"
            return result
        
        result.raw_response = raw_response
        
        # Convert to structured data
        result.data = _parse_design_response(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted study design with {len(result.data.arms)} arms, "
                f"{len(result.data.cohorts)} cohorts"
            )
        
    except Exception as e:
        logger.error(f"Study design extraction failed: {e}")
        result.error = str(e)
        
    return result


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _parse_design_response(raw: Dict[str, Any]) -> Optional[StudyDesignData]:
    """Parse raw LLM response into StudyDesignData object.
    
    Handles both legacy format and new USDM-compliant format with ids.
    """
    try:
        # Handle case where LLM returns a list instead of a dict
        if isinstance(raw, list):
            if len(raw) == 1 and isinstance(raw[0], dict):
                raw = raw[0]
            else:
                # Assume list contains arms directly
                raw = {'studyArms': raw}
        
        arms = []
        cohorts = []
        cells = []
        epochs = []
        
        # Process arms - accept both 'arms' and 'studyArms' keys
        arm_list = raw.get('arms', []) or raw.get('studyArms', [])
        for i, arm_data in enumerate(arm_list):
            if not isinstance(arm_data, dict):
                continue
            
            # Handle type as string or code object - use empty string if not extracted
            arm_type_data = arm_data.get('type')
            if isinstance(arm_type_data, dict):
                arm_type_str = arm_type_data.get('code') or arm_type_data.get('decode') or ''
            elif arm_type_data:
                arm_type_str = str(arm_type_data)
            else:
                arm_type_str = ''
            arm_type = _map_arm_type(arm_type_str) if arm_type_str else None
            
            # Parse titration info
            is_titration = arm_data.get('isTitration', False)
            dose_epochs = []
            if is_titration and arm_data.get('doseEpochs'):
                for de_data in arm_data.get('doseEpochs', []):
                    if isinstance(de_data, dict):
                        dose_epochs.append(DoseEpoch(
                            dose=de_data.get('dose', ''),
                            start_day=de_data.get('startDay'),
                            end_day=de_data.get('endDay'),
                            description=de_data.get('description'),
                        ))
            
            arms.append(StudyArm(
                id=arm_data.get('id', f"arm_{i+1}"),
                name=arm_data.get('name', f'Arm {i+1}'),
                description=arm_data.get('description'),
                arm_type=arm_type,
                is_titration=is_titration,
                dose_epochs=dose_epochs,
            ))
        
        # Process cohorts - accept both 'cohorts' and 'studyCohorts' keys
        cohort_list = raw.get('cohorts', []) or raw.get('studyCohorts', [])
        for i, cohort_data in enumerate(cohort_list):
            if not isinstance(cohort_data, dict):
                continue
                
            cohorts.append(StudyCohort(
                id=cohort_data.get('id', f"cohort_{i+1}"),
                name=cohort_data.get('name', f'Cohort {i+1}'),
                description=cohort_data.get('description'),
                characteristic=cohort_data.get('characteristic'),
            ))
        
        # Process epochs - accept both 'epochs' and 'studyEpochs' keys
        epoch_list = raw.get('epochs', []) or raw.get('studyEpochs', [])
        for i, epoch_data in enumerate(epoch_list):
            if isinstance(epoch_data, dict):
                epochs.append({
                    'id': epoch_data.get('id', f"epoch_{i+1}"),
                    'name': epoch_data.get('name', f'Epoch {i+1}'),
                    'description': epoch_data.get('description'),
                })
        
        # Process study design
        study_design = None
        design_data = raw.get('studyDesign', {})
        if isinstance(design_data, dict):
            # Blinding - use None if not extracted (don't inject 'Open Label')
            blinding = None
            blinding_data = design_data.get('blinding', {})
            if isinstance(blinding_data, dict):
                blinding_schema = blinding_data.get('schema')
                if blinding_schema:
                    blinding = _map_blinding(blinding_schema)
                masked_roles = blinding_data.get('maskedRoles', [])
            else:
                masked_roles = []
            
            # Randomization - use None if not extracted (don't inject 'Non-Randomized')
            randomization = None
            allocation = None
            stratification = []
            rand_data = design_data.get('randomization', {})
            if isinstance(rand_data, dict):
                rand_type = rand_data.get('type')
                if rand_type:
                    randomization = _map_randomization(rand_type)
                ratio = rand_data.get('allocationRatio')
                if ratio:
                    allocation = AllocationRatio(ratio=str(ratio))
                stratification = rand_data.get('stratificationFactors', [])
            
            # Control type
            control = None
            control_str = design_data.get('controlType')
            if control_str:
                control = _map_control_type(control_str)
            
            # Trial intent types
            intent_types = design_data.get('trialIntentTypes', [])
            if not isinstance(intent_types, list):
                intent_types = [intent_types] if intent_types else []
            
            study_design = InterventionalStudyDesign(
                id="sd_1",
                name="Study Design",
                description=design_data.get('description'),
                trial_intent_types=intent_types,
                trial_type=design_data.get('type') or '',  # Empty if not extracted
                blinding_schema=blinding,
                masked_roles=masked_roles if isinstance(masked_roles, list) else [],
                randomization_type=randomization,
                allocation_ratio=allocation,
                stratification_factors=stratification if isinstance(stratification, list) else [],
                control_type=control,
                arm_ids=[a.id for a in arms],
                cohort_ids=[c.id for c in cohorts],
                therapeutic_areas=design_data.get('therapeuticAreas', []),
            )
        
        # Generate cells and elements from arms × epochs if epochs provided
        cell_counter = 1
        elements = []
        for arm in arms:
            for epoch in epochs:
                epoch_id = epoch.get('id', f"epoch_{cell_counter}")
                epoch_name = epoch.get('name', f'Epoch {cell_counter}')
                
                # Create a StudyElement for this cell (treatment period)
                element_id = f"elem_{cell_counter}"
                element = StudyElement(
                    id=element_id,
                    name=f"{arm.name} - {epoch_name}",
                    description=f"Treatment period for {arm.name} during {epoch_name}",
                )
                elements.append(element)
                
                # Create cell with reference to the element
                cells.append(StudyCell(
                    id=f"cell_{cell_counter}",
                    arm_id=arm.id,
                    epoch_id=epoch_id,
                    element_ids=[element_id],
                ))
                cell_counter += 1
        
        return StudyDesignData(
            study_design=study_design,
            arms=arms,
            cells=cells,
            cohorts=cohorts,
            elements=elements,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse design response: {e}")
        return None


def _map_arm_type(type_str: str) -> ArmType:
    """Map string to ArmType enum. Returns UNKNOWN if input is empty."""
    if not type_str:
        return ArmType.UNKNOWN
    type_lower = type_str.lower()
    if 'placebo' in type_lower:
        return ArmType.PLACEBO_COMPARATOR
    elif 'active' in type_lower and 'comparator' in type_lower:
        return ArmType.ACTIVE_COMPARATOR
    elif 'sham' in type_lower:
        return ArmType.SHAM_COMPARATOR
    elif 'no intervention' in type_lower or 'no treatment' in type_lower:
        return ArmType.NO_INTERVENTION
    elif 'experimental' in type_lower:
        return ArmType.EXPERIMENTAL
    return ArmType.OTHER  # Use OTHER for unrecognized, not EXPERIMENTAL


def _map_blinding(schema_str: str) -> BlindingSchema:
    """Map string to BlindingSchema enum. Returns UNKNOWN if input is empty."""
    if not schema_str:
        return BlindingSchema.UNKNOWN
    schema_lower = schema_str.lower()
    if 'quadruple' in schema_lower:
        return BlindingSchema.QUADRUPLE_BLIND
    elif 'triple' in schema_lower:
        return BlindingSchema.TRIPLE_BLIND
    elif 'double' in schema_lower:
        return BlindingSchema.DOUBLE_BLIND
    elif 'single' in schema_lower:
        return BlindingSchema.SINGLE_BLIND
    elif 'open' in schema_lower:
        return BlindingSchema.OPEN_LABEL
    return BlindingSchema.UNKNOWN  # Return UNKNOWN for unrecognized, not OPEN_LABEL


def _map_randomization(type_str: str) -> RandomizationType:
    """Map string to RandomizationType enum. Returns UNKNOWN if input is empty."""
    if not type_str:
        return RandomizationType.UNKNOWN
    type_lower = type_str.lower()
    if 'non' in type_lower or 'not' in type_lower:
        return RandomizationType.NON_RANDOMIZED
    elif 'random' in type_lower:
        return RandomizationType.RANDOMIZED
    return RandomizationType.UNKNOWN  # Return UNKNOWN for unrecognized


def _map_control_type(type_str: str) -> ControlType:
    """Map string to ControlType enum."""
    type_lower = type_str.lower()
    if 'placebo' in type_lower:
        return ControlType.PLACEBO
    elif 'active' in type_lower:
        return ControlType.ACTIVE
    elif 'dose' in type_lower:
        return ControlType.DOSE_COMPARISON
    elif 'historical' in type_lower:
        return ControlType.HISTORICAL
    elif 'no treatment' in type_lower:
        return ControlType.NO_TREATMENT
    return ControlType.ACTIVE


def save_study_design_result(
    result: StudyDesignExtractionResult,
    output_path: str,
) -> None:
    """Save study design extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["studyDesignStructure"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved study design to {output_path}")
