"""
Centralized Code Registry — Single Source of Truth for all USDM CT codes.

Loads codelists from the pre-generated ``core/reference_data/usdm_ct.json``
(derived from the official USDM_CT.xlsx) and supplements them with
EVS-verified NCI Thesaurus codes for fields that have no USDM CT codelist.

Architecture
------------
1. **USDM CT codelists** (25 codelists, 125 terms) — loaded from JSON at
   import time.  These are the authoritative source for coded USDM fields.
2. **Supplementary codelists** — EVS-verified NCI codes for fields that
   have no USDM CT codelist (e.g. studyPhase, blindingSchema, armType).
3. **EVS fallback** — for codes not in either source, the ``EVSClient``
   can be used at extraction time to look up codes dynamically.
4. **CDISC API stub** — placeholder for future CDISC Library API
   integration when the API becomes available.

Usage
-----
    from core.code_registry import registry

    # Get a codelist
    cl = registry.get_codelist("Objective.level")
    # → CodeList(code="C188725", terms=[...], extensible=False)

    # Look up a code
    code = registry.lookup("Objective.level", "C85826")
    # → CodeTerm(code="C85826", decode="Primary Objective", ...)

    # Fuzzy match from free text
    code = registry.match("Objective.level", "primary")
    # → CodeTerm(code="C85826", decode="Primary Objective", ...)

    # Build a USDM Code dict
    d = registry.make_code("Objective.level", "C85826")
    # → {"code": "C85826", "codeSystem": "...", "decode": "Primary Objective", ...}

    # Get all options for a UI dropdown
    opts = registry.options("Objective.level")
    # → [{"code": "C85826", "decode": "Primary Objective"}, ...]

Regeneration
------------
    python scripts/generate_code_registry.py   # xlsx → JSON + TS
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodeTerm:
    """A single coded term within a codelist."""
    code: str
    decode: str
    definition: Optional[str] = None
    synonyms: Optional[str] = None


@dataclass
class CodeList:
    """A codelist (set of allowed coded values for a USDM attribute)."""
    codelist_code: str
    entity: str
    attribute: str
    extensible: bool
    terms: List[CodeTerm] = field(default_factory=list)
    source: str = "USDM_CT"  # "USDM_CT" | "NCI_EVS" | "CDISC_API"

    @property
    def key(self) -> str:
        return f"{self.entity}.{self.attribute}"

    def lookup(self, code: str) -> Optional[CodeTerm]:
        """Find a term by its C-code."""
        for t in self.terms:
            if t.code == code:
                return t
        return None

    def match(self, text: str) -> Optional[CodeTerm]:
        """Fuzzy-match a term from free text (case-insensitive)."""
        if not text:
            return None
        text_lower = text.lower().strip()
        # Exact decode match
        for t in self.terms:
            if t.decode.lower() == text_lower:
                return t
        # Partial match
        for t in self.terms:
            if text_lower in t.decode.lower() or t.decode.lower() in text_lower:
                return t
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_CODE_SYSTEM = "http://www.cdisc.org"
_CODE_SYSTEM_VERSION = "2024-09-27"

# Path to the pre-generated JSON (from USDM_CT.xlsx)
_JSON_PATH = Path(__file__).parent / "reference_data" / "usdm_ct.json"


class CodeRegistry:
    """
    Central registry of all USDM controlled terminology codelists.

    Loaded once at import time from the pre-generated JSON.
    Supplemented with EVS-verified NCI codes for fields without a
    USDM CT codelist.
    """

    def __init__(self) -> None:
        self._codelists: Dict[str, CodeList] = {}
        self._aliases: Dict[str, str] = {}  # alias → canonical key
        self._load_usdm_ct()
        self._load_supplementary()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_usdm_ct(self) -> None:
        """Load codelists from the pre-generated JSON."""
        if not _JSON_PATH.exists():
            logger.warning(
                "usdm_ct.json not found at %s — run scripts/generate_code_registry.py",
                _JSON_PATH,
            )
            return
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, cl_data in data.items():
            terms = [
                CodeTerm(
                    code=t["code"],
                    decode=t["decode"],
                    definition=t.get("definition"),
                    synonyms=t.get("synonyms"),
                )
                for t in cl_data["terms"]
            ]
            self._codelists[key] = CodeList(
                codelist_code=cl_data["codelistCode"],
                entity=cl_data["entity"],
                attribute=cl_data["attribute"],
                extensible=cl_data["extensible"],
                terms=terms,
                source="USDM_CT",
            )
        logger.debug("Loaded %d USDM CT codelists from %s", len(self._codelists), _JSON_PATH)

    def _load_supplementary(self) -> None:
        """
        Add EVS-verified codelists for fields that have no USDM CT codelist.

        These are NCI Thesaurus codes used by the pipeline and UI for coded
        fields where CDISC has not yet published a USDM CT codelist.
        """
        supplementary = {
            # StudyDesign.studyType — no USDM CT codelist
            "StudyDesign.studyType": CodeList(
                codelist_code="NCI",
                entity="StudyDesign",
                attribute="studyType",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C98388", "Interventional Study"),
                    CodeTerm("C142615", "Non-Interventional Study"),
                    CodeTerm("C48660", "Not Applicable"),
                ],
            ),
            # StudyDesign.trialPhase — no USDM CT codelist
            "StudyDesign.trialPhase": CodeList(
                codelist_code="NCI",
                entity="StudyDesign",
                attribute="trialPhase",
                extensible=False,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C15600", "Phase I Trial"),
                    CodeTerm("C15693", "Phase I/II Trial"),
                    CodeTerm("C15601", "Phase II Trial"),
                    CodeTerm("C15694", "Phase II/III Trial"),
                    CodeTerm("C15602", "Phase III Trial"),
                    CodeTerm("C15603", "Phase IV Trial"),
                    CodeTerm("C48660", "Not Applicable"),
                ],
            ),
            # Masking.blindingSchema — no USDM CT codelist
            "Masking.blindingSchema": CodeList(
                codelist_code="NCI",
                entity="Masking",
                attribute="blindingSchema",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C49659", "Open Label Study"),
                    CodeTerm("C28233", "Single Blind Study"),
                    CodeTerm("C15228", "Double Blind Study"),
                    CodeTerm("C66959", "Triple Blind Study"),
                ],
            ),
            # StudyArm.type — no USDM CT codelist
            "StudyArm.type": CodeList(
                codelist_code="NCI",
                entity="StudyArm",
                attribute="type",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C174266", "Investigational Arm"),
                    CodeTerm("C174267", "Active Comparator Arm"),
                    CodeTerm("C174268", "Placebo Control Arm"),
                    CodeTerm("C174269", "Sham Comparator Arm"),
                    CodeTerm("C174270", "No Intervention Arm"),
                    CodeTerm("C49649", "Active Control"),
                ],
            ),
            # EligibilityCriterion.category — no USDM CT codelist
            "EligibilityCriterion.category": CodeList(
                codelist_code="NCI",
                entity="EligibilityCriterion",
                attribute="category",
                extensible=False,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C25532", "Inclusion Criteria"),
                    CodeTerm("C25370", "Exclusion Criteria"),
                ],
            ),
            # StudyEpoch.type — no USDM CT codelist
            "StudyEpoch.type": CodeList(
                codelist_code="NCI",
                entity="StudyEpoch",
                attribute="type",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C48262", "Trial Screening"),
                    CodeTerm("C98779", "Run-in Period"),
                    CodeTerm("C101526", "Treatment Epoch"),
                    CodeTerm("C99158", "Clinical Study Follow-up"),
                    CodeTerm("C71738", "Clinical Trial Epoch"),
                ],
            ),
            # StudyDesign.model — no USDM CT codelist
            "StudyDesign.model": CodeList(
                codelist_code="NCI",
                entity="StudyDesign",
                attribute="model",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C82639", "Parallel Study"),
                    CodeTerm("C82637", "Crossover Study"),
                    CodeTerm("C82640", "Single Group Study"),
                    CodeTerm("C82638", "Factorial Study"),
                ],
            ),
            # StudyIntervention.type — no USDM CT codelist (ICH M11)
            "StudyIntervention.type": CodeList(
                codelist_code="NCI",
                entity="StudyIntervention",
                attribute="type",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C1909", "Drug"),
                    CodeTerm("C307", "Biological"),
                    CodeTerm("C16830", "Device"),
                    CodeTerm("C1505", "Dietary Supplement"),
                    CodeTerm("C15329", "Procedure"),
                    CodeTerm("C15313", "Radiation"),
                    CodeTerm("C17649", "Other"),
                ],
            ),
            # Population.plannedSex — no USDM CT codelist
            "Population.plannedSex": CodeList(
                codelist_code="NCI",
                entity="Population",
                attribute="plannedSex",
                extensible=False,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C16576", "Female"),
                    CodeTerm("C20197", "Male"),
                ],
            ),
            # Administration.route — no USDM CT codelist (SDTM ROUTE)
            "Administration.route": CodeList(
                codelist_code="NCI",
                entity="Administration",
                attribute="route",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C38288", "Oral"),
                    CodeTerm("C38276", "Intravenous"),
                    CodeTerm("C38299", "Subcutaneous"),
                    CodeTerm("C38274", "Intramuscular"),
                    CodeTerm("C38305", "Topical"),
                    CodeTerm("C38284", "Nasal"),
                    CodeTerm("C38246", "Inhalation"),
                    CodeTerm("C17998", "Other"),
                ],
            ),
            # AnalysisPopulation.level — no USDM CT codelist
            "AnalysisPopulation.level": CodeList(
                codelist_code="NCI",
                entity="AnalysisPopulation",
                attribute="level",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C174264", "Intent-to-Treat"),
                    CodeTerm("C174265", "Per-Protocol"),
                    CodeTerm("C174263", "Safety"),
                    CodeTerm("C17998", "Other"),
                ],
            ),
            # Procedure.type — no USDM CT codelist
            "Procedure.type": CodeList(
                codelist_code="NCI",
                entity="Procedure",
                attribute="type",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C18020", "Diagnostic Procedure"),
                    CodeTerm("C49236", "Therapeutic Procedure"),
                    CodeTerm("C15329", "Surgical Procedure"),
                    CodeTerm("C70945", "Biospecimen Collection"),
                    CodeTerm("C16502", "Diagnostic Imaging Testing"),
                    CodeTerm("C25218", "Clinical Intervention or Procedure"),
                ],
            ),
            # Substance.type — no USDM CT codelist
            "Substance.type": CodeList(
                codelist_code="NCI",
                entity="Substance",
                attribute="type",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C45305", "Active Ingredient"),
                    CodeTerm("C42637", "Inactive Ingredient"),
                    CodeTerm("C48660", "Not Applicable"),
                ],
            ),
            # Ingredient.role — no USDM CT codelist
            "Ingredient.role": CodeList(
                codelist_code="NCI",
                entity="Ingredient",
                attribute="role",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C82499", "Active"),
                    CodeTerm("C82500", "Inactive"),
                    CodeTerm("C82501", "Adjuvant"),
                    CodeTerm("C48660", "Not Applicable"),
                ],
            ),
            # StudyDesign.randomizationType — no USDM CT codelist
            "StudyDesign.randomizationType": CodeList(
                codelist_code="NCI",
                entity="StudyDesign",
                attribute="randomizationType",
                extensible=True,
                source="NCI_EVS",
                terms=[
                    CodeTerm("C25196", "Randomization"),
                    CodeTerm("C48660", "Not Applicable"),
                ],
            ),
        }
        for key, cl in supplementary.items():
            if key not in self._codelists:
                self._codelists[key] = cl

        # Register aliases for convenience (camelCase UI keys → Entity.attribute)
        self._aliases.update({
            "studyPhase": "StudyDesign.trialPhase",
            "studyType": "StudyDesign.studyType",
            "blindingSchema": "Masking.blindingSchema",
            "armType": "StudyArm.type",
            "epochType": "StudyEpoch.type",
            "encounterType": "Encounter.type",
            "objectiveLevel": "Objective.level",
            "endpointLevel": "Endpoint.level",
            "endpointPurpose": "Endpoint.level",
            "interventionRole": "StudyIntervention.role",
            "interventionType": "StudyIntervention.type",
            "sex": "Population.plannedSex",
            "eligibilityCategory": "EligibilityCriterion.category",
            "organizationType": "Organization.type",
            "studyModel": "StudyDesign.model",
            "routeOfAdministration": "Administration.route",
            "populationLevel": "AnalysisPopulation.level",
            "dataOriginType": "StudyArm.dataOriginType",
            "titleType": "StudyTitle.type",
            "timingType": "Timing.type",
            "timingRelativeToFrom": "Timing.relativeToFrom",
            "productDesignation": "AdministrableProduct.productDesignation",
            "productSourcing": "AdministrableProduct.sourcing",
            "studyCharacteristics": "StudyDesign.characteristics",
            "amendmentReason": "StudyAmendmentReason.code",
            "amendmentImpact": "StudyAmendmentImpact.type",
            "geographicScopeType": "GeographicScope.type",
            "governanceDateType": "GovernanceDate.type",
            "documentStatus": "StudyDefinitionDocumentVersion.status",
            "studyRoleCode": "StudyRole.code",
            "procedureType": "Procedure.type",
            "substanceType": "Substance.type",
            "ingredientRole": "Ingredient.role",
            "randomizationType": "StudyDesign.randomizationType",
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _resolve(self, key: str) -> str:
        """Resolve an alias to a canonical key."""
        return self._aliases.get(key, key)

    def get_codelist(self, key: str) -> Optional[CodeList]:
        """Get a codelist by Entity.attribute key or alias."""
        return self._codelists.get(self._resolve(key))

    def lookup(self, key: str, code: str) -> Optional[CodeTerm]:
        """Look up a specific code within a codelist."""
        cl = self.get_codelist(key)
        return cl.lookup(code) if cl else None

    def match(self, key: str, text: str) -> Optional[CodeTerm]:
        """Fuzzy-match a term from free text within a codelist."""
        cl = self.get_codelist(key)
        return cl.match(text) if cl else None

    def make_code(
        self,
        key: str,
        code: str,
        *,
        code_system: str = _CODE_SYSTEM,
        code_system_version: str = _CODE_SYSTEM_VERSION,
    ) -> Dict[str, Any]:
        """Build a USDM-compliant Code dict for a given code."""
        term = self.lookup(key, code)
        decode = term.decode if term else code
        return {
            "code": code,
            "codeSystem": code_system,
            "codeSystemVersion": code_system_version,
            "decode": decode,
            "instanceType": "Code",
        }

    def make_code_from_text(
        self,
        key: str,
        text: str,
        *,
        code_system: str = _CODE_SYSTEM,
        code_system_version: str = _CODE_SYSTEM_VERSION,
    ) -> Dict[str, Any]:
        """Build a USDM Code dict by fuzzy-matching free text."""
        term = self.match(key, text)
        if term:
            return {
                "code": term.code,
                "codeSystem": code_system,
                "codeSystemVersion": code_system_version,
                "decode": term.decode,
                "instanceType": "Code",
            }
        # Fallback: return text as-is
        return {
            "code": text,
            "codeSystem": code_system,
            "codeSystemVersion": code_system_version,
            "decode": text,
            "instanceType": "Code",
        }

    def options(self, key: str) -> List[Dict[str, str]]:
        """Get dropdown options for a codelist (for UI consumption)."""
        cl = self.get_codelist(key)
        if not cl:
            return []
        return [{"code": t.code, "decode": t.decode} for t in cl.terms]

    def all_codes_flat(self) -> Dict[str, str]:
        """Return a flat {code: decode} dict of all known codes."""
        result: Dict[str, str] = {}
        for cl in self._codelists.values():
            for t in cl.terms:
                result[t.code] = t.decode
        return result

    def keys(self) -> List[str]:
        """Return all registered codelist keys."""
        return list(self._codelists.keys())

    def alias_keys(self) -> Dict[str, str]:
        """Return all registered aliases → canonical keys."""
        return dict(self._aliases)

    def export_for_ui(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Export all codelists in the format consumed by the web-ui.

        Returns a dict keyed by alias (camelCase) with lists of
        {code, decode} objects — directly usable by EditableCodedValue.
        """
        result: Dict[str, List[Dict[str, str]]] = {}
        # Export by alias
        for alias, canonical in self._aliases.items():
            cl = self._codelists.get(canonical)
            if cl:
                result[alias] = [{"code": t.code, "decode": t.decode} for t in cl.terms]
        # Also export by canonical key for completeness
        for key, cl in self._codelists.items():
            if key not in result:
                result[key] = [{"code": t.code, "decode": t.decode} for t in cl.terms]
        return result

    def __len__(self) -> int:
        return len(self._codelists)

    def __contains__(self, key: str) -> bool:
        return self._resolve(key) in self._codelists


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

registry = CodeRegistry()
"""Module-level singleton — import this directly."""
