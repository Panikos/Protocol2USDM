"""
M11 Protocol Document Renderer — generates DOCX from USDM JSON.

Transforms a protocol_usdm.json into an ICH M11-structured Word document
by combining:
  1. M11 section mapping (from m11_mapper)
  2. Narrative content (extracted text)
  3. Structured USDM entities (objectives, endpoints, arms, epochs, etc.)

The renderer produces a professional DOCX with:
  - Title page with protocol metadata
  - Table of contents placeholder
  - All 14 M11 sections with proper heading hierarchy
  - Auto-composed entity sections (objectives, eligibility, study design)
  - Synopsis table

Reference: ICH M11 Guideline, Template & Technical Specification (Step 4, 19 Nov 2025)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)


@dataclass
class M11RenderResult:
    """Result of M11 DOCX rendering."""
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    sections_rendered: int = 0
    sections_with_content: int = 0
    total_words: int = 0


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _setup_styles(doc: Document) -> None:
    """Configure document styles per ICH M11 Template conventions.

    ICH M11 Template (Step 4, Nov 2025) heading table specifies:
      - Font: Times New Roman throughout
      - Body: 11pt, 1.15 line spacing, 6pt after paragraph
      - L1 (§N): 14pt TIMES NEW ROMAN BOLD BLACK (ALL CAPS)
      - L2 (§N.N): 14pt Times New Roman Bold Black
      - L3 (§N.N.N): 12pt Times New Roman Bold Black
      - L4 (§N.N.N.N): 12pt Times New Roman Bold Black
      - Non-numbered headings: 12pt Times New Roman Bold Black
      - Margins: 1 inch (2.54 cm) all sides
      - Page size: Letter (8.5 x 11 in)
    """
    # --- Page setup ---
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    # --- Normal (body text) ---
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0, 0, 0)
    pf = style.paragraph_format
    pf.space_after = Pt(6)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.15

    # --- Heading 1 (M11 major sections: §1, §2, ... §14) ---
    h1 = doc.styles['Heading 1']
    h1.font.name = 'Times New Roman'
    h1.font.size = Pt(14)
    h1.font.bold = True
    h1.font.italic = False
    h1.font.color.rgb = RGBColor(0, 0, 0)
    h1.font.all_caps = True
    h1.paragraph_format.space_before = Pt(24)
    h1.paragraph_format.space_after = Pt(6)
    h1.paragraph_format.keep_with_next = True
    h1.paragraph_format.page_break_before = False

    # --- Heading 2 (M11 sub-sections: §1.1, §3.1, etc.) ---
    # M11 Template: 14 point Times New Roman Bold Black
    h2 = doc.styles['Heading 2']
    h2.font.name = 'Times New Roman'
    h2.font.size = Pt(14)
    h2.font.bold = True
    h2.font.italic = False
    h2.font.color.rgb = RGBColor(0, 0, 0)
    h2.font.all_caps = False
    h2.paragraph_format.space_before = Pt(18)
    h2.paragraph_format.space_after = Pt(6)
    h2.paragraph_format.keep_with_next = True

    # --- Heading 3 (M11 sub-sub-sections: §1.1.2, §5.1.1, etc.) ---
    # M11 Template: 12 point Times New Roman Bold Black
    h3 = doc.styles['Heading 3']
    h3.font.name = 'Times New Roman'
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.italic = False
    h3.font.color.rgb = RGBColor(0, 0, 0)
    h3.paragraph_format.space_before = Pt(12)
    h3.paragraph_format.space_after = Pt(3)
    h3.paragraph_format.keep_with_next = True

    # --- Heading 4 (§N.N.N.N — e.g. 10.4.1, 6.10.1) ---
    # M11 Template: 12 point Times New Roman Bold Black
    try:
        h4 = doc.styles['Heading 4']
    except KeyError:
        h4 = doc.styles.add_style('Heading 4', 1)  # 1 = WD_STYLE_TYPE.PARAGRAPH
    h4.font.name = 'Times New Roman'
    h4.font.size = Pt(12)
    h4.font.bold = True
    h4.font.italic = False
    h4.font.color.rgb = RGBColor(0, 0, 0)
    h4.paragraph_format.space_before = Pt(6)
    h4.paragraph_format.space_after = Pt(3)
    h4.paragraph_format.keep_with_next = True

    # --- Heading 5 (§N.N.N.N.N — e.g. 10.4.1.1, 9.1.3.1) ---
    # M11 uses same 12pt bold for these deep sub-sections
    try:
        h5 = doc.styles['Heading 5']
    except KeyError:
        h5 = doc.styles.add_style('Heading 5', 1)
    h5.font.name = 'Times New Roman'
    h5.font.size = Pt(12)
    h5.font.bold = True
    h5.font.italic = False
    h5.font.color.rgb = RGBColor(0, 0, 0)
    h5.paragraph_format.space_before = Pt(6)
    h5.paragraph_format.space_after = Pt(3)
    h5.paragraph_format.keep_with_next = True

    # --- List Bullet ---
    try:
        lb = doc.styles['List Bullet']
        lb.font.name = 'Times New Roman'
        lb.font.size = Pt(11)
        lb.paragraph_format.space_after = Pt(3)
        lb.paragraph_format.space_before = Pt(0)
        lb.paragraph_format.left_indent = Inches(0.5)
    except KeyError:
        pass

    # --- List Number ---
    try:
        ln = doc.styles['List Number']
        ln.font.name = 'Times New Roman'
        ln.font.size = Pt(11)
        ln.paragraph_format.space_after = Pt(3)
        ln.paragraph_format.space_before = Pt(0)
        ln.paragraph_format.left_indent = Inches(0.5)
    except KeyError:
        pass


def _add_toc_field(doc: Document) -> None:
    """Insert a real Word TOC field code.

    When the document is opened in Word, right-click the TOC and select
    'Update Field' to populate it from the heading styles.
    """
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)

    # Build the TOC field XML:  TOC \\o "1-3" \\h \\z \\u
    run = p.add_run()
    fldChar_begin = run._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
    run._element.append(fldChar_begin)

    run2 = p.add_run()
    instrText = run2._element.makeelement(qn('w:instrText'), {qn('xml:space'): 'preserve'})
    instrText.text = r' TOC \o "1-3" \h \z \u '
    run2._element.append(instrText)

    run3 = p.add_run()
    fldChar_separate = run3._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'separate'})
    run3._element.append(fldChar_separate)

    # Placeholder text shown before field is updated
    run4 = p.add_run('[Right-click here and select "Update Field" to generate Table of Contents]')
    run4.font.size = Pt(10)
    run4.font.name = 'Times New Roman'
    run4.font.italic = True
    run4.font.color.rgb = RGBColor(128, 128, 128)

    run5 = p.add_run()
    fldChar_end = run5._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
    run5._element.append(fldChar_end)


def _add_headers_footers(doc: Document, usdm: Dict) -> None:
    """Add M11-compliant headers and footers.

    Header: Sponsor Protocol Identifier + Confidential (right-aligned)
    Footer: Page X of Y (centered)
    """
    # Extract protocol ID for header
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    identifiers = version.get('studyIdentifiers', study.get('studyIdentifiers', []))
    protocol_id = ''
    for ident in identifiers:
        if not isinstance(ident, dict):
            continue
        ident_type = ident.get('type', {})
        code = ident_type.get('code', '') if isinstance(ident_type, dict) else ''
        decode = ident_type.get('decode', '') if isinstance(ident_type, dict) else ''
        value = ident.get('text', ident.get('studyIdentifier', ''))
        if code == 'C132351' or 'sponsor' in decode.lower():
            protocol_id = value
            break

    if not protocol_id:
        # Fall back to study name
        protocol_id = study.get('name', 'Protocol')

    # Apply to all sections (including landscape SoA section)
    for section in doc.sections:
        section.different_first_page_header_footer = False

        # --- Header ---
        header = section.header
        header.is_linked_to_previous = False
        if header.paragraphs:
            hp = header.paragraphs[0]
        else:
            hp = header.add_paragraph()
        hp.text = ''
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.paragraph_format.space_after = Pt(0)
        hp.paragraph_format.space_before = Pt(0)

        run_id = hp.add_run(protocol_id)
        run_id.font.name = 'Times New Roman'
        run_id.font.size = Pt(8)
        run_id.bold = True

        run_sep = hp.add_run('    ')

        run_conf = hp.add_run('CONFIDENTIAL')
        run_conf.font.name = 'Times New Roman'
        run_conf.font.size = Pt(8)
        run_conf.font.color.rgb = RGBColor(192, 0, 0)
        run_conf.bold = True

        # --- Footer: Page X of Y ---
        footer = section.footer
        footer.is_linked_to_previous = False
        if footer.paragraphs:
            fp = footer.paragraphs[0]
        else:
            fp = footer.add_paragraph()
        fp.text = ''
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.paragraph_format.space_after = Pt(0)
        fp.paragraph_format.space_before = Pt(0)

        run_pre = fp.add_run('Page ')
        run_pre.font.name = 'Times New Roman'
        run_pre.font.size = Pt(8)

        # PAGE field
        run_page = fp.add_run()
        fldChar1 = run_page._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
        run_page._element.append(fldChar1)
        run_instr1 = fp.add_run()
        instrText1 = run_instr1._element.makeelement(qn('w:instrText'), {qn('xml:space'): 'preserve'})
        instrText1.text = ' PAGE '
        run_instr1._element.append(instrText1)
        run_sep1 = fp.add_run()
        fldSep1 = run_sep1._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'separate'})
        run_sep1._element.append(fldSep1)
        run_num = fp.add_run('1')
        run_num.font.name = 'Times New Roman'
        run_num.font.size = Pt(8)
        run_end1 = fp.add_run()
        fldEnd1 = run_end1._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
        run_end1._element.append(fldEnd1)

        run_of = fp.add_run(' of ')
        run_of.font.name = 'Times New Roman'
        run_of.font.size = Pt(8)

        # NUMPAGES field
        run_total = fp.add_run()
        fldChar2 = run_total._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
        run_total._element.append(fldChar2)
        run_instr2 = fp.add_run()
        instrText2 = run_instr2._element.makeelement(qn('w:instrText'), {qn('xml:space'): 'preserve'})
        instrText2.text = ' NUMPAGES '
        run_instr2._element.append(instrText2)
        run_sep2 = fp.add_run()
        fldSep2 = run_sep2._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'separate'})
        run_sep2._element.append(fldSep2)
        run_total_num = fp.add_run('1')
        run_total_num.font.name = 'Times New Roman'
        run_total_num.font.size = Pt(8)
        run_end2 = fp.add_run()
        fldEnd2 = run_end2._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
        run_end2._element.append(fldEnd2)


def _add_title_page(doc: Document, usdm: Dict) -> None:
    """Add an M11-compliant title page with all Required/Optional fields.

    M11 Title Page data elements (from Technical Specification):
      Required: Full Title, Sponsor Protocol Identifier, Original Protocol
                Indicator, Trial Phase, Sponsor Name and Address,
                Regulatory/Clinical Trial Identifiers, Sponsor Approval
      Optional: Confidentiality Statement, Trial Acronym, Short Title,
                Version Number/Date, Amendment details, IP codes/names,
                Co-Sponsor, Signatory, Medical Expert Contact
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    titles = version.get('titles', [])
    study_design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # ---- Extract title variants by type ----
    full_title = ''
    short_title = ''
    acronym = ''
    for t in titles:
        if not isinstance(t, dict):
            continue
        ttype = t.get('type', {})
        decode = ttype.get('decode', '') if isinstance(ttype, dict) else ''
        code = ttype.get('code', '') if isinstance(ttype, dict) else ''
        txt = t.get('text', '')
        if not txt:
            continue
        dl = decode.lower()
        if 'official' in dl or (not full_title and len(txt) > len(full_title)):
            full_title = txt
        if 'brief' in dl or 'short' in dl:
            short_title = txt
        if 'acronym' in dl:
            acronym = txt

    if not full_title:
        full_title = 'Clinical Protocol'

    # ---- Extract identifiers by C-code / decode ----
    # C-code mapping for M11 regulatory identifiers
    IDENT_MAP = {
        'C132351': 'Sponsor Protocol Identifier',
        'C172240': 'NCT Number',
        'C218684': 'EU CT Number',
        'C218685': 'FDA IND Number',
        'C218686': 'IDE Number',
        'C218687': 'jRCT Number',
        'C218688': 'NMPA IND Number',
        'C218689': 'WHO/UTN Number',
        'C98714':  'Registry Identifier',
    }

    identifiers = version.get('studyIdentifiers', study.get('studyIdentifiers', []))
    sponsor_protocol_id = ''
    regulatory_ids: List[tuple] = []

    for ident in identifiers:
        if not isinstance(ident, dict):
            continue
        ident_type = ident.get('type', {})
        code = ident_type.get('code', '') if isinstance(ident_type, dict) else ''
        decode = ident_type.get('decode', '') if isinstance(ident_type, dict) else ''
        value = ident.get('text', ident.get('studyIdentifier', ''))
        if not value:
            continue

        if code == 'C132351' or 'sponsor' in decode.lower():
            sponsor_protocol_id = value
        elif code in IDENT_MAP:
            regulatory_ids.append((IDENT_MAP[code], value))
        elif 'registry' in decode.lower() or 'identifier' in decode.lower():
            regulatory_ids.append((decode, value))

    # ---- Extract organizations ----
    organizations = version.get('organizations', study.get('organizations', []))
    sponsor_name = ''
    sponsor_address = ''
    for org in organizations:
        if not isinstance(org, dict):
            continue
        org_type = org.get('type', {})
        org_decode = org_type.get('decode', '') if isinstance(org_type, dict) else ''
        org_code = org_type.get('code', '') if isinstance(org_type, dict) else ''
        # C70793 = Clinical Study Site, C54086 = Pharmaceutical Company
        if org_code == 'C54086' or 'sponsor' in org_decode.lower() or 'pharma' in org_decode.lower():
            sponsor_name = org.get('name', '')
            sponsor_address = org.get('legalAddress', org.get('address', ''))
            if isinstance(sponsor_address, dict):
                parts = [sponsor_address.get(k, '') for k in
                         ['line', 'city', 'state', 'postalCode', 'country'] if sponsor_address.get(k)]
                sponsor_address = ', '.join(parts)
            break

    # ---- Trial Phase ----
    phase = version.get('studyPhase', study_design.get('studyPhase', {}))
    phase_text = ''
    if isinstance(phase, dict):
        phase_text = phase.get('decode', phase.get('code', ''))

    # ---- Investigational Product info ----
    interventions = version.get('studyInterventions', [])
    ip_names = []
    for si in interventions:
        if not isinstance(si, dict):
            continue
        role = si.get('role', si.get('type', {}))
        role_decode = role.get('decode', '') if isinstance(role, dict) else ''
        if 'investigational' in role_decode.lower() or not ip_names:
            name = si.get('name', '')
            if name:
                ip_names.append(name)

    # ---- Amendments ----
    amendments = version.get('amendments', [])
    has_amendment = bool(amendments)
    latest_amendment = amendments[-1] if amendments else {}

    # ---- Version info ----
    ver_text = version.get('versionIdentifier', '')
    date_text = version.get('effectiveDate', '')

    # ================================================================
    # Render title page
    # ================================================================

    # Confidentiality statement (M11 Optional) — top of page
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run('CONFIDENTIAL')
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'
    run.font.color.rgb = RGBColor(192, 0, 0)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(
        'This document is confidential and the property of the sponsor. '
        'No part of it may be transmitted, reproduced, published, or used '
        'without prior written authorization from the sponsor.'
    )
    run.font.size = Pt(8)
    run.font.name = 'Times New Roman'
    run.font.italic = True
    run.font.color.rgb = RGBColor(128, 128, 128)

    # Vertical spacing before title
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(72)
    p.paragraph_format.space_after = Pt(0)

    # Full Title (M11 Required)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(full_title)
    run.bold = True
    run.font.size = Pt(16)
    run.font.name = 'Times New Roman'

    # Short Title / Acronym line
    subtitle_parts = []
    if short_title:
        subtitle_parts.append(short_title)
    if acronym:
        subtitle_parts.append(f'({acronym})')
    if subtitle_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(24)
        run = p.add_run(' '.join(subtitle_parts))
        run.font.size = Pt(12)
        run.font.name = 'Times New Roman'
        run.font.italic = True

    # ---- Metadata table (M11 structured fields) ----
    meta_items: List[tuple] = []

    if sponsor_protocol_id:
        meta_items.append(('Sponsor Protocol Identifier', sponsor_protocol_id))
    meta_items.append(('Original Protocol', 'No' if has_amendment else 'Yes'))
    if ver_text:
        meta_items.append(('Version Number', ver_text))
    if date_text:
        meta_items.append(('Version Date', date_text))
    if has_amendment and isinstance(latest_amendment, dict):
        amend_name = latest_amendment.get('name', latest_amendment.get('number', ''))
        if amend_name:
            meta_items.append(('Amendment Identifier', amend_name))
        scope = latest_amendment.get('scope', {})
        scope_text = scope.get('decode', '') if isinstance(scope, dict) else ''
        if scope_text:
            meta_items.append(('Amendment Scope', scope_text))
    if ip_names:
        meta_items.append(("Investigational Product(s)", ', '.join(ip_names)))
    if phase_text:
        meta_items.append(('Trial Phase', phase_text))
    if sponsor_name:
        sponsor_val = sponsor_name
        if sponsor_address:
            sponsor_val += f'\n{sponsor_address}'
        meta_items.append(('Sponsor Name and Address', sponsor_val))
    for label, value in regulatory_ids:
        meta_items.append((label, value))
    meta_items.append(('Sponsor Approval Date',
                        date_text if date_text else '[Date of sponsor approval]'))

    # Render the metadata table — borderless with light shading on labels
    if meta_items:
        table = doc.add_table(rows=len(meta_items), cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Use no-border style for a cleaner look
        table.style = 'Table Grid'

        for i, (label, value) in enumerate(meta_items):
            cell_label = table.rows[i].cells[0]
            cell_value = table.rows[i].cells[1]
            cell_label.text = ''
            cell_value.text = ''

            # Label cell — bold, light grey background
            p_label = cell_label.paragraphs[0]
            p_label.paragraph_format.space_before = Pt(2)
            p_label.paragraph_format.space_after = Pt(2)
            run_label = p_label.add_run(label)
            run_label.bold = True
            run_label.font.size = Pt(10)
            run_label.font.name = 'Times New Roman'
            # Grey background
            tcPr = cell_label._element.get_or_add_tcPr()
            shd = tcPr.makeelement(qn('w:shd'), {
                qn('w:fill'): 'F2F2F2', qn('w:val'): 'clear'})
            tcPr.append(shd)

            # Value cell
            p_value = cell_value.paragraphs[0]
            p_value.paragraph_format.space_before = Pt(2)
            p_value.paragraph_format.space_after = Pt(2)
            run_value = p_value.add_run(str(value))
            run_value.font.size = Pt(10)
            run_value.font.name = 'Times New Roman'

            # Set column widths
            cell_label.width = Cm(6)
            cell_value.width = Cm(10)

    # Generation timestamp (bottom of title page)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(36)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(f'Document generated: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
    run.font.size = Pt(8)
    run.font.name = 'Times New Roman'
    run.font.italic = True
    run.font.color.rgb = RGBColor(160, 160, 160)

    doc.add_page_break()


# ---------------------------------------------------------------------------
# Entity composers — auto-generate section text from USDM entities
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Entity composers — imported from rendering.composers
# ---------------------------------------------------------------------------
from .composers import (
    _compose_synopsis,
    _compose_interventions,
    _compose_objectives,
    _compose_study_design,
    _compose_eligibility,
    _compose_estimands,
    _compose_statistics,
    _compose_safety,
    _compose_discontinuation,
)
from .tables import _add_soa_table, _add_synopsis_table


# Legacy stubs removed — all composer functions now live in rendering/composers.py
# The following functions were moved:
#   _compose_synopsis        → §1.1.2 Overall Design
#   _compose_interventions   → §6 Trial Interventions
#   _compose_objectives      → §3 Objectives and Endpoints
#   _compose_study_design    → §4 Trial Design
#   _compose_eligibility     → §5 Study Population
#   _compose_estimands       → §3.1 Estimands
#   _compose_statistics      → §10 Statistical Considerations
#   _compose_safety          → §9 Adverse Events / Safety
#   _compose_discontinuation → §7 Discontinuation


# ---------------------------------------------------------------------------
# Sub-heading content distribution
# ---------------------------------------------------------------------------

def _distribute_to_subsections(
    narrative_text: str,
    subheadings: List[tuple],
) -> Dict[str, str]:
    """Distribute narrative paragraphs to M11 sub-sections by keyword matching.

    Splits the narrative into paragraphs and scores each against the sub-heading
    keyword lists.  Returns a dict mapping sub_number → matched text, plus
    '_general' for unmatched paragraphs.

    Args:
        narrative_text: Full narrative text for the section
        subheadings: List of (sub_number, title, level, keywords) tuples

    Returns:
        Dict mapping sub_number → concatenated paragraph text
    """
    paragraphs = [p.strip() for p in narrative_text.split('\n') if p.strip()]
    if not paragraphs:
        return {'_general': ''}

    # Build buckets
    buckets: Dict[str, List[str]] = {'_general': []}
    for sub_num, _title, _level, _kw in subheadings:
        buckets[sub_num] = []

    for para in paragraphs:
        para_lower = para.lower()
        best_sub = None
        best_score = 0

        for sub_num, _title, _level, keywords in subheadings:
            score = sum(1 for kw in keywords if kw.lower() in para_lower)
            if score > best_score:
                best_score = score
                best_sub = sub_num

        if best_sub and best_score > 0:
            buckets[best_sub].append(para)
        else:
            buckets['_general'].append(para)

    # Join each bucket
    return {k: '\n'.join(v) for k, v in buckets.items()}


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_m11_docx(
    usdm: Dict,
    output_path: str,
    m11_mapping: Optional[Dict] = None,
) -> M11RenderResult:
    """
    Render an ICH M11-structured DOCX from USDM JSON.

    Args:
        usdm: Full protocol_usdm.json dict
        output_path: Path for the output .docx file
        m11_mapping: Optional pre-computed M11 mapping from the pipeline.
                     If not provided, computes it from narrative data.

    Returns:
        M11RenderResult with success status and stats
    """
    result = M11RenderResult(success=False)

    try:
        doc = Document()
        _setup_styles(doc)

        # Title page
        _add_title_page(doc, usdm)

        # Table of Contents — real Word TOC field
        doc.add_heading('Table of Contents', level=1)
        _add_toc_field(doc)
        doc.add_page_break()

        # Get or compute M11 mapping
        if m11_mapping is None:
            m11_mapping = _compute_m11_mapping(usdm)

        m11_sections = m11_mapping.get('sections', {})

        # Entity composers for enrichment
        entity_composers = {
            '1': _compose_synopsis,
            '3': _compose_objectives,
            '4': _compose_study_design,
            '5': _compose_eligibility,
            '6': _compose_interventions,
            '7': _compose_discontinuation,
            '9': _compose_safety,
            '10': _compose_statistics,
        }

        # Render each M11 section with sub-heading support
        from extraction.narrative.m11_mapper import M11_TEMPLATE, M11_SUBHEADINGS
        sections_rendered = 0
        sections_with_content = 0
        total_words = 0

        def _heading_level(section_number: str) -> int:
            """Determine Word heading level from M11 section number.

            M11 heading levels per template:
              '1'         → L1 (14pt ALL CAPS)
              '1.1'       → L2 (14pt bold)
              '1.1.2'     → L3 (12pt bold)
              '10.4.1'    → L4 (12pt bold)
              '10.4.1.1'  → L5 (12pt bold)
            Deeper levels capped at 5 (Word supports up to 9).
            """
            parts = section_number.split('.')
            return min(len(parts), 5)

        for m11 in M11_TEMPLATE:
            sec_data = m11_sections.get(m11.number, {})
            narrative_text = sec_data.get('text', '')
            has_content = bool(narrative_text.strip())

            # Add M11 section heading (L1 — style has all_caps=True)
            doc.add_heading(f'{m11.number} {m11.title}', level=1)

            # Distribute narrative to sub-sections if sub-headings defined
            subheadings = M11_SUBHEADINGS.get(m11.number, [])
            if narrative_text.strip() and subheadings:
                subsection_content = _distribute_to_subsections(
                    narrative_text, subheadings
                )
                # Render general content (not matched to any sub-heading)
                general = subsection_content.get('_general', '')
                if general.strip():
                    _add_narrative_text(doc, general)
                    total_words += len(general.split())
                # Render each sub-heading with its matched content
                for sub_num, sub_title, sub_level, _kw in subheadings:
                    sub_text = subsection_content.get(sub_num, '')
                    if sub_text.strip():
                        # Use section number depth for heading level
                        level = _heading_level(sub_num)
                        doc.add_heading(f'{sub_num} {sub_title}', level=level)
                        _add_narrative_text(doc, sub_text)
                        total_words += len(sub_text.split())
                    else:
                        # Render empty sub-section heading with placeholder
                        level = _heading_level(sub_num)
                        doc.add_heading(f'{sub_num} {sub_title}', level=level)
                sections_with_content += 1
            elif narrative_text.strip():
                # No sub-headings defined — render as flat narrative
                _add_narrative_text(doc, narrative_text)
                total_words += len(narrative_text.split())
                sections_with_content += 1

            # --- Section 1 special handling: Synopsis table + SoA table ---
            if m11.number == '1':
                # §1.1 Protocol Synopsis
                doc.add_heading('1.1 Protocol Synopsis', level=2)

                # §1.1.1 Primary and Secondary Objectives and Estimands
                doc.add_heading(
                    '1.1.1 Primary and Secondary Objectives and Estimands',
                    level=3
                )
                obj_text = _compose_objectives(usdm)
                if obj_text.strip():
                    _add_narrative_text(doc, obj_text)
                    total_words += len(obj_text.split())

                # §1.1.2 Overall Design — render as structured table
                doc.add_heading('1.1.2 Overall Design', level=3)
                synopsis_rendered = _add_synopsis_table(doc, usdm)
                if synopsis_rendered:
                    sections_with_content += 1
                elif not has_content:
                    composed = _compose_synopsis(usdm)
                    if composed.strip():
                        _add_narrative_text(doc, composed)
                        total_words += len(composed.split())
                        sections_with_content += 1

                # §1.2 Trial Schema
                doc.add_heading('1.2 Trial Schema', level=2)
                p = doc.add_paragraph()
                run = p.add_run('[Trial schema diagram — refer to Section 4 '
                                'Trial Design for details]')
                run.italic = True
                run.font.color.rgb = RGBColor(128, 128, 128)

                # §1.3 Schedule of Activities — render as DOCX table
                doc.add_heading('1.3 Schedule of Activities', level=2)
                soa_rendered = _add_soa_table(doc, usdm)
                if soa_rendered:
                    if not has_content and not synopsis_rendered:
                        sections_with_content += 1
                else:
                    p = doc.add_paragraph()
                    run = p.add_run('[Schedule of Activities table not available — '
                                    'no schedule timeline data in USDM]')
                    run.italic = True
                    run.font.color.rgb = RGBColor(192, 0, 0)

            else:
                # Entity-composed content (supplement or replace empty narrative)
                composer = entity_composers.get(m11.number)
                if composer:
                    composed = composer(usdm)
                    if composed.strip():
                        _add_narrative_text(doc, composed)
                        total_words += len(composed.split())
                        if not has_content:
                            sections_with_content += 1

                # Estimand tables for section 3
                if m11.number == '3':
                    estimand_text = _compose_estimands(usdm)
                    if estimand_text:
                        doc.add_heading(
                            '3.1 Primary Objective(s) and Associated Estimand(s)',
                            level=2
                        )
                        _add_narrative_text(doc, estimand_text)

                # Empty section notice
                if not narrative_text.strip() and not (
                    composer and composer(usdm).strip()
                ):
                    p = doc.add_paragraph()
                    run = p.add_run('[Section content not yet available]')
                    run.italic = True
                    run.font.color.rgb = RGBColor(192, 0, 0)

            sections_rendered += 1

            # Page break between major L1 sections (§1–§11)
            # Appendices §12–§14 flow continuously
            try:
                sec_num = int(m11.number)
                if sec_num <= 11:
                    doc.add_page_break()
            except ValueError:
                pass

        # Add headers and footers to all sections (must be after all
        # sections are created, including landscape SoA section)
        _add_headers_footers(doc, usdm)

        # Save
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)

        result.success = True
        result.output_path = output_path
        result.sections_rendered = sections_rendered
        result.sections_with_content = sections_with_content
        result.total_words = total_words

        logger.info(
            f"M11 DOCX rendered: {output_path} "
            f"({sections_with_content}/{sections_rendered} sections with content, "
            f"{total_words} words)"
        )

        # Run M11 conformance validation and save report
        try:
            from validation.m11_conformance import (
                validate_m11_conformance, save_conformance_report,
            )
            conf_report = validate_m11_conformance(usdm, m11_mapping)
            conf_path = str(Path(output_path).parent / 'm11_conformance_report.json')
            save_conformance_report(conf_report, conf_path)
        except Exception as conf_err:
            logger.warning(f"M11 conformance check failed: {conf_err}")

    except Exception as e:
        logger.error(f"M11 DOCX rendering failed: {e}")
        result.error = str(e)

    return result


def _add_narrative_text(doc: Document, text: str) -> None:
    """Add narrative text to the document with proper formatting.

    Handles:
      - Double-newline paragraph breaks
      - **bold** markers (markdown style)
      - Bullet lists (- item or • item)
      - Numbered lists (1. item, a. item)
      - Markdown headings (### Heading)
      - Regular paragraphs with preserved line breaks
    """
    paragraphs = text.split('\n\n')
    for para_text in paragraphs:
        para_text = para_text.strip()
        if not para_text:
            continue

        lines = para_text.split('\n')

        # Check if this block is a list (all lines start with - or •)
        is_bullet_list = all(
            l.strip().startswith('- ') or l.strip().startswith('• ')
            for l in lines if l.strip()
        )

        # Check if this block is a numbered list
        is_numbered_list = all(
            re.match(r'^\s*(\d+|[a-z])\.\s', l.strip())
            for l in lines if l.strip()
        )

        if is_bullet_list:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Strip bullet prefix
                if line.startswith('- '):
                    line = line[2:]
                elif line.startswith('• '):
                    line = line[2:]
                p = doc.add_paragraph(style='List Bullet')
                _add_formatted_run(p, line)

        elif is_numbered_list:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Strip number prefix but keep the text
                m = re.match(r'^\s*(?:\d+|[a-z])\.\s+(.*)', line)
                content = m.group(1) if m else line
                p = doc.add_paragraph(style='List Number')
                _add_formatted_run(p, content)

        elif para_text.startswith('### '):
            # Markdown L3 heading
            doc.add_heading(para_text[4:].strip(), level=3)

        elif para_text.startswith('## '):
            # Markdown L2 heading
            doc.add_heading(para_text[3:].strip(), level=2)

        elif '**' in para_text:
            # Contains bold markers — render with inline formatting
            p = doc.add_paragraph()
            _add_formatted_run(p, para_text)

        else:
            # Regular paragraph — preserve line breaks within
            p = doc.add_paragraph()
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                if i > 0:
                    p.add_run('\n')
                p.add_run(line)


def _add_formatted_run(paragraph, text: str) -> None:
    """Add text to a paragraph with inline **bold** and *italic* formatting."""
    # Split on bold markers first
    parts = re.split(r'\*\*(.*?)\*\*', text)
    for i, part in enumerate(parts):
        if not part:
            continue
        if i % 2 == 1:
            # Bold content — check for nested italic
            italic_parts = re.split(r'\*(.*?)\*', part)
            for j, ip in enumerate(italic_parts):
                if not ip:
                    continue
                run = paragraph.add_run(ip)
                run.bold = True
                if j % 2 == 1:
                    run.italic = True
        else:
            # Normal content — check for italic
            italic_parts = re.split(r'\*(.*?)\*', part)
            for j, ip in enumerate(italic_parts):
                if not ip:
                    continue
                run = paragraph.add_run(ip)
                if j % 2 == 1:
                    run.italic = True


def _compute_m11_mapping(usdm: Dict) -> Dict:
    """Compute M11 mapping from USDM narrative data on the fly."""
    from extraction.narrative.m11_mapper import map_sections_to_m11, build_m11_narrative

    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    # Combine narrativeContents and narrativeContentItems
    narrative_contents = version.get('narrativeContents', [])
    narrative_items = version.get('narrativeContentItems', [])
    all_items = narrative_contents + narrative_items

    # Build section dicts with sectionType extraction
    sec_dicts = []
    sec_texts = {}
    seen_nums = set()
    for nc in all_items:
        if not isinstance(nc, dict):
            continue
        num = nc.get('sectionNumber', '')
        if not num or num in seen_nums:
            continue
        seen_nums.add(num)
        title = nc.get('sectionTitle', nc.get('name', ''))
        text = nc.get('text', '')
        # Extract section type for Pass 3
        sec_type = ''
        st = nc.get('sectionType', {})
        if isinstance(st, dict):
            sec_type = st.get('decode', st.get('code', ''))
        sec_dicts.append({
            'number': num,
            'title': title,
            'type': sec_type,
        })
        if text and text != title:
            sec_texts[num] = text

    if not sec_dicts:
        return {'sections': {}}

    mapping = map_sections_to_m11(sec_dicts, section_texts=sec_texts)
    m11_narrative = build_m11_narrative(sec_dicts, sec_texts, mapping)

    return {
        'coverage': f"{mapping.m11_covered}/{mapping.m11_total}",
        'requiredCoverage': f"{mapping.m11_required_covered}/{mapping.m11_required_total}",
        'sections': m11_narrative,
    }
