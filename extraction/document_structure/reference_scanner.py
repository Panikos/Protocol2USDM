"""
Deterministic cross-reference and figure/table scanners.

These run without LLM calls — pure regex/heuristic scanning of
narrative text and PDF pages to extract:
  1. Inline cross-references (see Section X, Table Y, Figure Z)
  2. Figure/table/diagram catalog from the PDF
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.usdm_types import generate_uuid
from .schema import (
    FigureContentType,
    InlineCrossReference,
    ProtocolFigure,
    ReferenceType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Part A: Inline cross-reference scanner
# ---------------------------------------------------------------------------

# Patterns that introduce a cross-reference
_XREF_PATTERNS = [
    # "see Section 5.2", "refer to Section 5.2.1", "described in Section 5"
    (
        re.compile(
            r'(?:see|refer\s+to|described\s+in|detailed\s+in|outlined\s+in|'
            r'defined\s+in|specified\s+in|provided\s+in|per|as\s+per|'
            r'according\s+to|in\s+accordance\s+with)\s+'
            r'Section\s+(\d+(?:\.\d+)*)',
            re.IGNORECASE,
        ),
        ReferenceType.SECTION,
        'Section',
    ),
    # Bare "Section 5.2" (without a verb prefix)
    (
        re.compile(r'\bSection\s+(\d+(?:\.\d+)*)', re.IGNORECASE),
        ReferenceType.SECTION,
        'Section',
    ),
    # "Table 3-1", "Table 1", "Table 10.2"
    (
        re.compile(r'\bTable\s+(\d+(?:[-–.]\d+)*)', re.IGNORECASE),
        ReferenceType.TABLE,
        'Table',
    ),
    # "Figure 1", "Figure 4-1", "Figure 10.1"
    (
        re.compile(r'\bFigure\s+(\d+(?:[-–.]\d+)*)', re.IGNORECASE),
        ReferenceType.FIGURE,
        'Figure',
    ),
    # "Appendix 10.2", "Appendix A", "Appendix 1"
    (
        re.compile(r'\bAppendix\s+([A-Z0-9]+(?:\.\d+)*)', re.IGNORECASE),
        ReferenceType.APPENDIX,
        'Appendix',
    ),
    # "Listing 1", "Listing 14.1"
    (
        re.compile(r'\bListing\s+(\d+(?:\.\d+)*)', re.IGNORECASE),
        ReferenceType.LISTING,
        'Listing',
    ),
]

# Max characters of context to capture around the reference
_CONTEXT_WINDOW = 200

# Regex to strip inline page markers injected by the narrative extractor
_PAGE_MARKER_RE = re.compile(r'---\s*Page\s+\d+\s*---')


def _extract_context(text: str, match_start: int, match_end: int) -> str:
    """Extract the full sentence around the match for display context."""
    # Expand backwards to sentence start (look for period, newline, etc.)
    ctx_start = max(0, match_start - _CONTEXT_WINDOW // 2)
    for i in range(match_start - 1, ctx_start - 1, -1):
        if i >= 0 and text[i] in '.!?\n':
            ctx_start = i + 1
            break
    # Expand forwards to sentence end
    ctx_end = min(len(text), match_end + _CONTEXT_WINDOW // 2)
    for i in range(match_end, ctx_end):
        if text[i] in '.!?\n':
            ctx_end = i + 1
            break
    fragment = text[ctx_start:ctx_end].strip()
    # Remove page markers and collapse whitespace
    fragment = _PAGE_MARKER_RE.sub('', fragment)
    fragment = re.sub(r'\s+', ' ', fragment).strip()
    return fragment


def scan_inline_references(
    narrative_contents: List[Dict],
) -> List[InlineCrossReference]:
    """Scan narrative content dicts for inline cross-reference patterns.

    Args:
        narrative_contents: List of NarrativeContent dicts with
            'sectionNumber' and 'text' fields.

    Returns:
        Deduplicated list of InlineCrossReference objects.
    """
    refs: List[InlineCrossReference] = []
    seen: set = set()  # (source_section, target_label) dedup key

    for nc in narrative_contents:
        if not isinstance(nc, dict):
            continue
        source_section = nc.get('sectionNumber', '')
        text = nc.get('text', '')
        if not text or not source_section:
            continue

        for pattern, ref_type, prefix in _XREF_PATTERNS:
            for m in pattern.finditer(text):
                target_num = m.group(1)
                target_label = f"{prefix} {target_num}"

                dedup_key = (source_section, target_label)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Skip self-references
                if ref_type == ReferenceType.SECTION and target_num == source_section:
                    continue

                context = _extract_context(text, m.start(), m.end())

                # Resolve target section number for section refs
                target_section = None
                if ref_type == ReferenceType.SECTION:
                    target_section = target_num
                elif ref_type == ReferenceType.APPENDIX:
                    # Appendix numbers often map to sections 12+
                    if target_num.isdigit():
                        target_section = target_num

                refs.append(InlineCrossReference(
                    id=generate_uuid(),
                    source_section=source_section,
                    target_label=target_label,
                    target_section=target_section,
                    reference_type=ref_type,
                    context_text=context,
                ))

    logger.info(f"  ✓ Scanned inline references: {len(refs)} found "
                f"across {len(narrative_contents)} narrative sections")
    return refs


# ---------------------------------------------------------------------------
# Part B: Figure/table/image page scanner
# ---------------------------------------------------------------------------

# Patterns to detect figure/table labels on PDF pages
_FIGURE_LABEL_PATTERNS = [
    # "Figure 1:", "Figure 1.", "Figure 1 —", "Figure 1 Study Schema"
    (
        re.compile(
            r'^[ \t]*(?:Figure|Fig\.?)\s+(\d+(?:[-–.]\d+)*)\s*[:.—–\-]?\s*(.*)',
            re.IGNORECASE | re.MULTILINE,
        ),
        FigureContentType.FIGURE,
    ),
    # "Table 3-1:", "Table 1 Summary of..."
    (
        re.compile(
            r'^[ \t]*Table\s+(\d+(?:[-–.]\d+)*)\s*[:.—–\-]?\s*(.*)',
            re.IGNORECASE | re.MULTILINE,
        ),
        FigureContentType.TABLE,
    ),
    # "Diagram 1:", "Flowchart 1:"
    (
        re.compile(
            r'^[ \t]*(?:Diagram|Flowchart|Flow\s+Chart)\s+(\d+(?:[-–.]\d+)*)\s*[:.—–\-]?\s*(.*)',
            re.IGNORECASE | re.MULTILINE,
        ),
        FigureContentType.DIAGRAM,
    ),
]

# Additional heuristics for study schema (often unlabeled)
_SCHEMA_KEYWORDS = re.compile(
    r'study\s+schema|study\s+design\s+(?:diagram|schematic|overview)|'
    r'trial\s+schema|trial\s+design\s+(?:diagram|schematic)',
    re.IGNORECASE,
)

# Dotted-leader pattern (TOC lines like "Schedule of Activities ............ 14")
_DOTTED_LEADER_RE = re.compile(r'\.{3,}\s*\d+\s*$')


def _is_toc_page(page_text: str) -> bool:
    """Detect if a page is a Table of Contents page.

    Heuristic: a TOC page has many dotted-leader lines ("Title ..... 14")
    or an explicit TOC heading.
    """
    lines = page_text.strip().split('\n')
    if not lines:
        return False
    # Explicit heading check
    for line in lines[:5]:
        if re.search(r'table\s+of\s+contents|list\s+of\s+tables|list\s+of\s+figures',
                     line, re.IGNORECASE):
            return True
    # Count dotted-leader lines
    dot_lines = sum(1 for l in lines if _DOTTED_LEADER_RE.search(l))
    return dot_lines >= 4


def _clean_title(title: str) -> str:
    """Strip TOC artifacts (dotted leaders + page numbers) from a title."""
    # Remove ".............. 14" patterns
    title = _DOTTED_LEADER_RE.sub('', title)
    # Remove trailing dots
    title = re.sub(r'\.{2,}\s*$', '', title)
    # Collapse whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def scan_pdf_for_figures(
    pdf_path: str,
    max_pages: Optional[int] = None,
) -> List[ProtocolFigure]:
    """Scan every page of the PDF for figure/table/diagram labels.

    Args:
        pdf_path: Path to the protocol PDF.
        max_pages: Maximum number of pages to scan (None = all).

    Returns:
        List of ProtocolFigure objects with page numbers and labels.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not available — skipping figure scan")
        return []

    figures: List[ProtocolFigure] = []
    seen_labels: set = set()

    try:
        doc = fitz.open(pdf_path)
        total = len(doc) if max_pages is None else min(len(doc), max_pages)

        # First pass: collect candidates, preferring non-TOC pages
        # key = label, value = (ProtocolFigure, is_toc_page)
        candidates: Dict[str, Tuple[ProtocolFigure, bool]] = {}

        for page_num in range(total):
            page = doc[page_num]
            text = page.get_text()
            if not text:
                continue

            toc_page = _is_toc_page(text)

            for pattern, content_type in _FIGURE_LABEL_PATTERNS:
                for m in pattern.finditer(text):
                    label_num = m.group(1)
                    title_text = m.group(2).strip()
                    # Clean trailing whitespace/newlines from title
                    title_text = re.sub(r'\s+', ' ', title_text)[:200]
                    title_text = _clean_title(title_text)

                    if content_type == FigureContentType.TABLE:
                        label = f"Table {label_num}"
                    elif content_type == FigureContentType.DIAGRAM:
                        label = f"Diagram {label_num}"
                    else:
                        label = f"Figure {label_num}"

                    fig = ProtocolFigure(
                        id=generate_uuid(),
                        label=label,
                        title=title_text if title_text else None,
                        page_number=page_num,
                        content_type=content_type,
                    )

                    if label not in candidates:
                        # First occurrence
                        candidates[label] = (fig, toc_page)
                    elif candidates[label][1] and not toc_page:
                        # Replace TOC entry with actual content page entry
                        candidates[label] = (fig, toc_page)
                    # else: keep the existing (non-TOC or first-seen) entry

            # Check for study schema (often on a page near §1 or §4)
            if _SCHEMA_KEYWORDS.search(text) and 'study_schema' not in candidates:
                if not toc_page:
                    # Only tag it if there's a visual element (images or drawings)
                    image_list = page.get_images(full=True)
                    drawings = page.get_drawings()
                    if image_list or len(drawings) > 5:
                        candidates['study_schema'] = (ProtocolFigure(
                            id=generate_uuid(),
                            label="Study Schema",
                            title="Study Design Schema",
                            page_number=page_num,
                            content_type=FigureContentType.DIAGRAM,
                        ), False)

        # Build final list — also clean up any remaining TOC-only entries
        for label, (fig, was_toc) in candidates.items():
            if was_toc and fig.title:
                fig.title = _clean_title(fig.title)
            # Drop entries whose title is now empty after cleaning (pure TOC artifacts)
            # but keep entries that have a real label (Table 1, Figure 1, etc.)
            figures.append(fig)

        doc.close()

    except Exception as e:
        logger.error(f"Error scanning PDF for figures: {e}")

    logger.info(f"  ✓ Scanned PDF for figures/tables: {len(figures)} found")
    return figures


def _find_figure_region(
    page,
    fig_label: str,
    content_type: FigureContentType,
) -> Optional[Tuple[Optional[int], Optional[tuple]]]:
    """Detect the actual figure region on a PDF page.

    Returns:
        Tuple of (best_image_xref, clip_rect) where:
        - best_image_xref: xref of largest embedded image on page (or None)
        - clip_rect: (x0, y0, x1, y1) bounding box of the figure region (or None)
        At least one will be non-None if a figure region was found.
    """
    import fitz

    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height

    # --- Strategy 1: Find the largest embedded image on the page ---
    images = page.get_images(full=True)
    best_xref = None
    best_area = 0

    # Filter to images with meaningful size (>5% of page area)
    min_area = page_width * page_height * 0.05
    for img_info in images:
        xref = img_info[0]
        img_w = img_info[2]
        img_h = img_info[3]
        area = img_w * img_h
        if area > best_area and area > min_area:
            best_area = area
            best_xref = xref

    # If we found a large embedded image, prefer direct extraction
    if best_xref and best_area > page_width * page_height * 0.10:
        return (best_xref, None)

    # --- Strategy 2: Find the label position and crop below it ---
    # Search for the figure label text on the page
    label_instances = page.search_for(fig_label)
    if not label_instances:
        # Try shorter match (e.g., "Figure 1" without title)
        short_label = fig_label.split(':')[0].split('—')[0].strip()
        label_instances = page.search_for(short_label)

    if label_instances:
        # Use the first match as the label position
        label_rect = label_instances[0]
        # The figure content is typically below the label
        # Crop from slightly above the label to the bottom margin area
        # (leave ~8% margin at bottom for page numbers/footers)
        y_top = max(0, label_rect.y0 - 10)
        y_bottom = page_height * 0.92

        # If there are drawings/images below the label, use their extent
        drawings = page.get_drawings()
        img_rects = []
        for img_info in images:
            try:
                rects = page.get_image_rects(img_info[0])
                img_rects.extend(rects)
            except Exception:
                pass

        # Combine all visual elements below the label
        visual_bottom = label_rect.y1 + 20  # At minimum, some space below label
        for d in drawings:
            d_rect = d.get("rect") if isinstance(d, dict) else getattr(d, 'rect', None)
            if d_rect and d_rect.y0 > label_rect.y0:
                visual_bottom = max(visual_bottom, d_rect.y1)
        for ir in img_rects:
            if ir.y0 > label_rect.y0:
                visual_bottom = max(visual_bottom, ir.y1)

        # If visual content was found, use it; otherwise use page bottom margin
        if visual_bottom > label_rect.y1 + 50:
            y_bottom = min(visual_bottom + 15, page_height * 0.95)

        # Ensure minimum height (at least 20% of page)
        if (y_bottom - y_top) < page_height * 0.20:
            y_bottom = min(y_top + page_height * 0.5, page_height * 0.95)

        clip = (0, y_top, page_width, y_bottom)
        return (best_xref, clip)

    # --- Strategy 3: No label found — use largest image if any ---
    if best_xref:
        return (best_xref, None)

    return None


# Minimum image dimensions (pixels) to consider an extracted image valid
_MIN_IMAGE_WIDTH = 150
_MIN_IMAGE_HEIGHT = 100


def render_figure_images(
    pdf_path: str,
    figures: List[ProtocolFigure],
    output_dir: str,
    dpi: int = 200,
) -> List[ProtocolFigure]:
    """Extract or render figure images from the protocol PDF.

    Uses a three-strategy approach:
    1. Extract the largest embedded image from the figure's page (best quality)
    2. Crop the page to the detected figure region below the label
    3. Fall back to rendering the full page (worst case)

    Args:
        pdf_path: Path to the protocol PDF.
        figures: List of ProtocolFigure objects (must have page_number).
        output_dir: Directory to write images to.
        dpi: Rendering resolution.

    Returns:
        The same figures list, with image_path populated.
    """
    from core.pdf_utils import (
        extract_embedded_image,
        render_page_region_to_image,
        render_page_to_image,
    )

    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not available — skipping figure rendering")
        return figures

    fig_dir = Path(output_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    strategy_counts = {"embedded": 0, "cropped": 0, "fullpage": 0}

    try:
        doc = fitz.open(pdf_path)

        for fig in figures:
            if fig.page_number is None:
                continue
            if fig.page_number >= len(doc):
                continue

            page = doc[fig.page_number]
            safe_label = re.sub(r'[^\w\-]', '_', fig.label.lower()).strip('_')
            img_filename = f"{safe_label}_p{fig.page_number:03d}.png"
            img_path = str(fig_dir / img_filename)
            result_path = None

            # Try smart extraction
            region = _find_figure_region(page, fig.label, fig.content_type)

            if region:
                best_xref, clip_rect = region

                # Strategy 1: Extract embedded image directly
                if best_xref:
                    try:
                        img_data = doc.extract_image(best_xref)
                        if (img_data and img_data.get("image") and
                                img_data.get("width", 0) >= _MIN_IMAGE_WIDTH and
                                img_data.get("height", 0) >= _MIN_IMAGE_HEIGHT):
                            ext = img_data.get("ext", "png")
                            raw_bytes = img_data["image"]
                            # Write with correct extension
                            actual_path = img_path.rsplit('.', 1)[0] + f".{ext}"
                            with open(actual_path, "wb") as f:
                                f.write(raw_bytes)
                            # Update filename for relative path
                            actual_filename = Path(actual_path).name
                            fig.image_path = f"figures/{actual_filename}"
                            rendered += 1
                            strategy_counts["embedded"] += 1
                            continue
                    except Exception as e:
                        logger.debug(f"Embedded image extraction failed for {fig.label}: {e}")

                # Strategy 2: Crop to figure region
                if clip_rect:
                    result_path = render_page_region_to_image(
                        pdf_path, fig.page_number, img_path, clip_rect, dpi=dpi
                    )
                    if result_path:
                        fig.image_path = f"figures/{img_filename}"
                        rendered += 1
                        strategy_counts["cropped"] += 1
                        continue

            # Strategy 3: Full page fallback
            result_path = render_page_to_image(pdf_path, fig.page_number, img_path, dpi=dpi)
            if result_path:
                fig.image_path = f"figures/{img_filename}"
                rendered += 1
                strategy_counts["fullpage"] += 1

        doc.close()

    except Exception as e:
        logger.error(f"Error during figure rendering: {e}")

    logger.info(
        f"  ✓ Rendered {rendered}/{len(figures)} figures "
        f"(embedded: {strategy_counts['embedded']}, "
        f"cropped: {strategy_counts['cropped']}, "
        f"full-page: {strategy_counts['fullpage']})"
    )
    return figures


# ---------------------------------------------------------------------------
# Part C: Post-processing linker
# ---------------------------------------------------------------------------

def link_references_to_narratives(
    inline_refs: List[InlineCrossReference],
    narrative_contents: List[Dict],
) -> None:
    """Resolve targetId on each InlineCrossReference by matching
    targetSection to NarrativeContent sectionNumber.

    Modifies inline_refs in place.
    """
    # Build lookup: section_number → NarrativeContent id
    section_map: Dict[str, str] = {}
    for nc in narrative_contents:
        if not isinstance(nc, dict):
            continue
        num = nc.get('sectionNumber', '')
        nc_id = nc.get('id', '')
        if num and nc_id:
            section_map[num] = nc_id

    resolved = 0
    for ref in inline_refs:
        if ref.target_id:
            continue  # Already resolved
        if ref.target_section and ref.target_section in section_map:
            ref.target_id = section_map[ref.target_section]
            resolved += 1
        elif ref.target_section:
            # Try parent section (e.g. "5.2.1" → "5.2" → "5")
            parts = ref.target_section.split('.')
            for i in range(len(parts) - 1, 0, -1):
                parent = '.'.join(parts[:i])
                if parent in section_map:
                    ref.target_id = section_map[parent]
                    resolved += 1
                    break

    logger.info(f"  ✓ Linked {resolved}/{len(inline_refs)} cross-references to narrative sections")


def assign_figures_to_sections(
    figures: List[ProtocolFigure],
    narrative_contents: List[Dict],
) -> None:
    """Assign sectionNumber to figures based on which narrative section
    they appear near (by page proximity).

    Modifies figures in place.
    """
    if not figures or not narrative_contents:
        return

    # Build a rough page → section mapping from narrative text page markers
    # The narrative extractor embeds "--- Page N ---" markers in text
    section_pages: List[Tuple[str, int]] = []
    for nc in narrative_contents:
        if not isinstance(nc, dict):
            continue
        num = nc.get('sectionNumber', '')
        text = nc.get('text', '')
        if not num or not text:
            continue
        # Find first page marker in the section text
        m = re.search(r'---\s*Page\s+(\d+)\s*---', text)
        if m:
            section_pages.append((num, int(m.group(1)) - 1))  # Convert to 0-indexed

    if not section_pages:
        return

    # Sort by page number
    section_pages.sort(key=lambda x: x[1])

    assigned = 0
    for fig in figures:
        if fig.section_number or fig.page_number is None:
            continue
        # Find the section whose page is closest but <= figure page
        best_section = None
        for sec_num, sec_page in section_pages:
            if sec_page <= fig.page_number:
                best_section = sec_num
            else:
                break
        if best_section:
            fig.section_number = best_section
            assigned += 1

    logger.info(f"  ✓ Assigned {assigned}/{len(figures)} figures to sections")
