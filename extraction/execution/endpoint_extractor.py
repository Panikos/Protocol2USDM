"""
Endpoint Algorithm Extractor

Extracts computational logic for study endpoints from protocol PDFs.
Captures the algorithms needed to evaluate primary, secondary, and
exploratory endpoints deterministically.
"""

import re
import logging
from typing import List, Optional, Tuple, Dict, Any

from .schema import (
    EndpointAlgorithm,
    EndpointType,
    ExecutionModelData,
    ExecutionModelResult,
)

logger = logging.getLogger(__name__)


# Keywords for finding endpoint pages
ENDPOINT_KEYWORDS = [
    "primary endpoint", "secondary endpoint", "exploratory endpoint",
    "primary objective", "secondary objective", "efficacy endpoint",
    "safety endpoint", "outcome measure", "primary efficacy",
    "success criteria", "responder definition", "response rate",
    "change from baseline", "time to event", "survival",
]

# Patterns for detecting endpoint types
ENDPOINT_TYPE_PATTERNS = [
    (r'primary\s+(?:efficacy\s+)?endpoint', EndpointType.PRIMARY, 0.95),
    (r'primary\s+(?:study\s+)?objective', EndpointType.PRIMARY, 0.90),
    (r'secondary\s+(?:efficacy\s+)?endpoint', EndpointType.SECONDARY, 0.95),
    (r'secondary\s+(?:study\s+)?objective', EndpointType.SECONDARY, 0.90),
    (r'exploratory\s+endpoint', EndpointType.EXPLORATORY, 0.90),
    (r'safety\s+endpoint', EndpointType.SAFETY, 0.90),
    (r'key\s+secondary', EndpointType.SECONDARY, 0.85),
]

# Patterns for extracting algorithm components
ALGORITHM_PATTERNS = [
    # Change from baseline
    (r'change\s+(?:from\s+)?baseline\s+(?:in\s+)?(\w+(?:\s+\w+)?)', 'change_from_baseline'),
    # Percent change
    (r'(?:percent|%)\s+change\s+(?:from\s+baseline\s+)?(?:in\s+)?(\w+)', 'percent_change'),
    # Response rate / responder
    (r'(?:response|responder)\s+rate', 'response_rate'),
    (r'proportion\s+(?:of\s+)?(?:subjects?|patients?)\s+(?:with|achieving)', 'proportion'),
    # Time to event
    (r'time\s+to\s+(\w+(?:\s+\w+)?)', 'time_to_event'),
    # Threshold-based
    (r'(?:>=?|≥)\s*(\d+(?:\.\d+)?)\s*(%|mg/?d?l?|mmol|kg)', 'threshold'),
    (r'(?:<=?|≤)\s*(\d+(?:\.\d+)?)\s*(%|mg/?d?l?|mmol|kg)', 'threshold'),
    # Recovery/achievement
    (r'(?:achieve|reach|recover)\s+(?:a\s+)?(\w+(?:\s+\w+)?)', 'achievement'),
    # Duration-based
    (r'within\s+(\d+)\s*(min(?:ute)?s?|hours?|days?|weeks?)', 'duration'),
]

# Common input variables by therapeutic area
COMMON_INPUTS = {
    'diabetes': ['glucose', 'PG', 'HbA1c', 'fasting glucose', 'insulin'],
    'oncology': ['tumor size', 'ORR', 'PFS', 'OS', 'CR', 'PR'],
    'cardiovascular': ['blood pressure', 'systolic', 'diastolic', 'LDL', 'HDL'],
    'neurology': ['cognitive score', 'MMSE', 'ADAS-Cog'],
    'immunology': ['ACR20', 'ACR50', 'ACR70', 'DAS28'],
}


def find_endpoint_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain endpoint definitions."""
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    page_count = get_page_count(pdf_path)
    relevant_pages = []
    
    for page_idx in range(min(page_count, 80)):
        text = extract_text_from_pages(pdf_path, [page_idx])
        if text:
            text_lower = text.lower()
            score = sum(1 for kw in ENDPOINT_KEYWORDS if kw in text_lower)
            if score >= 2:
                relevant_pages.append(page_idx)
    
    return relevant_pages


def _detect_endpoint_type(text: str) -> Tuple[EndpointType, float]:
    """Detect the type of endpoint from text."""
    text_lower = text.lower()
    
    for pattern, ep_type, confidence in ENDPOINT_TYPE_PATTERNS:
        if re.search(pattern, text_lower):
            return ep_type, confidence
    
    return EndpointType.EXPLORATORY, 0.5


def _extract_inputs(text: str) -> List[str]:
    """Extract input variables mentioned in endpoint text."""
    inputs = []
    text_lower = text.lower()
    
    # Check common therapeutic area inputs
    for area, vars in COMMON_INPUTS.items():
        for var in vars:
            if var.lower() in text_lower:
                inputs.append(var)
    
    # Extract measurement terms
    measurement_pattern = r'(?:measure|assess|evaluate|determine)\s+(?:the\s+)?(\w+(?:\s+\w+)?)'
    for match in re.finditer(measurement_pattern, text_lower):
        inputs.append(match.group(1).strip())
    
    return list(set(inputs))


def _extract_time_window(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract time window reference and duration."""
    text_lower = text.lower()
    
    # Duration patterns
    duration_match = re.search(
        r'within\s+(\d+)\s*(min(?:ute)?s?|hours?|days?|weeks?)',
        text_lower
    )
    
    duration = None
    if duration_match:
        value = duration_match.group(1)
        unit = duration_match.group(2).lower()
        if 'min' in unit:
            duration = f"PT{value}M"
        elif 'hour' in unit:
            duration = f"PT{value}H"
        elif 'day' in unit:
            duration = f"P{value}D"
        elif 'week' in unit:
            duration = f"P{value}W"
    
    # Reference patterns
    reference = None
    ref_patterns = [
        (r'(?:from|after|following)\s+(\w+(?:\s+\w+)?(?:\s+administration)?)', 1),
        (r'(?:at|by)\s+(week\s+\d+|day\s+\d+|baseline)', 1),
        (r'(post[- ]?dose|pre[- ]?dose)', 1),
    ]
    
    for pattern, group in ref_patterns:
        match = re.search(pattern, text_lower)
        if match:
            reference = match.group(group).strip()
            break
    
    return reference, duration


def _extract_algorithm(text: str) -> Optional[str]:
    """Extract the computational algorithm from endpoint text."""
    text_lower = text.lower()
    
    # Look for explicit formulas
    formula_patterns = [
        r'(?:calculated|computed|defined)\s+as\s+[:\s]*([^.]+)',
        r'formula[:\s]+([^.]+)',
        r'=\s*([^.]+)',
    ]
    
    for pattern in formula_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    # Build algorithm from detected patterns
    algorithm_parts = []
    
    # Change from baseline
    if 'change from baseline' in text_lower:
        var_match = re.search(r'change\s+from\s+baseline\s+(?:in\s+)?(\w+)', text_lower)
        if var_match:
            var = var_match.group(1)
            algorithm_parts.append(f"{var}_postbaseline - {var}_baseline")
    
    # Threshold comparison
    threshold_match = re.search(r'(>=?|≥|<=?|≤)\s*(\d+(?:\.\d+)?)\s*(\S+)?', text)
    if threshold_match:
        op = threshold_match.group(1).replace('≥', '>=').replace('≤', '<=')
        val = threshold_match.group(2)
        unit = threshold_match.group(3) or ''
        algorithm_parts.append(f"value {op} {val}{unit}")
    
    # Response criteria
    if 'responder' in text_lower or 'response' in text_lower:
        response_match = re.search(r'(\d+)%?\s+(?:or\s+more\s+)?(?:reduction|improvement|decrease)', text_lower)
        if response_match:
            pct = response_match.group(1)
            algorithm_parts.append(f"improvement >= {pct}%")
    
    return ' AND '.join(algorithm_parts) if algorithm_parts else None


def _extract_success_criteria(text: str) -> Optional[str]:
    """Extract success/response criteria from text."""
    patterns = [
        r'success(?:ful)?\s+(?:is\s+)?(?:defined\s+as|if)\s+([^.]+)',
        r'responder\s+(?:is\s+)?(?:defined\s+as)\s+([^.]+)',
        r'(?:achieve|achieving)\s+([^.]+)',
        r'criterion\s+(?:for\s+success)?[:\s]+([^.]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).strip()
    
    return None


def _extract_unit(text: str) -> Optional[str]:
    """Extract the measurement unit from text."""
    unit_patterns = [
        r'(\d+(?:\.\d+)?)\s*(mg/?d?l?|mmol/?l?|%|kg/?m?2?|mm\s*hg)',
        r'(?:measured|expressed)\s+(?:in|as)\s+(\w+(?:/\w+)?)',
    ]
    
    for pattern in unit_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1) if match.lastindex == 1 else match.group(2)
    
    return None


def _parse_endpoints_from_text(text: str) -> List[EndpointAlgorithm]:
    """Parse endpoint definitions from text."""
    endpoints = []
    
    # Split by endpoint type markers
    sections = re.split(
        r'(?=(?:primary|secondary|exploratory|safety)\s+(?:efficacy\s+)?(?:endpoint|objective))',
        text,
        flags=re.IGNORECASE
    )
    
    for i, section in enumerate(sections):
        if len(section.strip()) < 30:
            continue
        
        ep_type, confidence = _detect_endpoint_type(section)
        
        # Extract endpoint name
        name_match = re.search(
            r'(?:primary|secondary|exploratory|safety)\s+(?:efficacy\s+)?(?:endpoint|objective)[:\s]*([^.]+)',
            section,
            re.IGNORECASE
        )
        name = name_match.group(1).strip() if name_match else f"{ep_type.value} Endpoint {i+1}"
        name = name[:100]  # Truncate long names
        
        inputs = _extract_inputs(section)
        time_ref, time_dur = _extract_time_window(section)
        algorithm = _extract_algorithm(section)
        success_criteria = _extract_success_criteria(section)
        unit = _extract_unit(section)
        
        endpoint = EndpointAlgorithm(
            id=f"ep_{i+1}",
            name=name,
            endpoint_type=ep_type,
            inputs=inputs,
            time_window_reference=time_ref,
            time_window_duration=time_dur,
            algorithm=algorithm,
            success_criteria=success_criteria,
            unit=unit,
            source_text=section[:300],
        )
        endpoints.append(endpoint)
    
    return endpoints


def extract_endpoint_algorithms(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
    sap_path: Optional[str] = None,
) -> ExecutionModelResult:
    """
    Extract endpoint algorithms from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        use_llm: Whether to use LLM enhancement
        
    Returns:
        ExecutionModelResult with endpoint algorithms
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting endpoint algorithm extraction...")
    
    # Find relevant pages
    pages = find_endpoint_pages(pdf_path)
    
    if not pages:
        pages = list(range(min(50, get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential endpoint pages")
    
    # Extract text
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Parse endpoints from text
    endpoints = _parse_endpoints_from_text(text)
    
    # Extract from SAP if provided (SAP has more detailed analysis methods)
    if sap_path:
        logger.info("Extracting additional endpoints from SAP...")
        try:
            sap_pages = find_endpoint_pages(sap_path)
            if not sap_pages:
                sap_pages = list(range(min(80, get_page_count(sap_path))))
            sap_text = extract_text_from_pages(sap_path, sap_pages)
            if sap_text:
                sap_endpoints = _parse_endpoints_from_text(sap_text)
                # Merge SAP endpoints (often has more detail on analysis methods)
                for sap_ep in sap_endpoints:
                    # Check if already exists (by name similarity)
                    existing = [e for e in endpoints if e.name.lower() in sap_ep.name.lower() or sap_ep.name.lower() in e.name.lower()]
                    if existing:
                        # Enhance existing with SAP details
                        if sap_ep.algorithm and not existing[0].algorithm:
                            existing[0].algorithm = sap_ep.algorithm
                        if sap_ep.success_criteria and not existing[0].success_criteria:
                            existing[0].success_criteria = sap_ep.success_criteria
                    else:
                        sap_ep.source_text = f"[SAP] {sap_ep.source_text}"
                        endpoints.append(sap_ep)
                logger.info(f"  Added/enhanced endpoints from SAP: {len(sap_endpoints)}")
        except Exception as e:
            logger.warning(f"SAP endpoint extraction failed: {e}")
    
    # LLM enhancement
    if use_llm and endpoints:
        try:
            enhanced = _enhance_with_llm(text, endpoints, model)
            if enhanced:
                endpoints = enhanced
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
    
    logger.info(f"Extracted {len(endpoints)} endpoint algorithms")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(endpoint_algorithms=endpoints),
        pages_used=pages,
        model_used=model,
    )


def _enhance_with_llm(
    text: str,
    endpoints: List[EndpointAlgorithm],
    model: str,
) -> Optional[List[EndpointAlgorithm]]:
    """Enhance endpoint extraction using LLM."""
    from core.llm_client import call_llm
    from .prompts import ENDPOINT_ALGORITHM_PROMPT, format_prompt
    
    prompt = format_prompt(ENDPOINT_ALGORITHM_PROMPT, protocol_text=text[:8000])
    
    try:
        result = call_llm(
            prompt=prompt,
            model_name=model,
            temperature=0.1,
        )
        
        # Extract response text from dict
        if isinstance(result, dict):
            if 'error' in result:
                logger.warning(f"LLM call error: {result['error']}")
                return None
            response = result.get('response', '')
        else:
            response = str(result)
        
        if not response:
            return None
        
        # Parse JSON response
        import json
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        
        # Convert to EndpointAlgorithm objects
        enhanced = []
        for i, ep_data in enumerate(data.get('endpoints', [])):
            ep_type = EndpointType.PRIMARY
            type_str = ep_data.get('type', 'Primary').lower()
            if 'secondary' in type_str:
                ep_type = EndpointType.SECONDARY
            elif 'exploratory' in type_str:
                ep_type = EndpointType.EXPLORATORY
            elif 'safety' in type_str:
                ep_type = EndpointType.SAFETY
            
            time_window = ep_data.get('timeWindow', {})
            
            endpoint = EndpointAlgorithm(
                id=f"ep_{i+1}",
                name=ep_data.get('name', f'Endpoint {i+1}'),
                endpoint_type=ep_type,
                inputs=ep_data.get('inputs', []),
                time_window_reference=time_window.get('reference'),
                time_window_duration=time_window.get('duration'),
                algorithm=ep_data.get('algorithm'),
                success_criteria=ep_data.get('successCriteria'),
                source_text=ep_data.get('sourceQuote', '')[:200],
            )
            enhanced.append(endpoint)
        
        return enhanced if enhanced else None
        
    except Exception as e:
        logger.warning(f"LLM endpoint enhancement failed: {e}")
        return None
