"""
Document Structure Extractor - Phase 12 of USDM Expansion

Extracts DocumentContentReference, CommentAnnotation, StudyDefinitionDocumentVersion.
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
)
from .prompts import get_document_structure_prompt, get_system_prompt

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
) -> DocumentStructureResult:
    """
    Extract document structure from protocol PDF.
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
        
        data = DocumentStructureData(
            content_references=content_references,
            annotations=annotations,
            document_versions=document_versions,
        )
        
        confidence = min(1.0, (len(content_references) + len(annotations) + len(document_versions)) / 10)
        
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
        
        logger.info(f"Extracted {len(content_references)} refs, {len(annotations)} annotations, {len(document_versions)} versions")
        
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
