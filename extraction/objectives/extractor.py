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
)
from .prompts import build_objectives_extraction_prompt

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
) -> ObjectivesExtractionResult:
    """
    Extract objectives and endpoints from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model_name: LLM model to use
        pages: Specific pages to use (0-indexed), auto-detected if None
        protocol_text: Optional pre-extracted text
        study_indication: Indication from metadata for context
        study_phase: Study phase from metadata for context
        
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
        
        # Call LLM for extraction
        logger.info("Extracting objectives and endpoints with LLM...")
        
        # Build context hints from prior extractions
        context_hints = ""
        if study_indication:
            context_hints += f"\nStudy indication: {study_indication}"
        if study_phase:
            context_hints += f"\nStudy phase: {study_phase}"
        
        prompt = build_objectives_extraction_prompt(protocol_text, context_hints=context_hints)
        
        response = call_llm(
            prompt=prompt,
            model_name=model_name,
            json_mode=True,
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
        result.data = _parse_objectives_response(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {result.data.primary_objectives_count} primary, "
                f"{result.data.secondary_objectives_count} secondary, "
                f"{result.data.exploratory_objectives_count} exploratory objectives"
            )
        
    except Exception as e:
        logger.error(f"Objectives extraction failed: {e}")
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


def _parse_usdm_format(raw: Dict[str, Any]) -> Optional[ObjectivesData]:
    """Parse new USDM-compliant format with flat objectives/endpoints lists."""
    try:
        objectives = []
        endpoints = []
        estimands = []
        
        primary_count = 0
        secondary_count = 0
        exploratory_count = 0
        
        # Parse objectives with level codes
        for obj_data in raw.get('objectives', []):
            level_data = obj_data.get('level', {})
            level_code = level_data.get('code', 'Primary') if isinstance(level_data, dict) else str(level_data)
            
            # Map level code to enum
            if 'Primary' in level_code:
                level = ObjectiveLevel.PRIMARY
                primary_count += 1
            elif 'Secondary' in level_code:
                level = ObjectiveLevel.SECONDARY
                secondary_count += 1
            else:
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
            level_data = ep_data.get('level', {})
            level_code = level_data.get('code', 'Primary') if isinstance(level_data, dict) else str(level_data)
            
            if 'Primary' in level_code:
                level = EndpointLevel.PRIMARY
            elif 'Secondary' in level_code:
                level = EndpointLevel.SECONDARY
            else:
                level = EndpointLevel.EXPLORATORY
            
            endpoints.append(Endpoint(
                id=ep_data.get('id', f"ep_{len(endpoints)+1}"),
                name=ep_data.get('name', ''),
                text=ep_data.get('text', ''),
                level=level,
                purpose=ep_data.get('purpose'),
            ))
        
        # Parse estimands if present
        for est_data in raw.get('estimands', []):
            estimands.append(Estimand(
                id=est_data.get('id', f"est_{len(estimands)+1}"),
                name=est_data.get('name', ''),
                objective_id=est_data.get('objectiveId'),
                endpoint_id=est_data.get('endpointId'),
                population=est_data.get('population'),
                analysis_population=est_data.get('analysisPopulation'),
                treatment=est_data.get('treatment'),
                variable_of_interest=est_data.get('variableOfInterest'),
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
        
        # Process estimands (if present)
        est_counter = 1
        for est_data in raw.get('estimands', []):
            if not isinstance(est_data, dict):
                continue
                
            ice_list = []
            for ie_data in est_data.get('intercurrentEvents', []):
                if isinstance(ie_data, dict):
                    strategy = _map_strategy(ie_data.get('strategy', 'Treatment Policy'))
                    ice_list.append(IntercurrentEvent(
                        id=f"ice_{est_counter}_{len(ice_list)+1}",
                        name=ie_data.get('event', 'Intercurrent Event'),
                        description=ie_data.get('event', ''),
                        strategy=strategy,
                    ))
            
            estimands.append(Estimand(
                id=f"est_{est_counter}",
                name=est_data.get('name', f'Estimand {est_counter}'),
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
