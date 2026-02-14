"""
SoA Page Finder - Locate Schedule of Activities pages in protocol PDFs.

This module identifies which pages contain the SoA table(s) using:
1. Text-based heuristics (searching for "Schedule of Activities", table markers)
2. LLM-assisted page identification

Usage:
    from extraction.soa_finder import find_soa_pages
    
    pages = find_soa_pages(pdf_path, model_name="gemini-2.5-pro")
    print(f"SoA found on pages: {pages}")
"""

import os
import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


# Keywords that indicate SoA presence
SOA_KEYWORDS = [
    "schedule of activities",
    "schedule of assessments",
    "study schedule",
    "visit schedule",
    "study procedures",
    "time and events",
]

# Table structure indicators
TABLE_INDICATORS = [
    r'\bvisit\s*\d+',
    r'\bweek\s*[-+]?\d+',
    r'\bday\s*[-+]?\d+',
    r'\bscreening\b',
    r'\bbaseline\b',
    r'\bend\s*of\s*treatment',
    r'\bfollow[-\s]*up\b',
]


@dataclass
class PageScore:
    """Score for how likely a page contains SoA."""
    page_num: int
    keyword_score: float
    table_score: float
    total_score: float
    text_snippet: str


def find_soa_pages_heuristic(pdf_path: str, top_n: int = 5) -> List[int]:
    """
    Find SoA pages using text heuristics.
    
    Args:
        pdf_path: Path to PDF file
        top_n: Number of top-scoring pages to return
        
    Returns:
        List of 0-indexed page numbers likely containing SoA
    """
    doc = fitz.open(pdf_path)
    scores: List[PageScore] = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().lower()
        
        # Score keywords
        keyword_score = 0.0
        for kw in SOA_KEYWORDS:
            if kw in text:
                keyword_score += 2.0
        
        # Score table indicators
        table_score = 0.0
        for pattern in TABLE_INDICATORS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            table_score += len(matches) * 0.5
        
        # Bonus for having multiple column-like structures
        # (rough heuristic based on repeated patterns)
        visit_matches = re.findall(r'visit\s*\d+', text, re.IGNORECASE)
        if len(visit_matches) >= 3:
            table_score += 3.0
        
        # Wide-table heuristic: pages with many isolated integers on separate
        # lines (visit numbers/week numbers) AND epoch-like keywords are likely
        # SoA continuation pages even without explicit "visit N" tokens.
        lines = text.split('\n')
        isolated_ints = sum(1 for ln in lines if re.fullmatch(r'\s*[-+±]?\d{1,3}\s*', ln))
        has_epoch_kw = bool(re.search(r'treatment\s*period|study\s*period|screening|lead[- ]?in|follow[- ]?up|safety', text, re.IGNORECASE))
        has_x_ticks = text.count('x') >= 5 or text.count('X') >= 5
        if isolated_ints >= 15 and has_epoch_kw:
            table_score += 4.0
        if isolated_ints >= 15 and has_x_ticks:
            table_score += 3.0
        
        total_score = keyword_score + table_score
        
        if total_score > 0:
            # Get a snippet for debugging
            snippet_start = text.find("schedule")
            if snippet_start == -1:
                snippet_start = 0
            snippet = text[snippet_start:snippet_start+100].replace('\n', ' ')
            
            scores.append(PageScore(
                page_num=page_num,
                keyword_score=keyword_score,
                table_score=table_score,
                total_score=total_score,
                text_snippet=snippet,
            ))
    
    doc.close()
    
    # Sort by score descending
    scores.sort(key=lambda x: x.total_score, reverse=True)
    
    # Return top N pages
    return [s.page_num for s in scores[:top_n]]


def find_soa_pages_llm(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    candidate_pages: Optional[List[int]] = None,
) -> List[int]:
    """
    Find SoA pages using LLM analysis.
    
    Args:
        pdf_path: Path to PDF file
        model_name: LLM model to use
        candidate_pages: Optional list of candidate pages to evaluate
                        (if None, evaluates all pages)
        
    Returns:
        List of 0-indexed page numbers containing SoA
    """
    doc = fitz.open(pdf_path)
    
    # If no candidates provided, use heuristics to narrow down
    if candidate_pages is None:
        candidate_pages = find_soa_pages_heuristic(pdf_path, top_n=10)
        if not candidate_pages:
            candidate_pages = list(range(min(30, len(doc))))  # Check first 30 pages
    
    # Extract text from candidate pages
    page_texts = []
    for page_num in candidate_pages:
        if 0 <= page_num < len(doc):
            text = doc[page_num].get_text()[:2000]  # Limit text per page
            page_texts.append(f"PAGE {page_num}:\n{text}")
    
    doc.close()
    
    if not page_texts:
        return []
    
    # Build prompt
    prompt = """Analyze these protocol pages and identify which ones contain a Schedule of Activities (SoA) table.

An SoA table typically has:
- Column headers with visit names (Visit 1, Visit 2, etc.) or time points (Week 0, Day 1, etc.)
- Row headers with procedure/activity names
- Checkmarks or X marks indicating which activities occur at which visits

IMPORTANT: SoA tables often span MULTIPLE PAGES. Include:
- Pages with the "Schedule of Activities" title/header (even if the table starts on that page)
- Continuation pages that have table content but no title
- All pages that are part of the same table

PAGES TO ANALYZE:
{pages}

Return a JSON object with:
{{
  "soa_pages": [list of page numbers that contain SoA tables - include ALL pages of multi-page tables],
  "confidence": "high" or "medium" or "low",
  "notes": "brief explanation"
}}

Include any page that has SoA table content, even if it's a continuation page.""".format(
        pages="\n\n---\n\n".join(page_texts)
    )
    
    try:
        from extraction.llm_task_config import get_llm_task_config, to_llm_config
        task_config = get_llm_task_config("soa_finder", model=model_name)
        config = to_llm_config(task_config)
        
        client = get_llm_client(model_name)
        response = client.generate(
            messages=[{"role": "user", "content": prompt}],
            config=config,
        )
        
        data = parse_llm_json(response.content, fallback={})
        # Handle LLM returning list instead of dict (e.g., [{...}] instead of {...})
        if isinstance(data, list) and data and isinstance(data[0], dict):
            data = data[0]
        elif not isinstance(data, dict):
            data = {}
        pages = data.get("soa_pages", [])
        
        logger.info(f"LLM identified SoA on pages: {pages} (confidence: {data.get('confidence', 'unknown')})")
        
        return [int(p) for p in pages if isinstance(p, (int, float))]
        
    except Exception as e:
        logger.warning(f"LLM page finding failed: {e}. Falling back to heuristics.")
        return candidate_pages[:5]  # Return top 5 heuristic candidates


def find_soa_pages(
    pdf_path: str,
    model_name: Optional[str] = None,
    use_llm: bool = True,
) -> List[int]:
    """
    Find pages containing Schedule of Activities table.
    
    This is the main entry point for SoA page detection.
    
    Args:
        pdf_path: Path to protocol PDF
        model_name: LLM model for enhanced detection (optional)
        use_llm: Whether to use LLM-assisted detection
        
    Returns:
        List of 0-indexed page numbers containing SoA
        
    Example:
        >>> pages = find_soa_pages("protocol.pdf")
        >>> print(f"Found SoA on pages: {pages}")
    """
    logger.info(f"Finding SoA pages in: {pdf_path}")
    
    # First pass: heuristic detection
    heuristic_pages = find_soa_pages_heuristic(pdf_path, top_n=10)
    logger.info(f"Heuristic candidates: {heuristic_pages}")
    
    # Find pages with SoA title (these are anchor pages)
    title_pages = _find_soa_title_pages(pdf_path)
    logger.info(f"Title pages: {title_pages}")
    
    # Combine heuristic and title pages
    all_candidates = list(set(heuristic_pages + title_pages))
    
    if not use_llm or not model_name:
        final_pages = _expand_adjacent_pages(all_candidates, pdf_path)
        return sorted(final_pages)[:10]
    
    # Second pass: LLM refinement
    llm_pages = find_soa_pages_llm(pdf_path, model_name, all_candidates)
    
    if llm_pages:
        # Expand to include adjacent pages (tables often span pages)
        final_pages = _expand_adjacent_pages(llm_pages, pdf_path)
        if set(final_pages) != set(llm_pages):
            logger.info(f"Expanded pages from {sorted(llm_pages)} to {sorted(final_pages)} (adjacent page detection)")
        return sorted(final_pages)
    
    # Fallback to heuristics if LLM fails
    final_pages = _expand_adjacent_pages(all_candidates, pdf_path)
    return sorted(final_pages)[:10]


def _find_soa_title_pages(pdf_path: str) -> List[int]:
    """
    Find pages that contain actual SoA table (not just mentions of it).
    
    Looks for:
    - "Table X: Schedule of Activities" pattern (actual table title)
    - Combined presence of title AND table structure (column headers like Day, Visit)
    """
    doc = fitz.open(pdf_path)
    title_pages = []
    
    # Patterns for actual table titles (not TOC or references)
    # Requires "Table X:" format which indicates actual table caption
    table_title_patterns = [
        r'table\s+\d+[:\.]?\s*schedule\s+of\s+(activities|assessments)',  # "Table 1: Schedule of..."
    ]
    
    # Patterns for table structure (columns/headers)
    structure_patterns = [
        r'\bday\s*[-+]?\d+',
        r'\bweek\s*[-+]?\d+', 
        r'\bvisit\s*\d+',
        r'\bscreening\b.*\btreatment\b',  # Multiple epochs on same page
        r'\binpatient\b',
        r'\boutpatient\b',
    ]
    
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().lower()
        
        # Method 1: Explicit table title pattern
        for pattern in table_title_patterns:
            if re.search(pattern, text):
                title_pages.append(page_num)
                logger.debug(f"Page {page_num + 1}: Found table title pattern")
                break
        else:
            # Method 2: "Schedule of Activities" + significant table structure
            if re.search(r'schedule\s+of\s+(activities|assessments)', text):
                structure_count = sum(
                    1 for p in structure_patterns if re.search(p, text)
                )
                # Need both the title AND substantial table structure
                if structure_count >= 3:
                    title_pages.append(page_num)
                    logger.debug(f"Page {page_num + 1}: Found title + {structure_count} structure indicators")
    
    doc.close()
    return title_pages


def _extract_header_fingerprint(text: str) -> Optional[frozenset]:
    """
    Extract a fingerprint from the column-header region of a SoA page.
    
    Multi-page SoA tables repeat identical column headers (epoch names,
    visit numbers) on every page.  We normalise the first ~40 lines to
    a compact string so two pages can be compared cheaply.
    Returns None if the page doesn't look like a SoA table.
    """
    lines = text.split('\n')
    # Take the first 40 lines (header region)
    header_lines = [ln.strip().lower() for ln in lines[:40] if ln.strip()]
    if len(header_lines) < 5:
        return None
    # Fingerprint = frozenset of normalised header tokens.
    # Strip page numbers (e.g., "page 19") which differ across continuation pages.
    tokens = set()
    for ln in header_lines:
        if len(ln) < 30 and not re.fullmatch(r'page\s*\d+', ln):
            tokens.add(re.sub(r'\s+', ' ', ln))
    if len(tokens) < 8:
        return None
    return frozenset(tokens)


def _expand_adjacent_pages(pages: List[int], pdf_path: str) -> List[int]:
    """
    Expand page list to include adjacent pages and fill gaps.
    
    SoA tables often span multiple pages, so if we find page N,
    we should also check page N+1 (and potentially N-1) for table continuation.
    Also fills in any gaps between detected pages (e.g., if 13 and 15 are detected, include 14).
    
    Uses header-fingerprint matching to detect continuation pages that share
    the same column structure (epoch names, visit numbers) as known SoA pages.
    """
    if not pages:
        return pages
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    expanded = set(pages)
    
    # Step 1: Fill in gaps between detected pages
    if len(pages) >= 2:
        sorted_pages = sorted(pages)
        for i in range(len(sorted_pages) - 1):
            start, end = sorted_pages[i], sorted_pages[i + 1]
            if end - start <= 3:
                for gap_page in range(start + 1, end):
                    if gap_page not in expanded:
                        expanded.add(gap_page)
                        logger.info(f"Filled gap: added page {gap_page + 1} (1-indexed) between pages {start + 1} and {end + 1}")
    
    # Step 2: Header-fingerprint walk — scan backward/forward from known
    # SoA pages for continuation pages with matching column headers.
    # Multi-page SoA tables repeat identical headers on every page.
    ref_fps = []
    for pg in sorted(expanded):
        fp = _extract_header_fingerprint(doc[pg].get_text())
        if fp:
            ref_fps.append(fp)
    
    def _matches_any_ref(candidate_fp):
        """Jaccard similarity >= 0.75 against any reference fingerprint."""
        for ref in ref_fps:
            intersection = len(candidate_fp & ref)
            union = len(candidate_fp | ref)
            if union > 0 and intersection / union >= 0.75:
                return True
        return False
    
    if ref_fps:
        sorted_exp = sorted(expanded)
        # Walk backward from earliest known page
        for pg in range(sorted_exp[0] - 1, max(sorted_exp[0] - 8, -1), -1):
            if pg < 0:
                break
            fp = _extract_header_fingerprint(doc[pg].get_text())
            if fp and _matches_any_ref(fp):
                expanded.add(pg)
                logger.info(f"Header-match: added page {pg + 1} (1-indexed) before SoA")
            else:
                break  # Stop at first non-matching page
        # Walk forward from latest known page
        for pg in range(sorted_exp[-1] + 1, min(sorted_exp[-1] + 8, total_pages)):
            fp = _extract_header_fingerprint(doc[pg].get_text())
            if fp and _matches_any_ref(fp):
                expanded.add(pg)
                logger.info(f"Header-match: added page {pg + 1} (1-indexed) after SoA")
            else:
                break
        # Interior scan: fill gaps between known pages using fingerprint matching
        # (covers wide gaps > 3 that simple gap-fill misses)
        sorted_after_walk = sorted(expanded)
        if len(sorted_after_walk) >= 2:
            lo, hi = sorted_after_walk[0], sorted_after_walk[-1]
            for pg in range(lo + 1, hi):
                if pg not in expanded:
                    fp = _extract_header_fingerprint(doc[pg].get_text())
                    if fp and _matches_any_ref(fp):
                        expanded.add(pg)
                        logger.info(f"Header-match: filled interior page {pg + 1} (1-indexed)")
    
    # Step 3: Fallback ±1 (covers cases where fingerprint doesn't match)
    sorted_pages = sorted(expanded)
    min_page, max_page = sorted_pages[0], sorted_pages[-1]
    if min_page - 1 >= 0 and min_page - 1 not in expanded:
        expanded.add(min_page - 1)
    if max_page + 1 < total_pages and max_page + 1 not in expanded:
        expanded.add(max_page + 1)
    
    doc.close()
    return list(expanded)


def extract_soa_text(pdf_path: str, page_numbers: List[int]) -> str:
    """
    Extract text from specified SoA pages.
    
    Args:
        pdf_path: Path to PDF file
        page_numbers: List of 0-indexed page numbers
        
    Returns:
        Combined text from specified pages
    """
    doc = fitz.open(pdf_path)
    texts = []
    
    for page_num in page_numbers:
        if 0 <= page_num < len(doc):
            texts.append(doc[page_num].get_text())
    
    doc.close()
    return "\n\n---PAGE BREAK---\n\n".join(texts)


def extract_soa_images(
    pdf_path: str,
    page_numbers: List[int],
    output_dir: str,
    dpi: int = 150,
) -> List[str]:
    """
    Extract SoA pages as images.
    
    Args:
        pdf_path: Path to PDF file
        page_numbers: List of 0-indexed page numbers
        output_dir: Directory to save images
        dpi: Resolution for image extraction
        
    Returns:
        List of paths to extracted images
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths = []
    
    for page_num in page_numbers:
        if 0 <= page_num < len(doc):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            img_path = os.path.join(output_dir, f"soa_page_{page_num + 1:03d}.png")  # 1-indexed for human readability
            pix.save(img_path)
            image_paths.append(img_path)
            logger.debug(f"Saved page {page_num} to {img_path}")
    
    doc.close()
    return image_paths
