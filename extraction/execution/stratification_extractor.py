"""
Stratification Extractor

Extracts randomization schemes and stratification factors from clinical protocol PDFs.
Uses a multi-pass LLM approach for structured extraction.

Phase 4 Component.

USDM v4.0 mapping:
  - Strata → StudyCohort per factor level under population.cohorts[]
  - Factor levels → Characteristic entities on StudyCohort
  - Factor→Eligibility → StudyCohort.criterionIds[]
  - Allocation rule → TransitionRule.text on randomization StudyElement
  - Full scheme → ExtensionAttribute x-stratification-scheme
"""

import re
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

import fitz  # PyMuPDF

from .schema import (
    ExecutionModelResult,
    ExecutionModelData,
    FactorLevel,
    StratificationFactor,
    RandomizationScheme,
)

logger = logging.getLogger(__name__)

# Maximum chars to send to LLM per pass
MAX_PROMPT_CHARS = 30000

# Keywords for finding randomization sections
RANDOMIZATION_KEYWORDS = [
    "randomization", "randomized", "allocation", "assigned", "stratified",
    "stratification", "blocking", "block size", "treatment assignment",
    "IWRS", "IXRS", "IRT", "interactive", "central randomization",
    "randomization ratio", "allocation ratio", "1:1", "2:1", "1:1:1",
    "minimization", "adaptive randomization", "permuted block",
]

# Ratio patterns
RATIO_PATTERN = re.compile(r'(\d+)\s*:\s*(\d+)(?:\s*:\s*(\d+))?')

# Block size patterns — supports variable block sizes like "4, 6, and 8"
BLOCK_SIZE_PATTERN = re.compile(r'block\s*(?:size)?[s:\s]+(\d+)', re.IGNORECASE)
VARIABLE_BLOCK_PATTERN = re.compile(
    r'block\s*sizes?\s*(?:of\s*)?(\d+)\s*(?:,\s*(\d+))?\s*(?:,?\s*(?:and\s*)?(\d+))?',
    re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────
# PDF text helpers
# ─────────────────────────────────────────────────────────────

def _get_page_count(pdf_path: str) -> int:
    """Get total page count of PDF."""
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def _extract_text_from_pages(pdf_path: str, pages: List[int] = None) -> str:
    """Extract text from specified pages or all pages."""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        if pages is None:
            pages = range(len(doc))
        
        for page_num in pages:
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                text_parts.append(page.get_text())
        
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"Error extracting text: {e}")
        return ""


def find_randomization_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain randomization information."""
    try:
        pages = []
        page_count = _get_page_count(pdf_path)
        
        for page_num in range(page_count):
            try:
                page_text = _extract_text_from_pages(pdf_path, pages=[page_num])
                if page_text:
                    text_lower = page_text.lower()
                    keyword_count = sum(1 for kw in RANDOMIZATION_KEYWORDS if kw.lower() in text_lower)
                    if keyword_count >= 2:
                        pages.append(page_num)
            except Exception:
                continue
        
        return pages[:30]  # Limit to 30 pages
        
    except Exception as e:
        logger.warning(f"Error finding randomization pages: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────

def extract_stratification(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
) -> ExecutionModelResult:
    """
    Extract randomization scheme and stratification factors from a protocol PDF.
    
    Uses a multi-pass approach:
      Pass 1 (heuristic): Quick regex-based extraction for ratio, method, block size
      Pass 2 (LLM - scheme): Full scheme identification with algorithm classification
      Pass 3 (LLM - factors): Detailed factor extraction with exact levels from PDF text
    
    Args:
        pdf_path: Path to the protocol PDF
        model: LLM model to use for enhancement
        use_llm: Whether to use LLM for extraction
        
    Returns:
        ExecutionModelResult with randomization scheme
    """
    logger.info("=" * 60)
    logger.info("PHASE 4C: Stratification/Randomization Extraction (v2 multi-pass)")
    logger.info("=" * 60)
    
    # Find relevant pages
    pages = find_randomization_pages(pdf_path)
    if not pages:
        pages = list(range(min(30, _get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential randomization pages")
    
    # Extract text
    text = _extract_text_from_pages(pdf_path, pages=pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Pass 1: Heuristic extraction
    scheme = _extract_scheme_heuristic(text)
    if scheme:
        logger.info(f"Pass 1 (heuristic): ratio={scheme.ratio}, method={scheme.method}, factors={len(scheme.stratification_factors)}")
    
    # Pass 2+3: LLM multi-pass extraction
    if use_llm and len(text) > 100:
        try:
            # Pass 2: Scheme identification
            llm_scheme = _pass2_scheme_identification(text, model)
            if llm_scheme:
                scheme = _merge_schemes(scheme, llm_scheme)
                logger.info(f"Pass 2 (scheme): ratio={scheme.ratio}, algorithm={scheme.algorithm_type}, IWRS={scheme.iwrs_system}")
            
            # Pass 3: Detailed factor extraction with levels
            if scheme and scheme.stratification_factors:
                factor_names = [f.name for f in scheme.stratification_factors]
                enriched_factors = _pass3_factor_details(text, factor_names, model)
                if enriched_factors:
                    scheme.stratification_factors = enriched_factors
                    logger.info(f"Pass 3 (factors): {len(enriched_factors)} factors with structured levels")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
    
    if scheme:
        total_levels = sum(len(f.factor_levels) for f in scheme.stratification_factors)
        logger.info(f"Final: {scheme.ratio} ratio, {scheme.algorithm_type} algorithm, "
                     f"{len(scheme.stratification_factors)} factors, {total_levels} structured levels")
    else:
        logger.info("No randomization scheme detected")
    
    return ExecutionModelResult(
        success=scheme is not None,
        data=ExecutionModelData(randomization_scheme=scheme) if scheme else ExecutionModelData(),
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


# ─────────────────────────────────────────────────────────────
# Pass 1: Heuristic extraction
# ─────────────────────────────────────────────────────────────

def _extract_scheme_heuristic(text: str) -> Optional[RandomizationScheme]:
    """Extract randomization scheme using pattern matching."""
    text_lower = text.lower()
    
    # Check if this is a randomized study
    if not any(kw in text_lower for kw in ['randomize', 'randomis', 'allocation']):
        return None
    
    ratio = _extract_ratio(text)
    method = _extract_method(text)
    algorithm_type = _classify_algorithm(text)
    block_size = _extract_block_size(text)
    block_sizes = _extract_block_sizes(text)
    factors = _extract_strat_factors_heuristic(text)
    central = any(kw in text_lower for kw in ['iwrs', 'ixrs', 'irt', 'interactive', 'central'])
    iwrs_system = _extract_iwrs_system(text)
    concealment = _extract_concealment(text)
    is_adaptive = 'adaptive randomization' in text_lower or 'response-adaptive' in text_lower
    
    return RandomizationScheme(
        id="randomization_1",
        ratio=ratio,
        method=method,
        algorithm_type=algorithm_type,
        block_size=block_size,
        block_sizes=block_sizes,
        stratification_factors=factors,
        central_randomization=central,
        iwrs_system=iwrs_system,
        concealment_method=concealment,
        is_adaptive=is_adaptive,
        source_text=text[:500],
    )


def _extract_ratio(text: str) -> str:
    """Extract allocation ratio from text."""
    match = RATIO_PATTERN.search(text)
    if match:
        if match.group(3):
            return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
        return f"{match.group(1)}:{match.group(2)}"
    
    text_lower = text.lower()
    if 'equal' in text_lower and 'allocation' in text_lower:
        return "1:1"
    if '2 to 1' in text_lower or '2-to-1' in text_lower:
        return "2:1"
    
    return "1:1"


def _extract_method(text: str) -> str:
    """Extract randomization method from text."""
    text_lower = text.lower()
    
    methods = []
    if 'stratif' in text_lower:
        methods.append("Stratified")
    if 'permuted' in text_lower:
        methods.append("permuted block")
    elif 'block' in text_lower:
        methods.append("block")
    if 'adaptive' in text_lower and 'response' in text_lower:
        methods.append("response-adaptive")
    elif 'adaptive' in text_lower:
        methods.append("adaptive")
    if 'minimization' in text_lower or 'minimisation' in text_lower:
        methods.append("minimization")
    if 'dynamic' in text_lower:
        methods.append("dynamic")
    if 'biased' in text_lower and 'coin' in text_lower:
        methods.append("biased-coin")
    
    if methods:
        return " ".join(methods) + " randomization"
    return "Simple randomization"


def _classify_algorithm(text: str) -> str:
    """Classify the randomization algorithm type."""
    text_lower = text.lower()
    if 'minimization' in text_lower or 'minimisation' in text_lower:
        return "minimization"
    if 'adaptive' in text_lower and ('response' in text_lower or 'bayesian' in text_lower):
        return "adaptive"
    if 'biased' in text_lower and 'coin' in text_lower:
        return "biased-coin"
    if 'block' in text_lower or 'permuted' in text_lower:
        return "block"
    if 'stratif' in text_lower:
        return "block"
    return "simple"


def _extract_block_size(text: str) -> Optional[int]:
    """Extract primary block size from text."""
    match = BLOCK_SIZE_PATTERN.search(text)
    if match:
        return int(match.group(1))
    if 'block of 4' in text.lower() or 'blocks of 4' in text.lower():
        return 4
    if 'block of 6' in text.lower() or 'blocks of 6' in text.lower():
        return 6
    return None


def _extract_block_sizes(text: str) -> List[int]:
    """Extract variable block sizes (e.g., 'block sizes of 4, 6, and 8')."""
    match = VARIABLE_BLOCK_PATTERN.search(text)
    if match:
        sizes = [int(g) for g in match.groups() if g]
        return sorted(set(sizes))
    return []


def _extract_iwrs_system(text: str) -> Optional[str]:
    """Extract IWRS/IXRS system name from text."""
    patterns = [
        r'(?:IWRS|IXRS|IRT|RTSM)\s*(?:system)?[:\s]*([A-Z][A-Za-z\s]+(?:IXRS|IWRS|RTSM|Rave|Argus|Medidata)?)',
        r'(?:via|using|through)\s+(?:the\s+)?([A-Z][A-Za-z\s]+(?:IWRS|IXRS|IRT|RTSM))',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            system = match.group(1).strip()
            if len(system) > 3 and len(system) < 80:
                return system
    # Just detect IWRS/IXRS mention
    text_lower = text.lower()
    if 'iwrs' in text_lower:
        return "IWRS"
    if 'ixrs' in text_lower:
        return "IXRS"
    if 'irt' in text_lower and 'interactive' in text_lower:
        return "IRT"
    return None


def _extract_concealment(text: str) -> Optional[str]:
    """Extract allocation concealment method from text."""
    text_lower = text.lower()
    if 'sealed envelope' in text_lower:
        return "Sealed envelopes"
    if 'central telephone' in text_lower:
        return "Central telephone"
    if any(kw in text_lower for kw in ['iwrs', 'ixrs', 'irt', 'interactive web']):
        return "Interactive response technology"
    if 'sequentially numbered' in text_lower:
        return "Sequentially numbered containers"
    return None


def _extract_strat_factors_heuristic(text: str) -> List[StratificationFactor]:
    """Extract stratification factor NAMES from text using regex (no hardcoded categories)."""
    factors = []
    text_lower = text.lower()
    factor_id = 1
    
    # Known factor name patterns to look for near stratification context
    FACTOR_PATTERNS = [
        "age", "sex", "gender", "race", "ethnicity", "region", "site", "country",
        "disease severity", "baseline", "prior therapy", "prior treatment",
        "HbA1c", "BMI", "weight", "renal function", "hepatic function",
        "ECOG", "performance status", "disease stage", "tumor type",
        "geographic region", "prior medication", "disease duration",
    ]
    
    # Look for explicit stratification section
    strat_match = re.search(
        r'stratif\w*\s+(?:by|factor|variable)[:\s]+([^.]+)',
        text_lower
    )
    
    search_text = strat_match.group(1) if strat_match else text_lower
    
    for factor_name in FACTOR_PATTERNS:
        # Factor must appear in stratification context
        if strat_match:
            if factor_name.lower() in search_text:
                factors.append(StratificationFactor(
                    id=f"strat_{factor_id}",
                    name=factor_name.title(),
                    categories=[],  # NO hardcoded defaults — categories come from LLM Pass 3
                    source_text=search_text[:200] if strat_match else None,
                ))
                factor_id += 1
        else:
            pattern = rf'stratif\w*[^.]*{re.escape(factor_name)}'
            if re.search(pattern, text_lower):
                factors.append(StratificationFactor(
                    id=f"strat_{factor_id}",
                    name=factor_name.title(),
                    categories=[],
                ))
                factor_id += 1
    
    return factors


# ─────────────────────────────────────────────────────────────
# Pass 2: LLM scheme identification
# ─────────────────────────────────────────────────────────────

PASS2_PROMPT = """Analyze this clinical protocol text and extract the complete randomization scheme.

You MUST extract all of the following if present in the text:
1. Allocation ratio (e.g., "1:1", "2:1", "1:1:1")
2. Randomization method — full description (e.g., "Stratified permuted block randomization")
3. Algorithm type — classify as one of: "block", "minimization", "adaptive", "biased-coin", "simple"
4. Block size(s) — single or variable (e.g., [4] or [4, 6])
5. Central randomization — true/false, and the system name (IWRS, IXRS, etc.)
6. Allocation concealment method
7. Whether this is an adaptive/response-adaptive design
8. Stratification factor NAMES (just names, not levels — levels come in the next pass)

Protocol text:
{text}

Return valid JSON only:
{{
    "ratio": "1:1",
    "method": "Stratified permuted block randomization",
    "algorithmType": "block",
    "blockSizes": [4, 6],
    "centralRandomization": true,
    "iwrsSystem": "IWRS",
    "concealmentMethod": "Interactive response technology",
    "isAdaptive": false,
    "stratificationFactorNames": ["Age", "Region", "Disease Severity"]
}}

If NOT a randomized study, return {{"ratio": null}}.
Return ONLY the JSON object, no explanation."""


def _pass2_scheme_identification(text: str, model: str) -> Optional[RandomizationScheme]:
    """Pass 2: LLM-based scheme identification with algorithm classification."""
    from core.llm_client import call_llm
    
    prompt = PASS2_PROMPT.format(text=text[:MAX_PROMPT_CHARS])
    
    try:
        result = call_llm(prompt, model_name=model, extractor_name="stratification_p2")
        response = result.get('response', '') if isinstance(result, dict) else str(result)
        
        if not response:
            return None
        
        data = _parse_json_response(response)
        if not data or not data.get('ratio'):
            return None
        
        # Build factors from names only (Pass 3 adds levels)
        factor_names = data.get('stratificationFactorNames') or data.get('stratificationFactors') or []
        factors = []
        for idx, name in enumerate(factor_names):
            if isinstance(name, dict):
                name = name.get('name', 'Unknown')
            factors.append(StratificationFactor(
                id=f"strat_llm_{idx+1}",
                name=str(name),
                categories=[],
            ))
        
        block_sizes = data.get('blockSizes', [])
        if isinstance(block_sizes, int):
            block_sizes = [block_sizes]
        
        return RandomizationScheme(
            id="randomization_llm_1",
            ratio=data.get('ratio', ''),
            method=data.get('method', ''),
            algorithm_type=data.get('algorithmType', 'block'),
            block_size=block_sizes[0] if block_sizes else data.get('blockSize'),
            block_sizes=block_sizes,
            stratification_factors=factors,
            central_randomization=data.get('centralRandomization', False),
            iwrs_system=data.get('iwrsSystem'),
            concealment_method=data.get('concealmentMethod'),
            is_adaptive=data.get('isAdaptive', False),
            adaptive_rules=data.get('adaptiveRules'),
        )
        
    except Exception as e:
        logger.error(f"Pass 2 (scheme identification) failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Pass 3: LLM detailed factor extraction
# ─────────────────────────────────────────────────────────────

PASS3_PROMPT = """Given these stratification factors from a clinical protocol: {factor_names}

Analyze the protocol text below and extract the EXACT levels/categories for each factor
as stated in the protocol. Do NOT invent or assume categories — only extract what is
explicitly written in the text.

For each factor, provide:
- name: The factor name
- levels: Array of exact level labels from the protocol text
- definitions: For each level, a brief definition if the protocol provides one
- dataSource: Where the factor value comes from (e.g., "screening assessment", "medical history")

Protocol text:
{text}

Return valid JSON only:
{{
    "factors": [
        {{
            "name": "Age",
            "levels": ["<65 years", ">=65 years"],
            "definitions": ["Participants younger than 65 years at screening", "Participants 65 years or older at screening"],
            "dataSource": "screening assessment"
        }},
        {{
            "name": "Region",
            "levels": ["North America", "Europe", "Rest of World"],
            "definitions": [],
            "dataSource": "site location"
        }}
    ]
}}

CRITICAL: Only include levels that are EXPLICITLY stated in the protocol text.
If levels are not specified for a factor, return an empty levels array.
Return ONLY the JSON object, no explanation."""


def _pass3_factor_details(
    text: str, factor_names: List[str], model: str
) -> Optional[List[StratificationFactor]]:
    """Pass 3: Extract detailed factor levels from protocol text."""
    from core.llm_client import call_llm
    
    if not factor_names:
        return None
    
    prompt = PASS3_PROMPT.format(
        factor_names=json.dumps(factor_names),
        text=text[:MAX_PROMPT_CHARS],
    )
    
    try:
        result = call_llm(prompt, model_name=model, extractor_name="stratification_p3")
        response = result.get('response', '') if isinstance(result, dict) else str(result)
        
        if not response:
            return None
        
        data = _parse_json_response(response)
        if not data:
            return None
        
        factors_raw = data.get('factors', [])
        if not factors_raw:
            return None
        
        factors = []
        for idx, f in enumerate(factors_raw):
            name = f.get('name', factor_names[idx] if idx < len(factor_names) else 'Unknown')
            levels_raw = f.get('levels', [])
            definitions = f.get('definitions', [])
            data_source = f.get('dataSource')
            
            # Build structured FactorLevel objects
            factor_levels = []
            for lidx, level_label in enumerate(levels_raw):
                definition = definitions[lidx] if lidx < len(definitions) else None
                factor_levels.append(FactorLevel(
                    id=f"fl_{idx+1}_{lidx+1}",
                    label=str(level_label),
                    definition=definition,
                ))
            
            # categories = bare strings for backward compat
            categories = [str(l) for l in levels_raw]
            
            factors.append(StratificationFactor(
                id=f"strat_{idx+1}",
                name=name,
                categories=categories,
                factor_levels=factor_levels,
                data_source=data_source,
            ))
        
        return factors
        
    except Exception as e:
        logger.error(f"Pass 3 (factor details) failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Merge logic
# ─────────────────────────────────────────────────────────────

def _merge_schemes(
    heuristic: Optional[RandomizationScheme],
    llm: Optional[RandomizationScheme]
) -> Optional[RandomizationScheme]:
    """Merge heuristic and LLM-extracted schemes. LLM wins on specifics."""
    if not heuristic and not llm:
        return None
    if not heuristic:
        return llm
    if not llm:
        return heuristic
    
    merged = RandomizationScheme(
        id=heuristic.id,
        ratio=llm.ratio if llm.ratio and llm.ratio != "1:1" else heuristic.ratio,
        method=llm.method if llm.method and llm.method != "Simple randomization" else heuristic.method,
        algorithm_type=llm.algorithm_type if llm.algorithm_type != "simple" else heuristic.algorithm_type,
        block_size=llm.block_size or heuristic.block_size,
        block_sizes=llm.block_sizes or heuristic.block_sizes,
        central_randomization=heuristic.central_randomization or llm.central_randomization,
        iwrs_system=llm.iwrs_system or heuristic.iwrs_system,
        concealment_method=llm.concealment_method or heuristic.concealment_method,
        seed_method=llm.seed_method or heuristic.seed_method,
        is_adaptive=llm.is_adaptive or heuristic.is_adaptive,
        adaptive_rules=llm.adaptive_rules or heuristic.adaptive_rules,
        blinding_schema_id=llm.blinding_schema_id or heuristic.blinding_schema_id,
        source_text=heuristic.source_text,
    )
    
    # Merge factors: LLM factors win, heuristic fills gaps
    factor_names = set()
    factors = []
    
    # LLM factors first (higher quality)
    for factor in llm.stratification_factors:
        if factor.name.lower() not in factor_names:
            factor_names.add(factor.name.lower())
            factors.append(factor)
    
    # Heuristic factors fill gaps
    for factor in heuristic.stratification_factors:
        if factor.name.lower() not in factor_names:
            factor_names.add(factor.name.lower())
            factors.append(factor)
    
    merged.stratification_factors = factors
    return merged


# ─────────────────────────────────────────────────────────────
# JSON parsing helper
# ─────────────────────────────────────────────────────────────

def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from an LLM response, handling markdown fences."""
    if not response:
        return None
    
    # Strip markdown code fences
    cleaned = response.strip()
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines)
    
    # Find JSON object
    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if not json_match:
        return None
    
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")
        return None
