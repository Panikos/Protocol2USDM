"""
M11 ↔ USDM Mapping Configuration Loader

Single source of truth for the M11 template ↔ USDM entity mapping.
All consumers (mapper, renderer, conformance validator) read from
the YAML config via this module instead of hardcoding their own lists.

Usage:
    from core.m11_mapping_config import get_m11_config

    config = get_m11_config()
    for sec in config.sections():
        print(sec.number, sec.title, sec.required)
"""

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "m11_usdm_mapping.yaml")


# ---------------------------------------------------------------------------
# Data classes — typed views over the YAML config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class M11Subheading:
    """A sub-heading within an M11 section."""
    number: str
    title: str
    level: int
    keywords: Tuple[str, ...]


@dataclass(frozen=True)
class ExtractorGap:
    """A known gap in extractor coverage for an M11 section."""
    field_name: str
    status: str
    priority: str
    description: str = ""


@dataclass(frozen=True)
class SynopsisField:
    """A structured field in the §1.1.2 Overall Design synopsis table."""
    name: str
    conformance: str  # "Required" | "Optional"
    usdm_path: Optional[str]
    check: str


@dataclass(frozen=True)
class TitlePageField:
    """A field on the M11 title page."""
    name: str
    conformance: str
    usdm_path: Optional[str]
    check: str
    c_code: str = ""


@dataclass(frozen=True)
class PromotionRule:
    """A rule for promoting extension data back into core USDM."""
    source: str
    target: str
    condition: str
    description: str


@dataclass(frozen=True)
class RegulatoryReference:
    """A reference to a regulatory framework applicable to an M11 section."""
    framework: str  # Key into regulatory_frameworks dict
    scope: str      # What aspect of the framework applies


@dataclass(frozen=True)
class M11SectionConfig:
    """Complete configuration for a single M11 section."""
    number: str
    title: str
    required: bool
    composer: Optional[str]
    extractor_phase: Optional[str]
    extractor_strategy: Optional[str]
    section_type_filter: Tuple[str, ...]
    keywords: Tuple[str, ...]
    aliases: Tuple[str, ...]
    subheadings: Tuple[M11Subheading, ...]
    usdm_entities: Tuple[Dict[str, Any], ...]
    extractor_gaps: Tuple[ExtractorGap, ...]
    synopsis_fields: Tuple[SynopsisField, ...]
    promotion_rules: Tuple[PromotionRule, ...]
    regulatory_references: Tuple[RegulatoryReference, ...] = ()


@dataclass
class M11MappingConfig:
    """
    Parsed M11 ↔ USDM mapping configuration.

    This is the single source of truth consumed by:
      - m11_mapper.py       (keywords, aliases, subheadings)
      - m11_renderer.py     (composer names, entity paths)
      - m11_conformance.py  (synopsis fields, title page fields, required sections)
      - orchestrator.py     (promotion rules)
    """
    schema_version: str
    m11_version: str
    usdm_version: str
    _sections: Dict[str, M11SectionConfig] = field(default_factory=dict)
    _title_page_fields: Tuple[TitlePageField, ...] = ()
    _extractor_coverage: Dict[str, Any] = field(default_factory=dict)
    _regulatory_frameworks: Dict[str, Any] = field(default_factory=dict)

    # --- Section accessors ---

    def sections(self) -> List[M11SectionConfig]:
        """All M11 sections in order (1–14)."""
        return [self._sections[k] for k in sorted(
            self._sections.keys(),
            key=lambda x: (len(x), x),  # sort "1"<"2"<…<"9"<"10"<"11"…
        )]

    def section(self, number: str) -> Optional[M11SectionConfig]:
        """Get a single section by number."""
        return self._sections.get(number)

    def required_sections(self) -> List[M11SectionConfig]:
        """Only sections where required=true."""
        return [s for s in self.sections() if s.required]

    # --- Title page ---

    def title_page_fields(self) -> List[TitlePageField]:
        return list(self._title_page_fields)

    # --- Synopsis fields (from §1 config) ---

    def synopsis_fields(self) -> List[SynopsisField]:
        sec1 = self._sections.get("1")
        return list(sec1.synopsis_fields) if sec1 else []

    # --- Mapper-compatible accessors ---

    def get_m11_template(self) -> List[Dict[str, Any]]:
        """Return M11_TEMPLATE-compatible list of dicts for the mapper."""
        result = []
        for sec in self.sections():
            result.append({
                "number": sec.number,
                "title": sec.title,
                "required": sec.required,
                "keywords": list(sec.keywords),
                "aliases": list(sec.aliases),
            })
        return result

    def get_m11_subheadings(self) -> Dict[str, List[Tuple[str, str, int, List[str]]]]:
        """Return M11_SUBHEADINGS-compatible dict for the mapper."""
        result: Dict[str, List[Tuple[str, str, int, List[str]]]] = {}
        for sec in self.sections():
            if sec.subheadings:
                result[sec.number] = [
                    (sh.number, sh.title, sh.level, list(sh.keywords))
                    for sh in sec.subheadings
                ]
        return result

    # --- Conformance-compatible accessors ---

    def get_m11_required_sections(self) -> List[Tuple[str, str, bool]]:
        """Return M11_REQUIRED_SECTIONS-compatible list for conformance."""
        return [(s.number, s.title, s.required) for s in self.sections()]

    def get_synopsis_fields_dicts(self) -> List[Dict[str, str]]:
        """Return SYNOPSIS_FIELDS-compatible list of dicts for conformance."""
        return [
            {"name": f.name, "conformance": f.conformance, "check": f.check}
            for f in self.synopsis_fields()
        ]

    def get_title_page_fields_dicts(self) -> List[Dict[str, str]]:
        """Return TITLE_PAGE_FIELDS-compatible list of dicts for conformance."""
        return [
            {"name": f.name, "conformance": f.conformance,
             "check": f.check, "cCode": f.c_code}
            for f in self._title_page_fields
        ]

    # --- Extractor coverage ---

    def get_extractor_coverage(self) -> Dict[str, Any]:
        return dict(self._extractor_coverage)

    def get_extractor_gaps(self) -> List[Dict[str, str]]:
        """All extractor gaps across all sections, for reporting."""
        gaps = []
        for sec in self.sections():
            for gap in sec.extractor_gaps:
                gaps.append({
                    "section": sec.number,
                    "section_title": sec.title,
                    "field": gap.field_name,
                    "status": gap.status,
                    "priority": gap.priority,
                    "description": gap.description,
                })
        return gaps

    # --- Promotion rules ---

    def get_promotion_rules(self) -> List[Dict[str, str]]:
        """All promotion rules across all sections."""
        rules = []
        for sec in self.sections():
            for rule in sec.promotion_rules:
                rules.append({
                    "section": sec.number,
                    "source": rule.source,
                    "target": rule.target,
                    "condition": rule.condition,
                    "description": rule.description,
                })
        return rules

    # --- Regulatory frameworks ---

    def get_regulatory_frameworks(self) -> Dict[str, Any]:
        """All regulatory frameworks defined in the config."""
        return dict(self._regulatory_frameworks)

    def get_framework(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a single regulatory framework by key (e.g. 'ich_e9_r1')."""
        return self._regulatory_frameworks.get(key)

    def get_section_regulatory_refs(self, section_number: str) -> List[Dict[str, str]]:
        """Get regulatory references for a specific M11 section."""
        sec = self._sections.get(section_number)
        if not sec:
            return []
        result = []
        for ref in sec.regulatory_references:
            fw = self._regulatory_frameworks.get(ref.framework, {})
            result.append({
                "framework": ref.framework,
                "name": fw.get("name", ref.framework),
                "scope": ref.scope,
                "version": fw.get("version", ""),
            })
        return result

    # --- Composer lookup ---

    def get_composer_map(self) -> Dict[str, str]:
        """Return section_number → composer_function_name mapping."""
        return {
            sec.number: sec.composer
            for sec in self.sections()
            if sec.composer
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_config(raw: Dict[str, Any]) -> M11MappingConfig:
    """Parse raw YAML dict into typed M11MappingConfig."""

    sections: Dict[str, M11SectionConfig] = {}

    for sec_num, sec_data in raw.get("sections", {}).items():
        sec_num = str(sec_num)

        # Parse subheadings
        subheadings = tuple(
            M11Subheading(
                number=sh["number"],
                title=sh["title"],
                level=sh.get("level", 2),
                keywords=tuple(sh.get("keywords", [])),
            )
            for sh in sec_data.get("subheadings", [])
        )

        # Parse extractor gaps
        gaps = tuple(
            ExtractorGap(
                field_name=g.get("field", ""),
                status=g.get("status", "unknown"),
                priority=g.get("priority", ""),
                description=g.get("description", ""),
            )
            for g in sec_data.get("extractor_gaps", [])
        )

        # Parse synopsis fields (only on §1)
        syn_fields = tuple(
            SynopsisField(
                name=sf["name"],
                conformance=sf["conformance"],
                usdm_path=sf.get("usdm_path"),
                check=sf["check"],
            )
            for sf in sec_data.get("synopsis_fields", [])
        )

        # Parse promotion rules
        promo_rules = tuple(
            PromotionRule(
                source=pr["source"],
                target=pr["target"],
                condition=pr.get("condition", "target_empty"),
                description=pr.get("description", ""),
            )
            for pr in sec_data.get("promotion_rules", [])
        )

        # Parse regulatory references
        reg_refs = tuple(
            RegulatoryReference(
                framework=rr.get("framework", ""),
                scope=rr.get("scope", ""),
            )
            for rr in sec_data.get("regulatory_references", [])
        )

        sections[sec_num] = M11SectionConfig(
            number=sec_num,
            title=sec_data.get("title", ""),
            required=sec_data.get("required", False),
            composer=sec_data.get("composer"),
            extractor_phase=sec_data.get("extractor_phase"),
            extractor_strategy=sec_data.get("extractor_strategy"),
            section_type_filter=tuple(sec_data.get("section_type_filter", [])),
            keywords=tuple(sec_data.get("keywords", [])),
            aliases=tuple(sec_data.get("aliases", [])),
            subheadings=subheadings,
            usdm_entities=tuple(sec_data.get("usdm_entities", [])),
            extractor_gaps=gaps,
            synopsis_fields=syn_fields,
            promotion_rules=promo_rules,
            regulatory_references=reg_refs,
        )

    # Parse title page fields
    tp_fields = tuple(
        TitlePageField(
            name=tp["name"],
            conformance=tp["conformance"],
            usdm_path=tp.get("usdm_path"),
            check=tp["check"],
            c_code=tp.get("cCode", ""),
        )
        for tp in raw.get("title_page_fields", [])
    )

    return M11MappingConfig(
        schema_version=raw.get("schema_version", "1.0"),
        m11_version=raw.get("m11_version", ""),
        usdm_version=raw.get("usdm_version", ""),
        _sections=sections,
        _title_page_fields=tp_fields,
        _extractor_coverage=raw.get("extractor_coverage", {}),
        _regulatory_frameworks=raw.get("regulatory_frameworks", {}),
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

_CANONICAL_SECTIONS = {str(i) for i in range(1, 15)}  # "1" .. "14"
_VALID_CONFORMANCE = {"Required", "Optional", "Conditional"}


class M11ConfigValidationError(Exception):
    """Raised when the M11 mapping YAML fails structural validation."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(
            f"M11 mapping config has {len(errors)} validation error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def validate_m11_config(raw: Dict[str, Any]) -> List[str]:
    """Validate raw YAML dict against structural rules.

    Returns a list of error strings (empty = valid).
    """
    errors: List[str] = []

    # -- Top-level keys --
    for key in ("schema_version", "m11_version", "usdm_version"):
        if key not in raw:
            errors.append(f"Missing top-level key: '{key}'")

    sections = raw.get("sections")
    if not isinstance(sections, dict):
        errors.append("'sections' must be a mapping")
        return errors  # can't continue without sections

    # -- Canonical section coverage --
    present = {str(k) for k in sections.keys()}
    missing = _CANONICAL_SECTIONS - present
    if missing:
        errors.append(f"Missing M11 sections: {sorted(missing, key=lambda x: (len(x), x))}")

    # -- Per-section validation --
    for sec_num, sec_data in sections.items():
        sec_num = str(sec_num)
        prefix = f"sections.{sec_num}"

        if not isinstance(sec_data, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue

        # Required fields
        if "title" not in sec_data:
            errors.append(f"{prefix}: missing 'title'")
        if "required" not in sec_data:
            errors.append(f"{prefix}: missing 'required'")
        elif not isinstance(sec_data["required"], bool):
            errors.append(f"{prefix}.required: must be boolean")

        # Keywords and aliases must be lists
        for list_key in ("keywords", "aliases"):
            val = sec_data.get(list_key)
            if val is not None and not isinstance(val, list):
                errors.append(f"{prefix}.{list_key}: must be a list")

        # Subheadings validation
        for i, sh in enumerate(sec_data.get("subheadings", [])):
            sh_prefix = f"{prefix}.subheadings[{i}]"
            if not isinstance(sh, dict):
                errors.append(f"{sh_prefix}: must be a mapping")
                continue
            for req in ("number", "title"):
                if req not in sh:
                    errors.append(f"{sh_prefix}: missing '{req}'")
            if "level" in sh and not isinstance(sh["level"], int):
                errors.append(f"{sh_prefix}.level: must be an integer")

        # Synopsis fields (only expected on §1)
        for i, sf in enumerate(sec_data.get("synopsis_fields", [])):
            sf_prefix = f"{prefix}.synopsis_fields[{i}]"
            if not isinstance(sf, dict):
                errors.append(f"{sf_prefix}: must be a mapping")
                continue
            for req in ("name", "conformance", "check"):
                if req not in sf:
                    errors.append(f"{sf_prefix}: missing '{req}'")
            conf = sf.get("conformance", "")
            if conf and conf not in _VALID_CONFORMANCE:
                errors.append(f"{sf_prefix}.conformance: '{conf}' not in {_VALID_CONFORMANCE}")

    # -- Title page fields --
    for i, tp in enumerate(raw.get("title_page_fields", [])):
        tp_prefix = f"title_page_fields[{i}]"
        if not isinstance(tp, dict):
            errors.append(f"{tp_prefix}: must be a mapping")
            continue
        for req in ("name", "conformance", "check"):
            if req not in tp:
                errors.append(f"{tp_prefix}: missing '{req}'")
        conf = tp.get("conformance", "")
        if conf and conf not in _VALID_CONFORMANCE:
            errors.append(f"{tp_prefix}.conformance: '{conf}' not in {_VALID_CONFORMANCE}")

    # -- Regulatory frameworks --
    frameworks = raw.get("regulatory_frameworks")
    if frameworks is not None:
        if not isinstance(frameworks, dict):
            errors.append("'regulatory_frameworks' must be a mapping")
        else:
            for fw_key, fw_data in frameworks.items():
                fw_prefix = f"regulatory_frameworks.{fw_key}"
                if not isinstance(fw_data, dict):
                    errors.append(f"{fw_prefix}: must be a mapping")
                    continue
                if "name" not in fw_data:
                    errors.append(f"{fw_prefix}: missing 'name'")

    return errors


def load_m11_config(path: str = _CONFIG_PATH) -> M11MappingConfig:
    """Load, validate, and parse the M11 ↔ USDM mapping config from YAML.

    Raises M11ConfigValidationError if the YAML is structurally invalid.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    errors = validate_m11_config(raw)
    if errors:
        raise M11ConfigValidationError(errors)

    config = _parse_config(raw)
    logger.debug(
        f"Loaded M11 mapping config: {len(config.sections())} sections, "
        f"USDM {config.usdm_version}"
    )
    return config


@lru_cache(maxsize=1)
def get_m11_config() -> M11MappingConfig:
    """Get the cached M11 mapping config (singleton)."""
    return load_m11_config()
