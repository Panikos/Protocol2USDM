"""
M11 Section Mapper — maps protocol-native section structure to ICH M11 template.

The ICH M11 template defines 12 canonical sections for clinical protocol documents.
Protocol PDFs use their own numbering which may not match M11 directly.
This module provides deterministic title-based semantic matching to map
protocol sections → M11 sections, enabling M11-compliant document generation.

Reference: ICH M11 Technical Specification (Step 4, 2023)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class M11Section:
    """Canonical M11 template section definition."""
    number: str           # "1" through "12"
    title: str            # Official M11 section title
    required: bool        # Whether this section is required per M11
    keywords: List[str]   # Keywords for matching protocol sections
    aliases: List[str]    # Alternative section titles commonly used


# ICH M11 Template — 12 canonical sections
M11_TEMPLATE: List[M11Section] = [
    M11Section(
        number="1",
        title="Protocol Summary",
        required=True,
        keywords=["synopsis", "summary", "protocol summary"],
        aliases=["synopsis", "protocol synopsis", "study synopsis",
                 "clinical study synopsis", "protocol summary"],
    ),
    M11Section(
        number="2",
        title="Introduction",
        required=True,
        keywords=["introduction", "background", "rationale"],
        aliases=["introduction", "background and rationale",
                 "study rationale", "introduction and rationale"],
    ),
    M11Section(
        number="3",
        title="Study Objectives and Endpoints",
        required=True,
        keywords=["objective", "endpoint", "primary objective",
                  "secondary objective", "estimand"],
        aliases=["study objectives", "objectives and endpoints",
                 "study objectives and endpoints",
                 "objectives, endpoints, and estimands"],
    ),
    M11Section(
        number="4",
        title="Study Design",
        required=True,
        keywords=["study design", "design", "overall design",
                  "study scheme", "randomization", "blinding"],
        aliases=["study design", "overall study design",
                 "study design and plan", "investigational plan"],
    ),
    M11Section(
        number="5",
        title="Study Population",
        required=True,
        keywords=["population", "eligibility", "inclusion", "exclusion",
                  "subject selection", "patient population"],
        aliases=["study population", "selection of study population",
                 "eligibility criteria", "selection of subjects",
                 "selection and withdrawal of subjects"],
    ),
    M11Section(
        number="6",
        title="Study Intervention",
        required=True,
        keywords=["intervention", "treatment", "investigational product",
                  "study drug", "dosage", "dosing", "medication",
                  "concomitant", "prohibited"],
        aliases=["study intervention", "study treatment",
                 "investigational product", "study drug",
                 "description of study treatment",
                 "treatments administered"],
    ),
    M11Section(
        number="7",
        title="Discontinuation of Study Intervention and Participant Discontinuation/Withdrawal",
        required=True,
        keywords=["discontinuation", "withdrawal", "dropout",
                  "early termination", "stopping rules", "lost to follow"],
        aliases=["discontinuation", "withdrawal",
                 "discontinuation of study treatment",
                 "discontinuation of study intervention",
                 "subject discontinuation", "participant withdrawal",
                 "premature withdrawal", "subject withdrawal"],
    ),
    M11Section(
        number="8",
        title="Study Assessments and Procedures",
        required=True,
        keywords=["assessment", "procedure", "schedule of activities",
                  "study procedure", "efficacy assessment",
                  "safety assessment", "laboratory", "vital signs",
                  "physical exam", "pharmacokinetic"],
        aliases=["study assessments and procedures",
                 "study procedures", "study assessments",
                 "schedule of assessments", "study evaluations"],
    ),
    M11Section(
        number="9",
        title="Statistical Considerations",
        required=True,
        keywords=["statistic", "statistical", "sample size", "analysis",
                  "power calculation", "interim analysis",
                  "multiplicity", "missing data"],
        aliases=["statistical considerations",
                 "statistical methods", "statistical analysis",
                 "statistical analysis plan", "data analysis"],
    ),
    M11Section(
        number="10",
        title="Supporting Documentation",
        required=False,
        keywords=["supporting", "administration", "regulatory",
                  "ethical", "ethics", "irb", "iec", "informed consent",
                  "data handling", "quality control", "monitoring",
                  "adverse event", "serious adverse event",
                  "safety reporting", "pharmacovigilance"],
        aliases=["supporting documentation",
                 "study administration", "administrative procedures",
                 "regulatory and ethical considerations",
                 "ethical considerations", "study governance",
                 "general considerations"],
    ),
    M11Section(
        number="11",
        title="References",
        required=False,
        keywords=["reference", "bibliography"],
        aliases=["references", "bibliography", "literature references"],
    ),
    M11Section(
        number="12",
        title="Appendices",
        required=False,
        keywords=["appendix", "appendices", "supplement", "attachment"],
        aliases=["appendices", "appendix", "supplements", "attachments"],
    ),
]


@dataclass
class M11MappingResult:
    """Result of mapping protocol sections to M11 template."""
    # Maps M11 section number → list of (protocol_section_number, score) tuples
    mappings: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)
    # Protocol sections that couldn't be mapped to any M11 section
    unmapped: List[str] = field(default_factory=list)
    # Summary statistics
    m11_covered: int = 0
    m11_required_covered: int = 0
    m11_total: int = 12
    m11_required_total: int = 9


def map_sections_to_m11(
    sections: List[Dict],
) -> M11MappingResult:
    """
    Map protocol-native sections to ICH M11 template sections.
    
    Uses a multi-pass approach:
      1. Exact title match against known aliases
      2. Keyword overlap scoring
      3. Section type matching (from narrative extraction)
    
    Args:
        sections: List of section dicts with 'number', 'title', 'type' keys
        
    Returns:
        M11MappingResult with mappings and coverage stats
    """
    result = M11MappingResult()
    
    # Track which protocol sections have been assigned
    assigned: set = set()
    
    # Pass 1: Exact/near-exact title matches
    for m11 in M11_TEMPLATE:
        best_matches = []
        for sec in sections:
            sec_num = sec.get('number', '')
            sec_title = sec.get('title', '').lower().strip()
            if not sec_title:
                continue
            
            # Check alias matches
            for alias in m11.aliases:
                if _fuzzy_title_match(sec_title, alias):
                    best_matches.append((sec_num, 0.95))
                    break
        
        if best_matches:
            result.mappings[m11.number] = best_matches
            for sec_num, _ in best_matches:
                assigned.add(sec_num)
    
    # Pass 2: Keyword scoring for unmapped M11 sections
    for m11 in M11_TEMPLATE:
        if m11.number in result.mappings:
            continue
        
        scored = []
        for sec in sections:
            sec_num = sec.get('number', '')
            if sec_num in assigned:
                continue
            
            score = _keyword_score(sec, m11)
            if score > 0.3:
                scored.append((sec_num, score))
        
        if scored:
            scored.sort(key=lambda x: -x[1])
            result.mappings[m11.number] = scored[:3]  # top 3 matches
            for sec_num, _ in scored[:1]:  # only assign top match
                assigned.add(sec_num)
    
    # Pass 3: Section type matching for still-unmapped M11 sections
    type_to_m11 = {
        'synopsis': '1', 'introduction': '2', 'objectives': '3',
        'study design': '4', 'population': '5', 'eligibility': '5',
        'treatment': '6', 'discontinuation': '7',
        'study procedures': '8', 'assessments': '8',
        'statistics': '9', 'safety': '10', 'ethics': '10',
        'references': '11', 'appendix': '12',
    }
    
    for sec in sections:
        sec_num = sec.get('number', '')
        sec_type = sec.get('type', '').lower()
        if sec_num in assigned or not sec_type:
            continue
        
        m11_num = type_to_m11.get(sec_type)
        if m11_num and m11_num not in result.mappings:
            result.mappings[m11_num] = [(sec_num, 0.6)]
            assigned.add(sec_num)
    
    # Collect unmapped protocol sections
    all_sec_nums = {sec.get('number', '') for sec in sections if sec.get('number')}
    result.unmapped = sorted(all_sec_nums - assigned)
    
    # Calculate coverage
    result.m11_covered = len(result.mappings)
    result.m11_required_covered = sum(
        1 for m11 in M11_TEMPLATE
        if m11.required and m11.number in result.mappings
    )
    
    logger.info(
        f"M11 mapping: {result.m11_covered}/{result.m11_total} sections covered "
        f"({result.m11_required_covered}/{result.m11_required_total} required)"
    )
    
    return result


def _fuzzy_title_match(title: str, alias: str) -> bool:
    """Check if a section title is a fuzzy match for an alias."""
    title = title.lower().strip()
    alias = alias.lower().strip()
    
    # Exact match
    if title == alias:
        return True
    
    # Title contains alias or vice versa
    if alias in title or title in alias:
        return True
    
    # Word overlap — require ≥75% shared words
    title_words = set(re.findall(r'\w+', title))
    alias_words = set(re.findall(r'\w+', alias))
    if not title_words or not alias_words:
        return False
    
    overlap = len(title_words & alias_words)
    min_len = min(len(title_words), len(alias_words))
    if min_len > 0 and overlap / min_len >= 0.75:
        return True
    
    return False


def _keyword_score(section: Dict, m11: M11Section) -> float:
    """Score how well a protocol section matches an M11 section by keyword overlap."""
    sec_title = section.get('title', '').lower()
    sec_type = section.get('type', '').lower()
    combined = f"{sec_title} {sec_type}"
    
    if not combined.strip():
        return 0.0
    
    matches = sum(1 for kw in m11.keywords if kw in combined)
    if not matches:
        return 0.0
    
    return min(1.0, matches / max(2, len(m11.keywords) * 0.3))


def build_m11_narrative(
    sections: List[Dict],
    section_texts: Dict[str, str],
    mapping: M11MappingResult,
) -> Dict[str, Dict]:
    """
    Build an M11-organized narrative structure from mapped sections.
    
    Returns a dict mapping M11 section number → {title, text, source_sections}
    """
    m11_narrative: Dict[str, Dict] = {}
    
    # Build lookup from protocol section number → section data
    sec_lookup = {s.get('number', ''): s for s in sections}
    
    for m11 in M11_TEMPLATE:
        mapped = mapping.mappings.get(m11.number, [])
        
        # Gather text and source info from all mapped protocol sections
        combined_texts = []
        source_sections = []
        
        for sec_num, score in mapped:
            sec_data = sec_lookup.get(sec_num, {})
            text = section_texts.get(sec_num, '')
            source_title = sec_data.get('title', sec_num)
            source_sections.append({
                'protocolSection': sec_num,
                'protocolTitle': source_title,
                'matchScore': round(score, 2),
                'hasText': bool(text),
            })
            if text:
                combined_texts.append(text)
        
        m11_narrative[m11.number] = {
            'm11Number': m11.number,
            'm11Title': m11.title,
            'required': m11.required,
            'text': '\n\n'.join(combined_texts) if combined_texts else '',
            'hasContent': bool(combined_texts),
            'sourceSections': source_sections,
        }
    
    return m11_narrative
