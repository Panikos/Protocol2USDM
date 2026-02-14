"""
Document Structure Extractor - Phase 12 of USDM Expansion

Extracts DocumentContentReference, CommentAnnotation, StudyDefinitionDocumentVersion,
InlineCrossReference (from narrative text), and ProtocolFigure (from PDF pages).
"""

import json
import logging
import re
from dataclasses import field
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    DocumentStructureData,
    DocumentStructureResult,
    DocumentContentReference,
    CommentAnnotation,
    StudyDefinitionDocumentVersion,
    AnnotationType,
    InlineCrossReference,
    ProtocolFigure,
)
from .prompts import (
    get_document_structure_prompt,
    get_figure_enrichment_prompt,
    get_system_prompt,
)
from .reference_scanner import (
    scan_inline_references,
    scan_pdf_for_figures,
    render_figure_images,
    link_references_to_narratives,
    assign_figures_to_sections,
)

logger = logging.getLogger(__name__)


def find_document_structure_pages(
    pdf_path: str,
    max_pages_to_scan: int = 60,
) -> List[int]:
    """
    Find pages containing document structure information.
    """
    import fitz
    
    structure_keywords = [
        r'table\s+of\s+contents',
        r'list\s+of\s+tables',
        r'list\s+of\s+figures',
        r'appendix',
        r'see\s+section',
        r'refer\s+to',
        r'footnote',
        r'protocol\s+version',
        r'amendment',
        r'document\s+history',
        r'revision\s+history',
        r'version\s+\d',
    ]
    
    pattern = re.compile('|'.join(structure_keywords), re.IGNORECASE)
    
    structure_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        # Always include first few pages (cover, TOC)
        structure_pages = [0, 1, 2, 3, 4]
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            matches = len(pattern.findall(text))
            if matches >= 2 and page_num not in structure_pages:
                structure_pages.append(page_num)
        
        doc.close()
        
        structure_pages = sorted(set(structure_pages))
        if len(structure_pages) > 20:
            structure_pages = structure_pages[:20]
        
        logger.info(f"Found {len(structure_pages)} document structure pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        structure_pages = list(range(min(10, get_page_count(pdf_path))))
    
    return structure_pages


def parse_annotation_type(type_str: str) -> AnnotationType:
    """Parse annotation type string to enum."""
    type_map = {
        'footnote': AnnotationType.FOOTNOTE,
        'comment': AnnotationType.COMMENT,
        'note': AnnotationType.NOTE,
        'clarification': AnnotationType.CLARIFICATION,
        'reference': AnnotationType.REFERENCE,
    }
    return type_map.get(type_str.lower(), AnnotationType.FOOTNOTE)


def extract_document_structure(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    output_dir: Optional[str] = None,
    narrative_contents: Optional[List[Dict]] = None,
) -> DocumentStructureResult:
    """
    Extract document structure from protocol PDF.

    Args:
        pdf_path: Path to the protocol PDF.
        model: LLM model for enrichment.
        output_dir: Directory for output files (figures saved here too).
        narrative_contents: List of NarrativeContent dicts from prior phases,
            used for cross-reference scanning and linking.
    """
    logger.info("Starting document structure extraction...")
    
    pages = find_document_structure_pages(pdf_path)
    
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return DocumentStructureResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    prompt = get_document_structure_prompt(text)
    system_prompt = get_system_prompt()
    
    try:
        full_prompt = f"{system_prompt}\n\n{prompt}"
        result = call_llm(
            prompt=full_prompt,
            model_name=model,
            json_mode=True,
            extractor_name="document_structure",
            temperature=0.1,
        )
        response = result.get('response', '')
        
        if not response or not response.strip():
            logger.warning("LLM returned empty response for document structure")
            return DocumentStructureResult(
                success=False,
                error="LLM returned empty response",
                pages_used=pages,
                model_used=model,
            )
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()
        
        if not json_str or json_str == '':
            logger.warning("No JSON content found in LLM response")
            return DocumentStructureResult(
                success=False,
                error="No JSON content in response",
                pages_used=pages,
                model_used=model,
            )
        
        raw_data = json.loads(json_str)
        
        # Parse content references
        content_references = []
        for r in raw_data.get('contentReferences', []):
            ref = DocumentContentReference(
                id=r.get('id', f"ref_{len(content_references)+1}"),
                name=r.get('name', ''),
                section_number=r.get('sectionNumber'),
                section_title=r.get('sectionTitle'),
                page_number=r.get('pageNumber'),
                target_id=r.get('targetId'),
                description=r.get('description'),
            )
            content_references.append(ref)
        
        # Parse annotations
        annotations = []
        for a in raw_data.get('annotations', []):
            annot = CommentAnnotation(
                id=a.get('id', f"annot_{len(annotations)+1}"),
                text=a.get('text', ''),
                annotation_type=parse_annotation_type(a.get('annotationType', 'Footnote')),
                source_section=a.get('sourceSection'),
                page_number=a.get('pageNumber'),
            )
            annotations.append(annot)
        
        # Parse document versions
        document_versions = []
        for v in raw_data.get('documentVersions', []):
            ver = StudyDefinitionDocumentVersion(
                id=v.get('id', f"ver_{len(document_versions)+1}"),
                version_number=v.get('versionNumber', '1.0'),
                version_date=v.get('versionDate'),
                status=v.get('status', 'Final'),
                description=v.get('description'),
                amendment_number=v.get('amendmentNumber'),
            )
            document_versions.append(ver)
        
        # --- Deterministic: Inline cross-reference scanning ---
        inline_refs: List[InlineCrossReference] = []
        if narrative_contents:
            inline_refs = scan_inline_references(narrative_contents)
            link_references_to_narratives(inline_refs, narrative_contents)

        # --- Deterministic: Figure/table scanning from PDF ---
        figures = scan_pdf_for_figures(pdf_path)
        if figures and narrative_contents:
            assign_figures_to_sections(figures, narrative_contents)

        # --- Render figure page images ---
        if figures and output_dir:
            figures = render_figure_images(pdf_path, figures, output_dir)

        # --- LLM enrichment: fill in missing figure titles ---
        if figures:
            figures = _enrich_figure_titles(figures, pdf_path, model)

        data = DocumentStructureData(
            content_references=content_references,
            annotations=annotations,
            document_versions=document_versions,
            inline_references=inline_refs,
            figures=figures,
        )
        
        total_items = (len(content_references) + len(annotations) +
                       len(document_versions) + len(inline_refs) + len(figures))
        confidence = min(1.0, total_items / 15)
        
        result = DocumentStructureResult(
            success=True,
            data=data,
            pages_used=pages,
            model_used=model,
            confidence=confidence,
        )
        
        if output_dir:
            output_path = Path(output_dir) / "13_document_structure.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved document structure to {output_path}")
        
        logger.info(
            f"Extracted {len(content_references)} refs, {len(annotations)} annotations, "
            f"{len(document_versions)} versions, {len(inline_refs)} inline xrefs, "
            f"{len(figures)} figures/tables"
        )
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return DocumentStructureResult(
            success=False,
            error=f"JSON parse error: {e}",
            pages_used=pages,
            model_used=model,
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return DocumentStructureResult(
            success=False,
            error=str(e),
            pages_used=pages,
            model_used=model,
        )


def _enrich_figure_titles(
    figures: List[ProtocolFigure],
    pdf_path: str,
    model: str,
) -> List[ProtocolFigure]:
    """Use a lightweight LLM call to fill in missing titles for figures.

    Only calls the LLM if at least one figure is missing a title.
    Extracts text from each figure's page as context for the LLM.
    """
    needs_enrichment = [f for f in figures if not f.title]
    if not needs_enrichment:
        return figures

    # Build catalog string and page contexts
    catalog_lines = []
    page_nums = set()
    for fig in figures:
        t = fig.title or "(unknown)"
        s = fig.section_number or "?"
        catalog_lines.append(f"- {fig.label}: title={t}, section={s}, page={fig.page_number}")
        if fig.page_number is not None:
            page_nums.add(fig.page_number)

    catalog_str = "\n".join(catalog_lines)

    # Extract text from figure pages for context
    page_contexts = ""
    if page_nums:
        sorted_pages = sorted(page_nums)[:15]  # Limit to avoid huge prompts
        from core.pdf_utils import extract_text_from_pages
        page_contexts = extract_text_from_pages(pdf_path, sorted_pages) or ""

    try:
        prompt = get_figure_enrichment_prompt(catalog_str, page_contexts)
        system = get_system_prompt()
        result = call_llm(
            prompt=f"{system}\n\n{prompt}",
            model_name=model,
            json_mode=True,
            extractor_name="figure_enrichment",
            temperature=0.1,
        )
        response = result.get('response', '')
        if not response:
            return figures

        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response.strip()
        raw = json.loads(json_str)

        # Build lookup by label
        enrichment_map: Dict[str, Dict] = {}
        for item in raw.get('figures', []):
            label = item.get('label', '')
            if label:
                enrichment_map[label] = item

        enriched = 0
        for fig in figures:
            if fig.label in enrichment_map:
                info = enrichment_map[fig.label]
                if not fig.title and info.get('title'):
                    fig.title = info['title']
                    enriched += 1
                if not fig.section_number and info.get('sectionNumber'):
                    fig.section_number = info['sectionNumber']

        logger.info(f"  ✓ LLM enriched {enriched} figure titles")

    except Exception as e:
        logger.warning(f"Figure title enrichment failed (non-fatal): {e}")

    return figures
