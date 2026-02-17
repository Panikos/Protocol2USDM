"""
Keyword-guided enrollment number extraction.

Scans PDF text for enrollment-related passages, then uses a focused LLM
call to extract the precise planned enrollment number from those passages.

This two-stage approach (keyword search → targeted LLM) is more reliable
than hoping the metadata or eligibility extractor sees the right pages.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1: Keyword search — find relevant pages and passages
# ---------------------------------------------------------------------------

# Patterns that signal enrollment / sample size text
_ENROLLMENT_KEYWORDS = re.compile(
    r'(?:'
    r'(?:approximately|about|up\s+to|total\s+of|planned|target|estimated|maximum\s+of)\s+\d[\d,]*\s+'
        r'(?:participants?|subjects?|patients?|individuals?)'
    r'|'
    r'\d[\d,]*\s+(?:participants?|subjects?|patients?)\s+'
        r'(?:will\s+be|are\s+planned|to\s+be|are\s+expected)\s+'
        r'(?:enrolled|randomized|recruited|screened)'
    r'|'
    r'(?:enroll(?:ment)?|randomiz(?:e|ation)|recruit(?:ment)?|sample\s+size)\s+'
        r'(?:of|is|:|will\s+be|was|target)\s*(?:approximately|about|up\s+to)?\s*\d[\d,]*'
    r'|'
    r'(?:N\s*=\s*\d[\d,]*)'
    r'|'
    r'(?:number\s+of\s+(?:participants?|subjects?|patients?))\s*(?::|is|will\s+be)\s*(?:approximately|about)?\s*\d[\d,]*'
    r')',
    re.IGNORECASE,
)

# TOC indicators to skip
_TOC_PATTERN = re.compile(
    r'(?:table\s+of\s+contents|\.{5,}|page\s+\d+\s+of\s+\d+.*page\s+\d+\s+of\s+\d+)',
    re.IGNORECASE,
)


def find_enrollment_passages(
    pdf_path: str,
    max_pages: int = 0,
) -> List[Tuple[int, str]]:
    """
    Scan a PDF for pages containing enrollment-related text.

    Args:
        pdf_path: Path to any PDF (protocol or SAP).
        max_pages: Max pages to scan (0 = all pages).

    Returns:
        List of (page_number_0indexed, passage_text) tuples, where
        passage_text is a ±300-char window around each match on that page.
        Pages are deduplicated; passages from the same page are merged.
    """
    import fitz

    results: List[Tuple[int, str]] = []

    try:
        doc = fitz.open(pdf_path)
        total = len(doc) if max_pages <= 0 else min(len(doc), max_pages)

        for page_num in range(total):
            text = doc[page_num].get_text()
            if not text or len(text) < 20:
                continue

            # Skip TOC pages
            if _TOC_PATTERN.search(text):
                continue

            matches = list(_ENROLLMENT_KEYWORDS.finditer(text))
            if not matches:
                continue

            # Build merged passage from all match windows on this page
            snippets = []
            for m in matches:
                start = max(0, m.start() - 300)
                end = min(len(text), m.end() + 300)
                snippets.append(text[start:end].strip())

            passage = "\n...\n".join(snippets)
            results.append((page_num, passage))
            logger.debug(
                f"Enrollment keywords on page {page_num + 1}: "
                f"{len(matches)} match(es)"
            )

        doc.close()
    except Exception as e:
        logger.warning(f"Error scanning PDF for enrollment keywords: {e}")

    logger.info(
        f"Found enrollment-related passages on {len(results)} page(s) "
        f"in {pdf_path}"
    )
    return results


# ---------------------------------------------------------------------------
# Stage 2: Focused LLM extraction from the identified passages
# ---------------------------------------------------------------------------

_ENROLLMENT_EXTRACTION_PROMPT = """Extract the planned enrollment number from these clinical trial passages.

Look for:
- Total number of participants/subjects/patients to be enrolled
- Sample size targets
- Randomization targets (e.g., "randomize 200 participants")
- Screening targets

Return ONLY a JSON object:
```json
{
  "plannedEnrollmentNumber": <integer or null>,
  "confidence": <float 0-1>,
  "sourceText": "<the exact phrase you found, max 100 chars>"
}
```

If multiple numbers are mentioned, prefer:
1. Total planned enrollment over per-arm numbers
2. Randomization target over screening target
3. The number that appears most prominently or repeatedly

If no enrollment number can be determined, return null for plannedEnrollmentNumber.

PASSAGES:
"""


def extract_enrollment_from_passages(
    passages: List[Tuple[int, str]],
    model: str = None,
) -> Optional[int]:
    """
    Use a focused LLM call to extract the enrollment number from passages.

    Args:
        passages: Output of find_enrollment_passages().
        model: LLM model (None = pipeline default from constants.py).

    Returns:
        The planned enrollment number, or None if not found.
    """
    if not passages:
        return None

    from core.llm_client import call_llm
    import json

    # Build context from passages
    context_parts = []
    for page_num, text in passages:
        context_parts.append(f"[Page {page_num + 1}]\n{text}")

    context = "\n\n---\n\n".join(context_parts)
    # Cap context to avoid excessive token use
    if len(context) > 8000:
        context = context[:8000] + "\n... (truncated)"

    prompt = _ENROLLMENT_EXTRACTION_PROMPT + context

    try:
        response = call_llm(
            prompt=prompt,
            model_name=model,
            max_tokens=256,
            extractor_name="enrollment_finder",
        )

        if not response or 'response' not in response:
            return None

        resp_text = response['response'].strip()
        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*?\}', resp_text)
        if json_match:
            data = json.loads(json_match.group(0))
            number = data.get('plannedEnrollmentNumber')
            confidence = data.get('confidence', 0)
            source = data.get('sourceText', '')

            if number and isinstance(number, (int, float)) and number > 0:
                logger.info(
                    f"  ✓ Enrollment finder: N={int(number)} "
                    f"(confidence={confidence:.2f}, source='{source[:60]}')"
                )
                return int(number)

    except Exception as e:
        logger.warning(f"Enrollment LLM extraction failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Convenience: single-call API for pipeline use
# ---------------------------------------------------------------------------

def find_planned_enrollment(
    pdf_path: str,
    model: str = None,
    max_pages: int = 0,
) -> Optional[int]:
    """
    End-to-end: keyword-scan a PDF then LLM-extract the enrollment number.

    Args:
        pdf_path: Path to protocol or SAP PDF.
        model: LLM model (None = pipeline default from constants.py).
        max_pages: Max pages to scan (0 = all).

    Returns:
        Planned enrollment number, or None.
    """
    passages = find_enrollment_passages(pdf_path, max_pages=max_pages)
    if not passages:
        logger.info("  No enrollment-related passages found in PDF")
        return None
    return extract_enrollment_from_passages(passages, model=model)
