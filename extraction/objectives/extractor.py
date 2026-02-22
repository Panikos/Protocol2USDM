"""
Objectives & Endpoints Extractor - Phase 3 of USDM Expansion

Extracts study objectives and endpoints from protocol.
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
    ObjectivesData,
    Objective,
    Endpoint,
    Estimand,
    IntercurrentEvent,
    ObjectiveLevel,
    EndpointLevel,
    IntercurrentEventStrategy,
    AnalysisApproach,
)
from .prompts import build_objectives_extraction_prompt, build_estimands_prompt

logger = logging.getLogger(__name__)


@dataclass
class ObjectivesExtractionResult:
    """Result of objectives/endpoints extraction."""
    success: bool
    data: Optional[ObjectivesData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_objectives_pages(
    pdf_path: str,
    max_pages_to_scan: int = 30,
) -> List[int]:
    """
    Find pages containing objectives and endpoints using heuristics.
    
    Args:
        pdf_path: Path to the protocol PDF
        max_pages_to_scan: Maximum pages to scan from start
        
    Returns:
        List of 0-indexed page numbers likely containing objectives
    """
    import fitz
    
    objectives_keywords = [
        r'primary\s+objective',
        r'secondary\s+objective',
        r'exploratory\s+objective',
        r'study\s+objectives?',
        r'primary\s+endpoint',
        r'secondary\s+endpoint',
        r'study\s+endpoints?',
        r'efficacy\s+endpoints?',
        r'safety\s+endpoints?',
        r'estimand',
    ]
    
    pattern = re.compile('|'.join(objectives_keywords), re.IGNORECASE)
    
    objectives_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            if pattern.search(text):
                objectives_pages.append(page_num)
                logger.debug(f"Found objectives keywords on page {page_num + 1}")
        
        doc.close()
        
        # If we found pages, also include adjacent pages for context
        if objectives_pages:
            expanded = set()
            for p in objectives_pages:
                expanded.add(p)
                if p > 0:
                    expanded.add(p - 1)
                if p < total_pages - 1:
                    expanded.add(p + 1)
            objectives_pages = sorted(expanded)
        
        logger.info(f"Found {len(objectives_pages)} potential objectives pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        
    return objectives_pages


def extract_objectives_endpoints(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    study_indication: Optional[str] = None,
    study_phase: Optional[str] = None,
    extract_estimands: bool = True,
) -> ObjectivesExtractionResult:
    """
    Extract objectives and endpoints from a protocol PDF using two-phase approach.
    
    Phase 1: Extract objectives and endpoints (core - always runs)
    Phase 2: Extract estimands with endpoint context (optional enhancement)
    
    Args:
        pdf_path: Path to the protocol PDF
        model_name: LLM model to use
        pages: Specific pages to use (0-indexed), auto-detected if None
        protocol_text: Optional pre-extracted text
        study_indication: Indication from metadata for context
        study_phase: Study phase from metadata for context
        extract_estimands: Whether to run Phase 2 estimands extraction (default True)
        
    Returns:
        ObjectivesExtractionResult with extracted data
    """
    result = ObjectivesExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect objectives pages if not specified
        if pages is None:
            pages = find_objectives_pages(pdf_path)
            if not pages:
                # Fallback to first 15 pages (synopsis usually has objectives)
                logger.warning("No objectives pages detected, scanning first 15 pages")
                pages = list(range(min(15, get_page_count(pdf_path))))
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Build context hints from prior extractions
        context_hints = ""
        if study_indication:
            context_hints += f"\nStudy indication: {study_indication}"
        if study_phase:
            context_hints += f"\nStudy phase: {study_phase}"
        
        # =====================================================================
        # PHASE 1: Extract objectives and endpoints (core)
        # =====================================================================
        logger.info("Phase 1: Extracting objectives and endpoints...")
        
        phase1_response = _extract_with_retry(
            prompt=build_objectives_extraction_prompt(protocol_text, context_hints=context_hints),
            model_name=model_name,
            phase_name="objectives",
            max_retries=3,
        )
        
        if phase1_response is None:
            result.error = "Phase 1 failed: Could not parse objectives/endpoints JSON"
            return result
        
        # Parse Phase 1 results
        objectives_data = _parse_objectives_only(phase1_response)
        if objectives_data is None:
            result.error = "Phase 1 failed: Could not parse objectives structure"
            return result
        
        logger.info(
            f"Phase 1 complete: {objectives_data.primary_objectives_count} primary, "
            f"{objectives_data.secondary_objectives_count} secondary, "
            f"{objectives_data.exploratory_objectives_count} exploratory objectives, "
            f"{len(objectives_data.endpoints)} endpoints"
        )
        
        # =====================================================================
        # PHASE 2: Classify analysis approach & extract estimands (if any)
        # =====================================================================
        if extract_estimands and objectives_data.endpoints:
            logger.info("Phase 2: Classifying analysis approach & extracting estimands...")
            
            # Build endpoint context for Phase 2
            endpoints_for_context = [ep.to_dict() for ep in objectives_data.endpoints]
            
            phase2_response = _extract_with_retry(
                prompt=build_estimands_prompt(protocol_text, endpoints_for_context, context_hints),
                model_name=model_name,
                phase_name="estimands",
                max_retries=2,
            )
            
            if phase2_response:
                # Parse analysis approach classification
                approach_str = phase2_response.get('analysisApproach', '').lower().strip()
                if approach_str == 'confirmatory':
                    objectives_data.analysis_approach = AnalysisApproach.CONFIRMATORY
                elif approach_str == 'descriptive':
                    objectives_data.analysis_approach = AnalysisApproach.DESCRIPTIVE
                else:
                    objectives_data.analysis_approach = AnalysisApproach.UNKNOWN
                
                objectives_data.analysis_approach_rationale = (
                    phase2_response.get('analysisApproachRationale', '')
                )
                
                logger.info(
                    f"Analysis approach: {objectives_data.analysis_approach.value} "
                    f"({objectives_data.analysis_approach_rationale[:100]})"
                )
                
                # Only populate estimands if explicitly found
                if phase2_response.get('estimands'):
                    estimands = _parse_estimands(phase2_response)
                    if estimands:
                        objectives_data.estimands = estimands
                        logger.info(f"Phase 2 complete: {len(estimands)} estimands extracted")
                    else:
                        logger.info("Phase 2: No valid estimands parsed from response")
                else:
                    logger.info(
                        f"Phase 2: No estimands defined in protocol "
                        f"(approach={objectives_data.analysis_approach.value})"
                    )
            else:
                logger.warning("Phase 2: Failed to get response (non-fatal)")
        
        # Store combined raw response
        result.raw_response = {
            "objectives": [o.to_dict() for o in objectives_data.objectives],
            "endpoints": [e.to_dict() for e in objectives_data.endpoints],
            "estimands": [est.to_dict() for est in objectives_data.estimands],
        }
        
        result.data = objectives_data
        result.success = True
        
        logger.info(
            f"Extraction complete: {result.data.primary_objectives_count} primary, "
            f"{result.data.secondary_objectives_count} secondary, "
            f"{result.data.exploratory_objectives_count} exploratory objectives"
        )
        
    except Exception as e:
        logger.error(f"Objectives extraction failed: {e}")
        result.error = str(e)
        
    return result


def _extract_with_retry(
    prompt: str,
    model_name: str,
    phase_name: str,
    max_retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    Call LLM with retry logic for truncated responses.
    
    Args:
        prompt: The extraction prompt
        model_name: LLM model to use
        phase_name: Name for logging (e.g., "objectives", "estimands")
        max_retries: Maximum continuation retries
        
    Returns:
        Parsed JSON response or None if failed
    """
    accumulated_response = ""
    
    for attempt in range(max_retries + 1):
        if attempt == 0:
            current_prompt = prompt
        else:
            logger.info(f"{phase_name} retry {attempt}/{max_retries}: Requesting continuation...")
            context_window = min(3000, len(accumulated_response))
            current_prompt = (
                f"Your previous response was truncated. Here is the end of what you generated:\n\n"
                f"```json\n{accumulated_response[-context_window:]}\n```\n\n"
                f"Please complete the JSON response. Continue EXACTLY from where you left off. "
                f"Do NOT repeat any content already generated. Output ONLY the remaining JSON."
            )
        
        response = call_llm(
            prompt=current_prompt,
            model_name=model_name,
            json_mode=True,
            extractor_name=phase_name,
        )
        
        if 'error' in response:
            logger.error(f"{phase_name} LLM error: {response['error']}")
            return None
        
        response_text = response.get('response', '')
        
        if attempt > 0 and response_text:
            accumulated_response = accumulated_response.rstrip() + response_text.lstrip()
            parsed = _parse_json_response(accumulated_response)
            if parsed:
                logger.info(f"{phase_name}: Parsed after {attempt} continuation(s)")
                return parsed
        else:
            accumulated_response = response_text
            parsed = _parse_json_response(response_text)
            if parsed:
                return parsed
                
            # Check if truncated
            if response_text and not response_text.rstrip().endswith('}'):
                continue  # Likely truncated, retry
            break  # Not truncated, just failed
    
    return None


def _parse_objectives_only(raw: Dict[str, Any]) -> Optional[ObjectivesData]:
    """Parse Phase 1 response (objectives + endpoints only, no estimands)."""
    try:
        objectives = []
        endpoints = []
        
        primary_count = 0
        secondary_count = 0
        exploratory_count = 0
        
        # Ensure raw is a dict
        if not isinstance(raw, dict):
            logger.error(f"Expected dict but got {type(raw).__name__}")
            return None
        
        # Parse objectives with level codes
        for obj_data in raw.get('objectives', []):
            # Skip non-dict items
            if not isinstance(obj_data, dict):
                logger.warning(f"Skipping non-dict objective item: {type(obj_data).__name__}")
                continue
            level_data = obj_data.get('level', {})
            level_code = level_data.get('code') if isinstance(level_data, dict) else (str(level_data) if level_data else '')
            
            level = ObjectiveLevel.UNKNOWN
            if level_code:
                if 'Primary' in level_code:
                    level = ObjectiveLevel.PRIMARY
                    primary_count += 1
                elif 'Secondary' in level_code:
                    level = ObjectiveLevel.SECONDARY
                    secondary_count += 1
                elif 'Exploratory' in level_code:
                    level = ObjectiveLevel.EXPLORATORY
                    exploratory_count += 1
            
            objectives.append(Objective(
                id=obj_data.get('id', f"obj_{len(objectives)+1}"),
                name=obj_data.get('name', ''),
                text=obj_data.get('text', ''),
                level=level,
                endpoint_ids=obj_data.get('endpointIds', []),
            ))
        
        # Parse endpoints with level codes
        for ep_data in raw.get('endpoints', []):
            # Skip non-dict items
            if not isinstance(ep_data, dict):
                logger.warning(f"Skipping non-dict endpoint item: {type(ep_data).__name__}")
                continue
            level_data = ep_data.get('level', {})
            level_code = level_data.get('code') if isinstance(level_data, dict) else (str(level_data) if level_data else '')
            
            level = EndpointLevel.UNKNOWN
            if level_code:
                if 'Primary' in level_code:
                    level = EndpointLevel.PRIMARY
                elif 'Secondary' in level_code:
                    level = EndpointLevel.SECONDARY
                elif 'Exploratory' in level_code:
                    level = EndpointLevel.EXPLORATORY
            
            endpoints.append(Endpoint(
                id=ep_data.get('id', f"ep_{len(endpoints)+1}"),
                name=ep_data.get('name', ''),
                text=ep_data.get('text', ''),
                level=level,
                purpose=ep_data.get('purpose'),
            ))
        
        return ObjectivesData(
            objectives=objectives,
            endpoints=endpoints,
            estimands=[],  # Populated in Phase 2
            primary_objectives_count=primary_count,
            secondary_objectives_count=secondary_count,
            exploratory_objectives_count=exploratory_count,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse objectives: {e}")
        return None


def _parse_estimands(raw: Dict[str, Any]) -> List[Estimand]:
    """Parse Phase 2 response (estimands only) - aligned with USDM 4.0."""
    estimands = []
    
    try:
        for est_data in raw.get('estimands', []):
            endpoint_id = est_data.get('endpointId')
            
            # Parse intercurrent events - ensure at least one for USDM compliance
            ice_list = []
            for ie_data in est_data.get('intercurrentEvents', []):
                if isinstance(ie_data, dict):
                    strategy_data = ie_data.get('strategy', {})
                    strategy_code = strategy_data.get('code', 'TreatmentPolicy') if isinstance(strategy_data, dict) else str(strategy_data)
                    strategy = _map_strategy(strategy_code)
                    ice_text = ie_data.get('text') or ie_data.get('description') or ie_data.get('name', 'Intercurrent event')
                    ice_list.append(IntercurrentEvent(
                        id=ie_data.get('id', f"ice_{len(estimands)+1}_{len(ice_list)+1}"),
                        name=ie_data.get('name', 'Intercurrent Event'),
                        text=ice_text,
                        strategy=strategy,
                        description=ie_data.get('description'),
                        label=ie_data.get('label'),
                    ))
            
            # Population summary - combine population and analysis population
            pop_text = est_data.get('populationSummary') or est_data.get('population', '')
            analysis_pop = est_data.get('analysisPopulation', '')
            if analysis_pop and analysis_pop not in pop_text:
                pop_text = f"{pop_text} ({analysis_pop})" if pop_text else analysis_pop
            if not pop_text:
                pop_text = 'Study population as defined by eligibility criteria'
            
            # Extract intervention IDs - convert intervention names to IDs if needed
            intervention_ids = est_data.get('interventionIds', [])
            intervention_names = est_data.get('interventionNames', [])
            treatment_desc = est_data.get('treatmentDescription') or est_data.get('treatment', '')
            
            # If no intervention IDs but we have names, create placeholder IDs
            if not intervention_ids and intervention_names:
                intervention_ids = [f"int_{i+1}" for i in range(len(intervention_names))]
            
            estimands.append(Estimand(
                id=est_data.get('id', f"est_{len(estimands)+1}"),
                name=est_data.get('name', ''),
                label=est_data.get('label'),
                description=est_data.get('description'),
                population_summary=pop_text,
                analysis_population_id=est_data.get('analysisPopulationId'),
                variable_of_interest_id=endpoint_id,
                intervention_ids=intervention_ids,
                intercurrent_events=ice_list,
                summary_measure=est_data.get('summaryMeasure'),
                treatment=treatment_desc,
                analysis_population=analysis_pop,
                variable_of_interest=est_data.get('variableOfInterest'),
                endpoint_id=endpoint_id,
            ))
    
    except Exception as e:
        logger.error(f"Failed to parse estimands: {e}")
    
    return estimands


def _repair_json(json_str: str) -> str:
    """Attempt to repair common JSON syntax errors."""
    repaired = json_str
    
    # Fix unterminated strings - close them before newlines or end
    # This handles cases like: "text that was cut off
    lines = repaired.split('\n')
    fixed_lines = []
    for line in lines:
        # Count quotes in line (excluding escaped quotes)
        quote_count = len(re.findall(r'(?<!\\)"', line))
        if quote_count % 2 == 1:
            # Odd number of quotes - line has unterminated string
            line = line.rstrip() + '"'
        fixed_lines.append(line)
    repaired = '\n'.join(fixed_lines)
    
    # Fix missing commas between elements
    repaired = re.sub(r'"\s*\n\s*"', '",\n"', repaired)
    repaired = re.sub(r'}\s*\n\s*{', '},\n{', repaired)
    repaired = re.sub(r']\s*\n\s*"', '],\n"', repaired)
    repaired = re.sub(r'"\s*\n\s*{', '",\n{', repaired)
    repaired = re.sub(r'}\s*\n\s*"', '},\n"', repaired)
    
    # Fix trailing commas before closing brackets
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)
    
    # Ensure proper closing brackets
    open_braces = repaired.count('{') - repaired.count('}')
    open_brackets = repaired.count('[') - repaired.count(']')
    
    if open_braces > 0:
        repaired = repaired.rstrip() + '}' * open_braces
    if open_brackets > 0:
        repaired = repaired.rstrip() + ']' * open_brackets
    
    return repaired


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    def normalize_result(result):
        """Ensure result is a dict with expected structure."""
        if isinstance(result, dict):
            return result
        elif isinstance(result, list):
            # LLM returned a list - try to determine what it contains
            logger.warning(f"LLM returned list instead of dict ({len(result)} items), attempting to normalize")
            if result and isinstance(result[0], dict):
                first_item = result[0]
                # Check if first item IS the expected dict structure (wrapped in list)
                if 'objectives' in first_item or 'endpoints' in first_item:
                    logger.info("Found wrapped dict structure in list, extracting first item")
                    return first_item
                # Otherwise check if these are objectives or endpoints based on structure
                if 'endpointIds' in first_item or ('level' in first_item and 'text' in first_item):
                    # Looks like a list of objectives
                    return {"objectives": result, "endpoints": []}
                elif 'purpose' in first_item:
                    # Looks like a list of endpoints
                    return {"objectives": [], "endpoints": result}
            # Default: assume it's objectives
            return {"objectives": result, "endpoints": []}
        return None
    
    try:
        result = json.loads(response_text)
        return normalize_result(result)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        
        # Try to repair and parse again
        try:
            repaired = _repair_json(response_text)
            result = json.loads(repaired)
            logger.info("Successfully parsed JSON after repair")
            return normalize_result(result)
        except json.JSONDecodeError as e2:
            logger.warning(f"JSON repair also failed: {e2}")
            return None


def _parse_usdm_format(raw: Dict[str, Any]) -> Optional[ObjectivesData]:
    """Parse new USDM-compliant format with flat objectives/endpoints lists."""
    try:
        objectives = []
        endpoints = []
        estimands = []
        
        primary_count = 0
        secondary_count = 0
        exploratory_count = 0
        
        # Parse objectives with level codes - use UNKNOWN if not extracted
        for obj_data in raw.get('objectives', []):
            level_data = obj_data.get('level', {})
            level_code = level_data.get('code') if isinstance(level_data, dict) else (str(level_data) if level_data else '')
            
            # Map level code to enum - default to UNKNOWN if not specified
            level = ObjectiveLevel.UNKNOWN
            if level_code:
                if 'Primary' in level_code:
                    level = ObjectiveLevel.PRIMARY
                    primary_count += 1
                elif 'Secondary' in level_code:
                    level = ObjectiveLevel.SECONDARY
                    secondary_count += 1
                elif 'Exploratory' in level_code:
                    level = ObjectiveLevel.EXPLORATORY
                    exploratory_count += 1
            
            objectives.append(Objective(
                id=obj_data.get('id', f"obj_{len(objectives)+1}"),
                name=obj_data.get('name', ''),
                text=obj_data.get('text', ''),
                level=level,
                endpoint_ids=obj_data.get('endpointIds', []),
            ))
        
        # Parse endpoints with level codes - use UNKNOWN if not extracted
        for ep_data in raw.get('endpoints', []):
            level_data = ep_data.get('level', {})
            level_code = level_data.get('code') if isinstance(level_data, dict) else (str(level_data) if level_data else '')
            
            level = EndpointLevel.UNKNOWN
            if level_code:
                if 'Primary' in level_code:
                    level = EndpointLevel.PRIMARY
                elif 'Secondary' in level_code:
                    level = EndpointLevel.SECONDARY
                elif 'Exploratory' in level_code:
                    level = EndpointLevel.EXPLORATORY
            
            endpoints.append(Endpoint(
                id=ep_data.get('id', f"ep_{len(endpoints)+1}"),
                name=ep_data.get('name', ''),
                text=ep_data.get('text', ''),
                level=level,
                purpose=ep_data.get('purpose'),
            ))
        
        # Parse estimands if present - with full ICH E9(R1) attributes aligned to USDM 4.0
        for est_data in raw.get('estimands', []):
            endpoint_id = est_data.get('endpointId')
            
            # Parse intercurrent events - USDM 4.0 requires: id, name, text, strategy
            ice_list = []
            for ie_data in est_data.get('intercurrentEvents', []):
                if isinstance(ie_data, dict):
                    strategy_data = ie_data.get('strategy', {})
                    strategy_code = strategy_data.get('code', 'TreatmentPolicy') if isinstance(strategy_data, dict) else str(strategy_data)
                    strategy = _map_strategy(strategy_code)
                    # text is required in USDM 4.0 - use description or name as fallback
                    ice_text = ie_data.get('text') or ie_data.get('description') or ie_data.get('name', 'Intercurrent event')
                    ice_list.append(IntercurrentEvent(
                        id=ie_data.get('id', f"ice_{len(estimands)+1}_{len(ice_list)+1}"),
                        name=ie_data.get('name', 'Intercurrent Event'),
                        text=ice_text,  # Required in USDM 4.0
                        strategy=strategy,
                        description=ie_data.get('description'),
                        label=ie_data.get('label'),
                    ))
            
            # Population summary in USDM 4.0 is the population-level summary (ICH E9 attribute 5)
            # It should describe both the population AND how the effect is summarized
            pop_text = est_data.get('population', est_data.get('populationSummary', 'Study population as defined by eligibility criteria'))
            
            estimands.append(Estimand(
                id=est_data.get('id', f"est_{len(estimands)+1}"),
                name=est_data.get('name', ''),
                label=est_data.get('label'),
                description=est_data.get('description'),
                # USDM 4.0 required fields
                population_summary=pop_text,
                analysis_population_id=est_data.get('analysisPopulationId'),
                variable_of_interest_id=endpoint_id,
                intervention_ids=est_data.get('interventionIds', []),
                intercurrent_events=ice_list,
                # Extension fields for ICH E9(R1) context
                summary_measure=est_data.get('summaryMeasure'),
                treatment=est_data.get('treatment'),
                analysis_population=est_data.get('analysisPopulation') or est_data.get('population'),
                variable_of_interest=est_data.get('variableOfInterest'),
                endpoint_id=endpoint_id,
            ))
        
        logger.info(f"Parsed USDM format: {primary_count} primary, {secondary_count} secondary, {exploratory_count} exploratory objectives")
        
        return ObjectivesData(
            objectives=objectives,
            endpoints=endpoints,
            estimands=estimands,
            primary_objectives_count=primary_count,
            secondary_objectives_count=secondary_count,
            exploratory_objectives_count=exploratory_count,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse USDM format objectives: {e}")
        return None


def _parse_objectives_response(raw: Dict[str, Any]) -> Optional[ObjectivesData]:
    """Parse raw LLM response into ObjectivesData object.
    
    Handles two formats:
    1. New USDM-compliant format: flat 'objectives' and 'endpoints' lists with level codes
    2. Legacy format: grouped by 'primaryObjectives', 'secondaryObjectives', etc.
    """
    try:
        # Handle case where LLM returns a list instead of a dict
        if isinstance(raw, list):
            if len(raw) == 1 and isinstance(raw[0], dict):
                raw = raw[0]
            else:
                # Assume list contains objectives directly
                raw = {'objectives': raw}
        
        # Check for new USDM-compliant format (flat objectives list with level codes)
        if raw.get('objectives') and isinstance(raw['objectives'], list) and len(raw['objectives']) > 0:
            first_obj = raw['objectives'][0]
            if isinstance(first_obj, dict) and 'level' in first_obj and isinstance(first_obj.get('level'), dict):
                # New format - objectives already have proper structure
                return _parse_usdm_format(raw)
        
        # Legacy format processing
        objectives = []
        endpoints = []
        estimands = []
        
        endpoint_counter = 1
        objective_counter = 1
        
        # Process primary objectives
        for obj_data in raw.get('primaryObjectives', []):
            obj_id, ep_ids, new_endpoints, endpoint_counter = _process_objective(
                obj_data, ObjectiveLevel.PRIMARY, objective_counter, endpoint_counter
            )
            if obj_id:
                objectives.append(Objective(
                    id=obj_id,
                    name=f"Primary Objective {objective_counter}",
                    text=obj_data.get('text', ''),
                    level=ObjectiveLevel.PRIMARY,
                    endpoint_ids=ep_ids,
                ))
                endpoints.extend(new_endpoints)
                objective_counter += 1
        
        primary_count = len([o for o in objectives if o.level == ObjectiveLevel.PRIMARY])
        
        # Process secondary objectives
        sec_counter = 1
        for obj_data in raw.get('secondaryObjectives', []):
            obj_id = f"obj_sec_{sec_counter}"
            ep_ids = []
            new_endpoints = []
            
            for ep_data in obj_data.get('endpoints', []):
                ep_id = f"ep_{endpoint_counter}"
                ep_text = ep_data.get('text', '') if isinstance(ep_data, dict) else str(ep_data)
                ep_purpose = ep_data.get('purpose', 'Secondary') if isinstance(ep_data, dict) else None
                
                if ep_text:
                    new_endpoints.append(Endpoint(
                        id=ep_id,
                        name=f"Secondary Endpoint {endpoint_counter}",
                        text=ep_text,
                        level=EndpointLevel.SECONDARY,
                        purpose=ep_purpose,
                        objective_id=obj_id,
                    ))
                    ep_ids.append(ep_id)
                    endpoint_counter += 1
            
            if obj_data.get('text'):
                objectives.append(Objective(
                    id=obj_id,
                    name=f"Secondary Objective {sec_counter}",
                    text=obj_data['text'],
                    level=ObjectiveLevel.SECONDARY,
                    endpoint_ids=ep_ids,
                ))
                endpoints.extend(new_endpoints)
                sec_counter += 1
        
        secondary_count = len([o for o in objectives if o.level == ObjectiveLevel.SECONDARY])
        
        # Process exploratory objectives
        exp_counter = 1
        for obj_data in raw.get('exploratoryObjectives', []):
            obj_id = f"obj_exp_{exp_counter}"
            ep_ids = []
            new_endpoints = []
            
            for ep_data in obj_data.get('endpoints', []):
                ep_id = f"ep_{endpoint_counter}"
                ep_text = ep_data.get('text', '') if isinstance(ep_data, dict) else str(ep_data)
                ep_purpose = ep_data.get('purpose', 'Exploratory') if isinstance(ep_data, dict) else None
                
                if ep_text:
                    new_endpoints.append(Endpoint(
                        id=ep_id,
                        name=f"Exploratory Endpoint {endpoint_counter}",
                        text=ep_text,
                        level=EndpointLevel.EXPLORATORY,
                        purpose=ep_purpose,
                        objective_id=obj_id,
                    ))
                    ep_ids.append(ep_id)
                    endpoint_counter += 1
            
            if obj_data.get('text'):
                objectives.append(Objective(
                    id=obj_id,
                    name=f"Exploratory Objective {exp_counter}",
                    text=obj_data['text'],
                    level=ObjectiveLevel.EXPLORATORY,
                    endpoint_ids=ep_ids,
                ))
                endpoints.extend(new_endpoints)
                exp_counter += 1
        
        exploratory_count = len([o for o in objectives if o.level == ObjectiveLevel.EXPLORATORY])
        
        # Process estimands (if present) - aligned with USDM 4.0
        est_counter = 1
        for est_data in raw.get('estimands', []):
            if not isinstance(est_data, dict):
                continue
                
            ice_list = []
            for ie_data in est_data.get('intercurrentEvents', []):
                if isinstance(ie_data, dict):
                    strategy = _map_strategy(ie_data.get('strategy', 'Treatment Policy'))
                    event_name = ie_data.get('event') or ie_data.get('name', 'Intercurrent Event')
                    event_text = ie_data.get('text') or ie_data.get('description') or event_name
                    ice_list.append(IntercurrentEvent(
                        id=f"ice_{est_counter}_{len(ice_list)+1}",
                        name=event_name,
                        text=event_text,  # Required in USDM 4.0
                        strategy=strategy,
                        description=ie_data.get('description'),
                    ))
            
            estimands.append(Estimand(
                id=f"est_{est_counter}",
                name=est_data.get('name', f'Estimand {est_counter}'),
                population_summary=est_data.get('population', 'Study population as defined by eligibility criteria'),
                summary_measure=est_data.get('summaryMeasure', 'Unknown'),
                analysis_population=est_data.get('population'),
                treatment=est_data.get('treatment'),
                variable_of_interest=est_data.get('variable'),
                intercurrent_events=ice_list,
            ))
            est_counter += 1
        
        return ObjectivesData(
            objectives=objectives,
            endpoints=endpoints,
            estimands=estimands,
            primary_objectives_count=primary_count,
            secondary_objectives_count=secondary_count,
            exploratory_objectives_count=exploratory_count,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse objectives response: {e}")
        return None


def _process_objective(
    obj_data: Dict[str, Any],
    level: ObjectiveLevel,
    obj_counter: int,
    ep_counter: int,
) -> Tuple[Optional[str], List[str], List[Endpoint], int]:
    """Process a single objective and its endpoints."""
    if not isinstance(obj_data, dict) or not obj_data.get('text'):
        return None, [], [], ep_counter
    
    obj_id = f"obj_pri_{obj_counter}" if level == ObjectiveLevel.PRIMARY else f"obj_{obj_counter}"
    ep_ids = []
    endpoints = []
    
    ep_level = EndpointLevel.PRIMARY if level == ObjectiveLevel.PRIMARY else EndpointLevel.SECONDARY
    
    for ep_data in obj_data.get('endpoints', []):
        ep_id = f"ep_{ep_counter}"
        ep_text = ep_data.get('text', '') if isinstance(ep_data, dict) else str(ep_data)
        ep_purpose = ep_data.get('purpose', 'Efficacy') if isinstance(ep_data, dict) else None
        
        if ep_text:
            endpoints.append(Endpoint(
                id=ep_id,
                name=f"{'Primary' if level == ObjectiveLevel.PRIMARY else 'Secondary'} Endpoint {ep_counter}",
                text=ep_text,
                level=ep_level,
                purpose=ep_purpose,
                objective_id=obj_id,
            ))
            ep_ids.append(ep_id)
            ep_counter += 1
    
    return obj_id, ep_ids, endpoints, ep_counter


def _map_strategy(strategy_str: str) -> IntercurrentEventStrategy:
    """Map string to IntercurrentEventStrategy enum."""
    strategy_lower = strategy_str.lower()
    if 'composite' in strategy_lower:
        return IntercurrentEventStrategy.COMPOSITE
    elif 'hypothetical' in strategy_lower:
        return IntercurrentEventStrategy.HYPOTHETICAL
    elif 'principal' in strategy_lower or 'stratum' in strategy_lower:
        return IntercurrentEventStrategy.PRINCIPAL_STRATUM
    elif 'while on' in strategy_lower:
        return IntercurrentEventStrategy.WHILE_ON_TREATMENT
    return IntercurrentEventStrategy.TREATMENT_POLICY


def save_objectives_result(
    result: ObjectivesExtractionResult,
    output_path: str,
) -> None:
    """Save objectives extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["objectivesEndpoints"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved objectives/endpoints to {output_path}")
