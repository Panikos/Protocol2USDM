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
  - All 12 M11 sections with proper heading hierarchy
  - Auto-composed entity sections (objectives, eligibility, study design)
  - Synopsis table
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

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
    """Configure document styles for M11 template."""
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    for level in range(1, 4):
        heading_style = doc.styles[f'Heading {level}']
        heading_style.font.name = 'Calibri'
        heading_style.font.color.rgb = RGBColor(0, 51, 102)
        if level == 1:
            heading_style.font.size = Pt(16)
            heading_style.font.bold = True
        elif level == 2:
            heading_style.font.size = Pt(14)
            heading_style.font.bold = True
        else:
            heading_style.font.size = Pt(12)
            heading_style.font.bold = True


def _add_title_page(doc: Document, usdm: Dict) -> None:
    """Add a professional title page with protocol metadata."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    titles = version.get('titles', [])

    # Protocol title
    title_text = 'Clinical Protocol'
    for t in titles:
        if isinstance(t, dict):
            txt = t.get('text', '')
            if txt and len(txt) > len(title_text):
                title_text = txt

    # Add spacing before title
    for _ in range(6):
        doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title_text)
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0, 51, 102)

    doc.add_paragraph('')

    # Metadata table
    study_design = (version.get('studyDesigns', [{}]) or [{}])[0]
    meta_items = []

    # Protocol ID
    identifiers = study.get('studyIdentifiers', version.get('studyIdentifiers', []))
    for ident in identifiers:
        if isinstance(ident, dict):
            org = ident.get('studyIdentifierScope', {})
            org_type = org.get('organizationType', {})
            type_decode = org_type.get('decode', '') if isinstance(org_type, dict) else ''
            if 'sponsor' in type_decode.lower() or not meta_items:
                meta_items.insert(0, ('Protocol Number', ident.get('studyIdentifier', '')))

    # Phase
    phase = study_design.get('studyPhase', {})
    if isinstance(phase, dict):
        phase_text = phase.get('decode', phase.get('code', ''))
        if phase_text:
            meta_items.append(('Study Phase', phase_text))

    # Version
    ver_text = version.get('versionIdentifier', '')
    if ver_text:
        meta_items.append(('Protocol Version', ver_text))

    # Date
    date_text = version.get('effectiveDate', '')
    if date_text:
        meta_items.append(('Protocol Date', date_text))

    if meta_items:
        table = doc.add_table(rows=len(meta_items), cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, (label, value) in enumerate(meta_items):
            row = table.rows[i]
            row.cells[0].text = label
            row.cells[0].paragraphs[0].runs[0].bold = True if row.cells[0].paragraphs[0].runs else False
            row.cells[1].text = str(value)

    # Footer note
    doc.add_paragraph('')
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('CONFIDENTIAL')
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(192, 0, 0)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')

    doc.add_page_break()


# ---------------------------------------------------------------------------
# Entity composers — auto-generate section text from USDM entities
# ---------------------------------------------------------------------------

def _compose_objectives(usdm: Dict) -> str:
    """Compose Section 3 content from USDM objectives and endpoints."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    objectives = design.get('objectives', [])
    if not objectives:
        return ''

    lines = []
    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        level = obj.get('objectiveLevel', {})
        level_text = level.get('decode', '') if isinstance(level, dict) else str(level)
        text = obj.get('objectiveText', obj.get('text', ''))
        if text:
            lines.append(f"**{level_text} Objective**: {text}")

        # Endpoints
        for ep in obj.get('objectiveEndpoints', []):
            if isinstance(ep, dict):
                ep_text = ep.get('endpointText', ep.get('text', ''))
                ep_level = ep.get('endpointLevel', {})
                ep_level_text = ep_level.get('decode', '') if isinstance(ep_level, dict) else ''
                if ep_text:
                    lines.append(f"  {ep_level_text} Endpoint: {ep_text}")
        lines.append('')

    return '\n'.join(lines)


def _compose_study_design(usdm: Dict) -> str:
    """Compose Section 4 content from USDM study design entities."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    lines = []

    # Study type
    study_type = design.get('studyType', {})
    if isinstance(study_type, dict) and study_type.get('decode'):
        lines.append(f"Study Type: {study_type['decode']}")

    # Arms
    arms = design.get('studyArms', design.get('arms', []))
    if arms:
        lines.append(f"\nStudy Arms ({len(arms)}):")
        for arm in arms:
            if isinstance(arm, dict):
                name = arm.get('name', arm.get('studyArmName', ''))
                desc = arm.get('description', arm.get('studyArmDescription', ''))
                arm_type = arm.get('studyArmType', {})
                type_text = arm_type.get('decode', '') if isinstance(arm_type, dict) else ''
                lines.append(f"  - {name} ({type_text}): {desc}")

    # Epochs
    epochs = design.get('studyEpochs', design.get('epochs', []))
    if epochs:
        lines.append(f"\nStudy Epochs ({len(epochs)}):")
        for epoch in epochs:
            if isinstance(epoch, dict):
                name = epoch.get('name', epoch.get('studyEpochName', ''))
                etype = epoch.get('studyEpochType', {})
                type_text = etype.get('decode', '') if isinstance(etype, dict) else ''
                lines.append(f"  - {name} ({type_text})")

    return '\n'.join(lines)


def _compose_eligibility(usdm: Dict) -> str:
    """Compose Section 5 content from USDM eligibility criteria."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    populations = design.get('population', design.get('populations', {}))
    if isinstance(populations, dict):
        populations = [populations]

    lines = []
    for pop in populations:
        if not isinstance(pop, dict):
            continue
        criteria = pop.get('criteria', pop.get('criterionIds', []))
        if not criteria:
            continue

        inc = [c for c in criteria if isinstance(c, dict) and
               'inclusion' in str(c.get('category', '')).lower()]
        exc = [c for c in criteria if isinstance(c, dict) and
               'exclusion' in str(c.get('category', '')).lower()]
        other = [c for c in criteria if isinstance(c, dict) and c not in inc and c not in exc]

        if inc:
            lines.append("Inclusion Criteria:")
            for c in inc:
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"  - {text}")
            lines.append('')

        if exc:
            lines.append("Exclusion Criteria:")
            for c in exc:
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"  - {text}")
            lines.append('')

        if other:
            lines.append("Other Criteria:")
            for c in other:
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"  - {text}")

    return '\n'.join(lines)


def _compose_estimands(usdm: Dict) -> str:
    """Compose estimands subsection from USDM estimand entities."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    estimands = design.get('estimands', [])
    if not estimands:
        return ''

    lines = ['Estimands:']
    for i, est in enumerate(estimands):
        if not isinstance(est, dict):
            continue
        summary = est.get('summaryMeasure', est.get('summary', ''))
        treatment = est.get('treatment', '')
        lines.append(f"\n  Estimand {i+1}:")
        if summary:
            lines.append(f"    Summary Measure: {summary}")
        if treatment:
            lines.append(f"    Treatment: {treatment}")

        # Intercurrent events
        ices = est.get('intercurrentEvents', [])
        for ice in ices:
            if isinstance(ice, dict):
                name = ice.get('name', ice.get('intercurrentEventName', ''))
                strategy = ice.get('strategy', ice.get('intercurrentEventStrategy', ''))
                if name:
                    lines.append(f"    ICE: {name} — Strategy: {strategy}")

    return '\n'.join(lines)


def _compose_statistics(usdm: Dict) -> str:
    """Compose Section 9 content from SAP extension attributes."""
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # Collect SAP extensions by URL
    exts = design.get('extensionAttributes', [])
    sap_data: Dict[str, list] = {}
    for ext in exts:
        url = ext.get('url', '')
        if 'x-sap-' in url:
            key = url.rsplit('/', 1)[-1].replace('x-sap-', '')
            try:
                sap_data[key] = json.loads(ext.get('valueString', '[]'))
            except (json.JSONDecodeError, TypeError):
                pass

    # Also get analysisPopulations directly from studyDesign
    pops = design.get('analysisPopulations', [])

    lines = []

    # 9.1 Analysis Populations
    if pops:
        lines.append('Analysis Populations:')
        for p in pops:
            if not isinstance(p, dict):
                continue
            name = p.get('name', '')
            desc = p.get('populationDescription', p.get('text', ''))
            ptype = p.get('populationType', '')
            lines.append(f'  - **{name}** ({ptype}): {desc}')
        lines.append('')

    # 9.2 Statistical Methods
    methods = sap_data.get('statistical-methods', [])
    if methods:
        lines.append('Statistical Methods:')
        for m in methods:
            if not isinstance(m, dict):
                continue
            name = m.get('name', '')
            desc = m.get('description', '')
            endpoint = m.get('endpointName', '')
            stato = m.get('statoCode', '')
            alpha = m.get('alphaLevel', '')
            line = f'  - **{name}**'
            if stato:
                line += f' ({stato})'
            if endpoint:
                line += f' — {endpoint}'
            lines.append(line)
            if desc:
                lines.append(f'    {desc}')
            if alpha:
                lines.append(f'    Alpha level: {alpha}')
        lines.append('')

    # 9.3 Sample Size
    ss = sap_data.get('sample-size-calculations', [])
    if ss:
        lines.append('Sample Size and Power:')
        for calc in ss:
            if not isinstance(calc, dict):
                continue
            name = calc.get('name', '')
            desc = calc.get('description', '')
            n = calc.get('targetSampleSize', '')
            power = calc.get('power', '')
            alpha = calc.get('alpha', '')
            effect = calc.get('effectSize', '')
            dropout = calc.get('dropoutRate', '')
            lines.append(f'  - **{name}**')
            if desc:
                lines.append(f'    {desc}')
            details = []
            if n:
                details.append(f'N={n}')
            if power:
                details.append(f'Power={power}')
            if alpha:
                details.append(f'Alpha={alpha}')
            if effect:
                details.append(f'Effect size: {effect}')
            if dropout:
                details.append(f'Dropout: {dropout}')
            if details:
                lines.append(f'    {", ".join(details)}')
        lines.append('')

    # 9.4 Interim Analyses
    ia = sap_data.get('interim-analyses', [])
    if ia:
        lines.append('Interim Analyses:')
        for analysis in ia:
            if not isinstance(analysis, dict):
                continue
            name = analysis.get('name', '')
            desc = analysis.get('description', '')
            timing = analysis.get('timing', '')
            spending = analysis.get('spendingFunction', '')
            lines.append(f'  - **{name}**')
            if desc:
                lines.append(f'    {desc}')
            if timing:
                lines.append(f'    Timing: {timing}')
            if spending:
                lines.append(f'    Spending function: {spending}')
        lines.append('')

    # 9.5 Multiplicity Adjustments
    mult = sap_data.get('multiplicity-adjustments', [])
    if mult:
        lines.append('Multiplicity Adjustments:')
        for adj in mult:
            if not isinstance(adj, dict):
                continue
            name = adj.get('name', '')
            desc = adj.get('description', '')
            lines.append(f'  - **{name}**: {desc}')
        lines.append('')

    # 9.6 Sensitivity Analyses
    sens = sap_data.get('sensitivity-analyses', [])
    if sens:
        lines.append('Sensitivity Analyses:')
        for sa in sens:
            if not isinstance(sa, dict):
                continue
            name = sa.get('name', '')
            desc = sa.get('description', '')
            lines.append(f'  - **{name}**: {desc}')
        lines.append('')

    # 9.7 Subgroup Analyses
    sub = sap_data.get('subgroup-analyses', [])
    if sub:
        lines.append('Subgroup Analyses:')
        for sg in sub:
            if not isinstance(sg, dict):
                continue
            name = sg.get('name', '')
            desc = sg.get('description', '')
            var = sg.get('subgroupVariable', '')
            lines.append(f'  - **{name}** (variable: {var}): {desc}')
        lines.append('')

    # 9.8 Data Handling Rules
    rules = sap_data.get('data-handling-rules', [])
    if rules:
        lines.append('Data Handling Rules:')
        for r in rules:
            if not isinstance(r, dict):
                continue
            name = r.get('name', '')
            rule = r.get('rule', '')
            lines.append(f'  - **{name}**: {rule}')
        lines.append('')

    return '\n'.join(lines)


def _compose_discontinuation(usdm: Dict) -> str:
    """Compose Section 7 content from narrative text containing discontinuation info.

    Many protocols embed discontinuation/withdrawal rules within the Study
    Intervention section (§6) or Study Population section (§5). This
    composer searches all narrative sections for discontinuation-related
    content and aggregates it.
    """
    import re as _re

    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])
    all_items = nc + nci

    discontinuation_keywords = [
        'discontinu', 'withdraw', 'dropout', 'drop-out', 'drop out',
        'early termination', 'stopping rule', 'lost to follow',
        'premature', 'removal from study',
    ]

    pattern = _re.compile('|'.join(discontinuation_keywords), _re.IGNORECASE)

    fragments = []
    for item in all_items:
        if not isinstance(item, dict):
            continue
        title = item.get('sectionTitle', item.get('name', ''))
        text = item.get('text', '')
        if not text or text == title:
            continue

        # Check if title or text mentions discontinuation
        if pattern.search(title) or pattern.search(text[:500]):
            source = item.get('sectionNumber', '')
            header = f'{source} {title}'.strip() if source else title
            fragments.append(f'**{header}**\n{text}')

    if not fragments:
        return ''

    return '\n\n'.join(fragments)


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

        # TOC placeholder
        doc.add_heading('Table of Contents', level=1)
        p = doc.add_paragraph('[Table of Contents — update field after opening in Word]')
        p.italic = True
        doc.add_page_break()

        # Get or compute M11 mapping
        if m11_mapping is None:
            m11_mapping = _compute_m11_mapping(usdm)

        m11_sections = m11_mapping.get('sections', {})

        # Entity composers for enrichment
        entity_composers = {
            '3': _compose_objectives,
            '4': _compose_study_design,
            '5': _compose_eligibility,
            '7': _compose_discontinuation,
            '9': _compose_statistics,
        }

        # Render each M11 section
        from extraction.narrative.m11_mapper import M11_TEMPLATE
        sections_rendered = 0
        sections_with_content = 0
        total_words = 0

        for m11 in M11_TEMPLATE:
            sec_data = m11_sections.get(m11.number, {})
            narrative_text = sec_data.get('text', '')
            has_content = bool(narrative_text.strip())

            # Add M11 section heading
            doc.add_heading(f'{m11.number}. {m11.title}', level=1)

            # Source attribution (small note)
            sources = sec_data.get('sourceSections', [])
            if sources:
                source_list = ', '.join(
                    f"§{s['protocolSection']} {s.get('protocolTitle', '')}"
                    for s in sources
                )
                p = doc.add_paragraph()
                run = p.add_run(f'[Source: {source_list}]')
                run.italic = True
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(128, 128, 128)

            # Narrative text
            if narrative_text.strip():
                _add_narrative_text(doc, narrative_text)
                total_words += len(narrative_text.split())
                sections_with_content += 1

            # Entity-composed content (supplement or replace empty narrative)
            composer = entity_composers.get(m11.number)
            if composer:
                composed = composer(usdm)
                if composed.strip():
                    if narrative_text.strip():
                        doc.add_paragraph('')  # separator
                        p = doc.add_paragraph()
                        run = p.add_run('[Auto-composed from USDM entities]')
                        run.italic = True
                        run.font.size = Pt(9)
                        run.font.color.rgb = RGBColor(128, 128, 128)
                    _add_narrative_text(doc, composed)
                    total_words += len(composed.split())
                    if not has_content:
                        sections_with_content += 1

            # Estimands for section 3
            if m11.number == '3':
                estimand_text = _compose_estimands(usdm)
                if estimand_text:
                    doc.add_heading('Estimand Framework', level=2)
                    _add_narrative_text(doc, estimand_text)

            # Empty section notice
            if not narrative_text.strip() and not (composer and composer(usdm).strip()):
                p = doc.add_paragraph()
                run = p.add_run('[Section content not yet available]')
                run.italic = True
                run.font.color.rgb = RGBColor(192, 0, 0)

            sections_rendered += 1

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

    except Exception as e:
        logger.error(f"M11 DOCX rendering failed: {e}")
        result.error = str(e)

    return result


def _add_narrative_text(doc: Document, text: str) -> None:
    """Add narrative text to the document, handling basic formatting."""
    # Split into paragraphs
    paragraphs = text.split('\n\n')
    for para_text in paragraphs:
        para_text = para_text.strip()
        if not para_text:
            continue

        # Handle bold markers (**text**)
        if '**' in para_text:
            p = doc.add_paragraph()
            parts = re.split(r'\*\*(.*?)\*\*', para_text)
            for i, part in enumerate(parts):
                if not part:
                    continue
                run = p.add_run(part)
                if i % 2 == 1:  # odd indices are bold content
                    run.bold = True
        # Handle bullet points
        elif para_text.startswith('  - ') or para_text.startswith('- '):
            for line in para_text.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    doc.add_paragraph(line[2:], style='List Bullet')
                elif line:
                    doc.add_paragraph(line)
        # Handle sub-headings (lines that look like headings within text)
        elif ':' in para_text and len(para_text) < 80 and not para_text.endswith('.'):
            # Could be a sub-heading like "Inclusion Criteria:"
            lines = para_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.endswith(':') and len(line) < 60:
                    doc.add_heading(line.rstrip(':'), level=2)
                elif line:
                    doc.add_paragraph(line)
        else:
            # Regular paragraph — preserve line breaks within
            lines = para_text.split('\n')
            p = doc.add_paragraph()
            for i, line in enumerate(lines):
                if i > 0:
                    p.add_run('\n')
                p.add_run(line.strip())


def _compute_m11_mapping(usdm: Dict) -> Dict:
    """Compute M11 mapping from USDM narrative data on the fly."""
    from extraction.narrative.m11_mapper import map_sections_to_m11, build_m11_narrative

    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    narrative_contents = version.get('narrativeContents', [])

    # Build section dicts
    sec_dicts = []
    sec_texts = {}
    for nc in narrative_contents:
        if not isinstance(nc, dict):
            continue
        num = nc.get('sectionNumber', '')
        title = nc.get('sectionTitle', nc.get('name', ''))
        text = nc.get('text', '')
        sec_dicts.append({
            'number': num,
            'title': title,
            'type': '',
        })
        if text and text != title:
            sec_texts[num] = text

    if not sec_dicts:
        return {'sections': {}}

    mapping = map_sections_to_m11(sec_dicts)
    m11_narrative = build_m11_narrative(sec_dicts, sec_texts, mapping)

    return {
        'coverage': f"{mapping.m11_covered}/{mapping.m11_total}",
        'requiredCoverage': f"{mapping.m11_required_covered}/{mapping.m11_required_total}",
        'sections': m11_narrative,
    }
