"""
Stratification Extractor

Extracts randomization schemes and stratification factors from clinical protocol PDFs.
Critical for generating realistic subject allocation patterns.

Phase 4 Component.
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

import fitz  # PyMuPDF

from .schema import (
    ExecutionModelResult,
    ExecutionModelData,
    StratificationFactor,
    RandomizationScheme,
)

logger = logging.getLogger(__name__)


# Keywords for finding randomization sections
RANDOMIZATION_KEYWORDS = [
    "randomization", "randomized", "allocation", "assigned", "stratified",
    "stratification", "blocking", "block size", "treatment assignment",
    "IWRS", "IXRS", "IRT", "interactive", "central randomization",
    "randomization ratio", "allocation ratio", "1:1", "2:1", "1:1:1",
]

# Common stratification factors
COMMON_STRAT_FACTORS = [
    "age", "sex", "gender", "race", "ethnicity", "region", "site", "country",
    "disease severity", "baseline", "prior therapy", "prior treatment",
    "HbA1c", "BMI", "weight", "renal function", "hepatic function",
    "ECOG", "performance status", "disease stage", "tumor type",
]

# Ratio patterns
RATIO_PATTERN = re.compile(r'(\d+)\s*:\s*(\d+)(?:\s*:\s*(\d+))?')

# Block size patterns
BLOCK_SIZE_PATTERN = re.compile(r'block\s*(?:size)?[:\s]+(\d+)', re.IGNORECASE)


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
        
        return pages[:20]  # Limit to 20 pages
        
    except Exception as e:
        logger.warning(f"Error finding randomization pages: {e}")
        return []


def extract_stratification(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
) -> ExecutionModelResult:
    """
    Extract randomization scheme and stratification factors from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model: LLM model to use for enhancement
        use_llm: Whether to use LLM for extraction
        
    Returns:
        ExecutionModelResult with randomization scheme
    """
    logger.info("=" * 60)
    logger.info("PHASE 4C: Stratification/Randomization Extraction")
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
    
    # Heuristic extraction
    scheme = _extract_scheme_heuristic(text)
    if scheme:
        logger.info(f"Heuristic extraction found randomization: {scheme.ratio}, {len(scheme.stratification_factors)} factors")
    
    # LLM enhancement
    if use_llm and len(text) > 100:
        try:
            llm_scheme = _extract_scheme_llm(text, model)
            if llm_scheme:
                scheme = _merge_schemes(scheme, llm_scheme)
                logger.info(f"After LLM enhancement: {scheme.ratio}, {len(scheme.stratification_factors)} factors")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
    
    if scheme:
        logger.info(f"Extracted randomization scheme: {scheme.ratio} ratio, {len(scheme.stratification_factors)} stratification factors")
    else:
        logger.info("No randomization scheme detected")
    
    return ExecutionModelResult(
        success=scheme is not None,
        data=ExecutionModelData(randomization_scheme=scheme) if scheme else ExecutionModelData(),
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


def _extract_scheme_heuristic(text: str) -> Optional[RandomizationScheme]:
    """Extract randomization scheme using pattern matching."""
    text_lower = text.lower()
    
    # Check if this is a randomized study
    if not any(kw in text_lower for kw in ['randomize', 'randomis', 'allocation']):
        return None
    
    # Extract ratio
    ratio = _extract_ratio(text)
    
    # Extract method
    method = _extract_method(text)
    
    # Extract block size
    block_size = _extract_block_size(text)
    
    # Extract stratification factors
    factors = _extract_strat_factors(text)
    
    # Check for central randomization
    central = any(kw in text_lower for kw in ['iwrs', 'ixrs', 'irt', 'interactive', 'central'])
    
    return RandomizationScheme(
        id="randomization_1",
        ratio=ratio,
        method=method,
        block_size=block_size,
        stratification_factors=factors,
        central_randomization=central,
        source_text=text[:500],
    )


def _extract_ratio(text: str) -> str:
    """Extract allocation ratio from text."""
    # Look for explicit ratio patterns
    match = RATIO_PATTERN.search(text)
    if match:
        if match.group(3):
            return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
        return f"{match.group(1)}:{match.group(2)}"
    
    # Check for common ratio descriptions
    text_lower = text.lower()
    if 'equal' in text_lower and 'allocation' in text_lower:
        return "1:1"
    if '2 to 1' in text_lower or '2-to-1' in text_lower:
        return "2:1"
    
    return "1:1"  # Default


def _extract_method(text: str) -> str:
    """Extract randomization method from text."""
    text_lower = text.lower()
    
    methods = []
    if 'stratif' in text_lower:
        methods.append("Stratified")
    if 'block' in text_lower:
        methods.append("block")
    if 'permuted' in text_lower:
        methods.append("permuted block")
    if 'adaptive' in text_lower:
        methods.append("adaptive")
    if 'minimization' in text_lower:
        methods.append("minimization")
    if 'dynamic' in text_lower:
        methods.append("dynamic")
    
    if methods:
        return " ".join(methods) + " randomization"
    return "Simple randomization"


def _extract_block_size(text: str) -> Optional[int]:
    """Extract block size from text."""
    match = BLOCK_SIZE_PATTERN.search(text)
    if match:
        return int(match.group(1))
    
    # Look for common block sizes mentioned
    if 'block of 4' in text.lower() or 'blocks of 4' in text.lower():
        return 4
    if 'block of 6' in text.lower() or 'blocks of 6' in text.lower():
        return 6
    
    return None


def _extract_strat_factors(text: str) -> List[StratificationFactor]:
    """Extract stratification factors from text."""
    factors = []
    text_lower = text.lower()
    factor_id = 1
    
    # Look for explicit stratification section
    strat_match = re.search(
        r'stratif\w*\s+(?:by|factor|variable)[:\s]+([^.]+)',
        text_lower
    )
    
    if strat_match:
        strat_text = strat_match.group(1)
        # Parse factors from the match
        for factor_name in COMMON_STRAT_FACTORS:
            if factor_name in strat_text:
                categories = _get_factor_categories(factor_name, text)
                factors.append(StratificationFactor(
                    id=f"strat_{factor_id}",
                    name=factor_name.title(),
                    categories=categories,
                    source_text=strat_text[:200],
                ))
                factor_id += 1
    else:
        # Look for common factors mentioned near "stratif"
        for i, factor_name in enumerate(COMMON_STRAT_FACTORS):
            # Check if factor appears near stratification context
            pattern = rf'stratif\w*[^.]*{factor_name}'
            if re.search(pattern, text_lower):
                categories = _get_factor_categories(factor_name, text)
                factors.append(StratificationFactor(
                    id=f"strat_{factor_id}",
                    name=factor_name.title(),
                    categories=categories,
                ))
                factor_id += 1
    
    return factors


def _get_factor_categories(factor_name: str, text: str) -> List[str]:
    """Get categories/levels for a stratification factor."""
    text_lower = text.lower()
    
    # Common categories by factor type
    if factor_name in ['sex', 'gender']:
        return ['Male', 'Female']
    if factor_name == 'age':
        # Look for age cutoffs
        age_match = re.search(r'(\d+)\s*(?:years?|y\.?o\.?)', text_lower)
        if age_match:
            cutoff = age_match.group(1)
            return [f'<{cutoff} years', f'≥{cutoff} years']
        return ['<65 years', '≥65 years']
    if factor_name == 'region':
        return ['North America', 'Europe', 'Asia', 'Rest of World']
    if factor_name in ['disease severity', 'ecog', 'performance status']:
        return ['Mild', 'Moderate', 'Severe']
    if factor_name == 'prior therapy':
        return ['Yes', 'No']
    
    # Default binary categories
    return ['Category 1', 'Category 2']


def _extract_scheme_llm(text: str, model: str) -> Optional[RandomizationScheme]:
    """Extract randomization scheme using LLM."""
    from core.llm_client import call_llm
    import json
    
    prompt = f"""Analyze this clinical protocol text and extract the randomization scheme.

Identify:
1. Allocation ratio (e.g., "1:1", "2:1", "1:1:1")
2. Randomization method (e.g., "Stratified block randomization")
3. Block size (if specified)
4. Whether using central/interactive randomization (IWRS/IXRS)
5. Stratification factors with their categories/levels

Text to analyze:
{text[:8000]}

Return JSON format:
{{
    "ratio": "1:1",
    "method": "Stratified block randomization",
    "blockSize": 4,
    "centralRandomization": true,
    "stratificationFactors": [
        {{
            "name": "Age",
            "categories": ["<65 years", "≥65 years"]
        }},
        {{
            "name": "Prior Therapy",
            "categories": ["Yes", "No"]
        }}
    ]
}}

Return valid JSON only. If not a randomized study, return {{"ratio": null}}."""

    try:
        response = call_llm(prompt, model_name=model)
        
        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        
        if not data.get('ratio'):
            return None
        
        # Parse stratification factors
        factors = []
        for idx, item in enumerate(data.get('stratificationFactors', [])):
            factors.append(StratificationFactor(
                id=f"strat_llm_{idx+1}",
                name=item.get('name', 'Unknown'),
                categories=item.get('categories', []),
            ))
        
        return RandomizationScheme(
            id="randomization_llm_1",
            ratio=data.get('ratio', '1:1'),
            method=data.get('method', 'Simple randomization'),
            block_size=data.get('blockSize'),
            stratification_factors=factors,
            central_randomization=data.get('centralRandomization', False),
        )
        
    except Exception as e:
        logger.error(f"LLM stratification extraction failed: {e}")
        return None


def _merge_schemes(
    heuristic: Optional[RandomizationScheme],
    llm: Optional[RandomizationScheme]
) -> Optional[RandomizationScheme]:
    """Merge heuristic and LLM-extracted schemes."""
    if not heuristic and not llm:
        return None
    if not heuristic:
        return llm
    if not llm:
        return heuristic
    
    # Prefer LLM details but use heuristic as base
    merged = RandomizationScheme(
        id=heuristic.id,
        ratio=llm.ratio if llm.ratio != "1:1" else heuristic.ratio,
        method=llm.method if llm.method != "Simple randomization" else heuristic.method,
        block_size=llm.block_size or heuristic.block_size,
        central_randomization=heuristic.central_randomization or llm.central_randomization,
        source_text=heuristic.source_text,
    )
    
    # Merge stratification factors
    factor_names = set()
    factors = []
    
    for factor in heuristic.stratification_factors + llm.stratification_factors:
        if factor.name.lower() not in factor_names:
            factor_names.add(factor.name.lower())
            factors.append(factor)
    
    merged.stratification_factors = factors
    
    return merged
