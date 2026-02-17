"""
CDISC CORE Compliance Normalization

Pre-validation pass that fixes common CORE conformance issues:
  1. codeSystem normalization  — remap non-CDISC URIs to "http://www.cdisc.org"
  2. Empty ID generation       — assign UUIDs to nested entities missing IDs
  3. Default label population   — copy name → label for required entities
  4. XHTML sanitization         — escape raw angle brackets in text fields

Called from core.validation.validate_and_fix_schema() between type-inference
normalization and UUID conversion.
"""

import copy
import html
import logging
import re
import uuid as _uuid
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CDISC_CODE_SYSTEM = "http://www.cdisc.org"
CDISC_CODE_SYSTEM_VERSION = "2024-09-27"

# codeSystem values that should be remapped to the canonical CDISC URI.
# These are DDF-managed codelists where CORE expects "http://www.cdisc.org".
_REMAP_CODE_SYSTEMS: Set[str] = {
    "USDM",
    "http://www.cdisc.org/USDM",
    "http://www.cdisc.org/USDM/sex",
}

# NCI EVS URI variants — keep these as-is for NCI-sourced codes that are
# NOT on a DDF codelist (e.g., procedure codes, indication codes).
# But eligibility category, timing type, objective level, etc. need the
# CDISC codeSystem because CORE validates them against DDF codelists.
_EVS_URIS = {
    "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
}

# DDF codelist C-code ranges — codes that belong to DDF-managed codelists
# and must have codeSystem = "http://www.cdisc.org".
# We identify them by checking if the code appears in a DDF codelist context.
# Rather than maintaining a list, we use the parent key to decide.
_DDF_CODELIST_PARENT_KEYS: Set[str] = {
    # Eligibility
    "category",
    # Timing
    "type",           # also used for encounter type, epoch type, etc.
    "relativeToFrom",
    # Objectives/Endpoints
    "level",
    # Interventions
    "role",
    "sourcing",
    "productDesignation",
    # Study Design
    "blindingSchema",
    "studyPhase",
    "model",
    "studyType",
    "trialType",
    "trialIntentType",
    "interventionModel",
    "dataOriginType",
    # Population
    "plannedSex",
    # Governance
    "dateType",
    # Geographic
    "geographicScope",
    # Amendment
    "primaryReason",
    "secondaryReasons",
    # StudyTitle
    "titleType",
    # StudyIdentifier
    "identifierType",
    # Characteristics
    "characteristics",
}

# Entity types that require a 'label' field per USDM schema (CORE-000937)
_ENTITIES_NEEDING_LABEL: Set[str] = {
    "Activity",
    "Encounter",
    "Objective",
    "Endpoint",
    "Estimand",
    "StudyIntervention",
    "StudyAmendment",
    "AnalysisPopulation",
    "StudyElement",
    "Procedure",
    "ScheduledActivityInstance",
}

# Entity types that require a 'description' field
_ENTITIES_NEEDING_DESCRIPTION: Set[str] = {
    "Activity",
    "Encounter",
    "Objective",
    "Endpoint",
    "StudyElement",
}

# Keys whose string values should be XHTML-sanitized
_XHTML_KEYS: Set[str] = {"text"}


# ---------------------------------------------------------------------------
# 1. codeSystem Normalization
# ---------------------------------------------------------------------------

def _normalize_code_system(obj: Dict[str, Any], parent_key: str = "") -> int:
    """
    Normalize codeSystem on a Code-like dict.

    Returns number of fields fixed.
    """
    if not isinstance(obj, dict) or "code" not in obj:
        return 0

    fixed = 0
    cs = obj.get("codeSystem", "")

    # Direct USDM variants → always remap
    if cs in _REMAP_CODE_SYSTEMS:
        obj["codeSystem"] = CDISC_CODE_SYSTEM
        obj["codeSystemVersion"] = CDISC_CODE_SYSTEM_VERSION
        fixed += 1

    # EVS URI on a DDF-codelist parent key → remap to CDISC
    elif cs in _EVS_URIS and parent_key in _DDF_CODELIST_PARENT_KEYS:
        obj["codeSystem"] = CDISC_CODE_SYSTEM
        obj["codeSystemVersion"] = CDISC_CODE_SYSTEM_VERSION
        fixed += 1

    # Fix blank codeSystemVersion when codeSystem is already CDISC
    if obj.get("codeSystem") == CDISC_CODE_SYSTEM:
        csv = obj.get("codeSystemVersion", "")
        if not csv or csv in ("null", "None"):
            obj["codeSystemVersion"] = CDISC_CODE_SYSTEM_VERSION
            fixed += 1

    return fixed


def _walk_normalize_codes(obj: Any, parent_key: str = "") -> int:
    """Recursively normalize codeSystem across the entire USDM tree."""
    fixed = 0
    if isinstance(obj, dict):
        # If this dict itself is a Code object, normalize it
        if "code" in obj and "decode" in obj:
            fixed += _normalize_code_system(obj, parent_key)
        # Recurse into children
        for key, value in obj.items():
            fixed += _walk_normalize_codes(value, parent_key=key)
    elif isinstance(obj, list):
        for item in obj:
            fixed += _walk_normalize_codes(item, parent_key=parent_key)
    return fixed


# ---------------------------------------------------------------------------
# 2. Empty ID Generation
# ---------------------------------------------------------------------------

def _generate_uuid() -> str:
    return str(_uuid.uuid4())


_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I
)


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID v4 format."""
    return bool(value and _UUID_RE.match(value))


def _walk_generate_ids(obj: Any, parent_key: str = "") -> int:
    """Assign UUIDs to entities/Code objects with missing, empty, or non-UUID 'id' fields."""
    generated = 0
    if isinstance(obj, dict):
        instance_type = obj.get("instanceType", "")
        current_id = obj.get("id")
        needs_id = not current_id or current_id in ("", None)

        # For Code/AliasCode objects, also replace non-UUID IDs (e.g., C-codes)
        if not needs_id and instance_type in ("Code", "AliasCode"):
            if not _is_valid_uuid(str(current_id)):
                needs_id = True

        # If it looks like a typed entity (has instanceType) and id is needed
        if instance_type and needs_id:
            obj["id"] = _generate_uuid()
            generated += 1
        # Also handle Code objects without instanceType but with code+decode
        elif "code" in obj and "decode" in obj and (not obj.get("id") or obj["id"] in ("", None)):
            obj["id"] = _generate_uuid()
            generated += 1
        # Recurse
        for key, value in obj.items():
            generated += _walk_generate_ids(value, parent_key=key)
    elif isinstance(obj, list):
        for item in obj:
            generated += _walk_generate_ids(item, parent_key=parent_key)
    return generated


# ---------------------------------------------------------------------------
# 3. Default Label / Description Population
# ---------------------------------------------------------------------------

def _walk_populate_labels(obj: Any, parent_key: str = "") -> int:
    """Copy name → label and name → description where missing on required entities."""
    populated = 0
    if isinstance(obj, dict):
        inst = obj.get("instanceType", "")
        name = obj.get("name", "")

        if inst in _ENTITIES_NEEDING_LABEL:
            if not obj.get("label") and name:
                obj["label"] = name
                populated += 1

        if inst in _ENTITIES_NEEDING_DESCRIPTION:
            if not obj.get("description") and name:
                obj["description"] = name
                populated += 1

        for key, value in obj.items():
            populated += _walk_populate_labels(value, parent_key=key)
    elif isinstance(obj, list):
        for item in obj:
            populated += _walk_populate_labels(item, parent_key=parent_key)
    return populated


# ---------------------------------------------------------------------------
# 4. XHTML Sanitization
# ---------------------------------------------------------------------------

# Pattern to detect raw angle brackets that aren't valid XML tags
_RAW_ANGLE_RE = re.compile(r'<(?![/?]?\w+[\s/>])')


def _sanitize_xhtml_value(text: str) -> str:
    """Escape problematic angle brackets in a text value."""
    if not text or "<" not in text:
        return text
    # If the text contains what looks like invalid XML tags, escape them
    if _RAW_ANGLE_RE.search(text):
        # Escape < that aren't part of valid-looking tags
        return _RAW_ANGLE_RE.sub("&lt;", text)
    return text


def _walk_sanitize_xhtml(obj: Any, parent_key: str = "") -> int:
    """Sanitize text fields that CORE validates as XHTML."""
    sanitized = 0
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _XHTML_KEYS and isinstance(value, str):
                new_val = _sanitize_xhtml_value(value)
                if new_val != value:
                    obj[key] = new_val
                    sanitized += 1
            elif isinstance(value, (dict, list)):
                sanitized += _walk_sanitize_xhtml(value, parent_key=key)
    elif isinstance(obj, list):
        for item in obj:
            sanitized += _walk_sanitize_xhtml(item, parent_key=parent_key)
    return sanitized


# ---------------------------------------------------------------------------
# 5. Strip Non-USDM Properties
# ---------------------------------------------------------------------------

# Allowed properties per USDM entity type (from dataStructure.yml).
# Only entity types that have known non-USDM properties in our pipeline.
_USDM_ALLOWED_KEYS: Dict[str, Set[str]] = {
    "ExtensionAttribute": {
        "id", "url", "valueString", "valueBoolean", "valueInteger", "valueId",
        "valueQuantity", "valueRange", "valueCode", "valueAliasCode",
        "valueExtensionClass", "extensionAttributes", "instanceType",
    },
    "NarrativeContentItem": {
        "id", "name", "text", "extensionAttributes", "instanceType",
    },
    "NarrativeContent": {
        "id", "name", "sectionNumber", "sectionTitle",
        "displaySectionTitle", "displaySectionNumber",
        "text", "contentItemId", "previousId", "nextId", "childIds",
        "extensionAttributes", "instanceType",
    },
    "StudyDefinitionDocument": {
        "id", "name", "label", "description", "type", "templateName",
        "language", "notes", "childIds", "versions",
        "extensionAttributes", "instanceType",
    },
    "StudyDefinitionDocumentVersion": {
        "id", "status", "version", "notes", "dateValues", "contents",
        "extensionAttributes", "instanceType",
    },
    "Activity": {
        "id", "name", "label", "description", "definedProcedures",
        "bcCategories", "bcSurrogates", "biomedicalConceptSurrogates",
        "biomedicalConceptCategories", "notes", "extensionAttributes",
        "instanceType", "nextId", "previousId", "childIds", "timelineId",
        "biomedicalConceptIds", "bcCategoryIds", "bcSurrogateIds",
    },
    "Encounter": {
        "id", "name", "label", "description", "type", "environmentalSettings",
        "contactModes", "notes", "transitionStartRule", "transitionEndRule",
        "scheduledAtId", "extensionAttributes", "instanceType",
        "nextId", "previousId",
    },
    "Objective": {
        "id", "name", "label", "description", "text", "level",
        "endpoints", "extensionAttributes", "instanceType",
    },
    "Procedure": {
        "id", "name", "label", "description", "type",
        "procedureType", "code",
        "extensionAttributes", "instanceType",
    },
    "ScheduledActivityInstance": {
        "id", "name", "label", "description", "timelineId",
        "timelineExitId", "activityIds", "encounterId",
        "epochId", "defaultConditionId",
        "extensionAttributes", "instanceType",
    },
    "AnalysisPopulation": {
        "id", "name", "label", "description", "text",
        "extensionAttributes", "instanceType",
    },
    "StudyDesignPopulation": {
        "id", "name", "label", "description",
        "plannedEnrollmentNumber", "plannedCompletionNumber",
        "plannedAge", "plannedSex", "includesHealthySubjects",
        "criterionIds", "extensionAttributes", "instanceType",
    },
    "StudyElement": {
        "id", "name", "label", "description",
        "studyInterventionIds", "transitionStartRule", "transitionEndRule",
        "extensionAttributes", "instanceType",
    },
    "StudyAmendment": {
        "id", "name", "label", "description", "number",
        "summary", "primaryReason", "secondaryReasons",
        "changes", "impacts", "enrollments", "geographicScopes",
        "extensionAttributes", "instanceType",
    },
    "StudyAmendmentImpact": {
        "id", "type", "text", "isSubstantial",
        "extensionAttributes", "instanceType",
    },
    "StudyAmendmentReason": {
        "id", "code", "otherReason",
        "extensionAttributes", "instanceType",
    },
    "StudyChange": {
        "id", "name", "rationale", "changedSections",
        "extensionAttributes", "instanceType",
    },
    "StudyIdentifier": {
        "id", "text", "scopeId",
        "extensionAttributes", "instanceType",
    },
    "Organization": {
        "id", "name", "label", "identifier", "identifierScheme",
        "type", "legalAddress", "managedSites",
        "extensionAttributes", "instanceType",
    },
    "StudySite": {
        "id", "name", "label", "description", "country",
        "extensionAttributes", "instanceType",
    },
    "StudyIntervention": {
        "id", "name", "label", "description", "role", "type",
        "minimumResponseDuration", "codes",
        "extensionAttributes", "instanceType",
    },
    "Estimand": {
        "id", "name", "label", "description",
        "populationSummary", "analysisPopulationId",
        "variableOfInterestId", "interventionIds",
        "intercurrentEvents", "notes",
        "extensionAttributes", "instanceType",
    },
    "AdministrableProduct": {
        "id", "name", "label", "description",
        "pharmacologicalClass", "productDesignation",
        "administrableDoseForm", "ingredients",
        "identifiers", "properties",
        "extensionAttributes", "instanceType",
    },
    "Ingredient": {
        "id", "name", "label", "description",
        "role", "substance", "referenceStrength",
        "extensionAttributes", "instanceType",
    },
    "StudyVersion": {
        "id", "versionIdentifier", "businessTherapeuticAreas", "rationale",
        "notes", "abbreviations", "dateValues", "referenceIdentifiers",
        "amendments", "documentVersionIds", "studyDesigns", "studyIdentifiers",
        "titles", "extensionAttributes", "eligibilityCriterionItems",
        "narrativeContentItems", "roles", "organizations", "studyInterventions",
        "administrableProducts", "medicalDevices", "productOrganizationRoles",
        "biomedicalConcepts", "bcCategories", "bcSurrogates", "dictionaries",
        "conditions", "instanceType",
    },
    "InterventionalStudyDesign": {
        "id", "name", "label", "description", "rationale",
        "therapeuticAreas", "studyType", "characteristics", "studyPhase",
        "notes", "activities", "biospecimenRetentions", "eligibilityCriteria",
        "encounters", "estimands", "indications", "objectives",
        "scheduleTimelines", "arms", "studyCells", "documentVersionIds",
        "elements", "studyInterventionIds", "epochs", "population",
        "model", "subTypes", "blindingSchema", "intentTypes",
        "extensionAttributes", "analysisPopulations", "instanceType",
    },
}


def _walk_strip_non_usdm(obj: Any, parent_key: str = "") -> int:
    """Remove properties not in the USDM schema from typed entities."""
    stripped = 0
    if isinstance(obj, dict):
        inst = obj.get("instanceType", "")
        if inst in _USDM_ALLOWED_KEYS:
            allowed = _USDM_ALLOWED_KEYS[inst]
            to_remove = [k for k in obj if k not in allowed]
            for k in to_remove:
                del obj[k]
                stripped += 1
        # Recurse into remaining values
        for value in list(obj.values()):
            if isinstance(value, (dict, list)):
                stripped += _walk_strip_non_usdm(value, parent_key=parent_key)
    elif isinstance(obj, list):
        for item in obj:
            stripped += _walk_strip_non_usdm(item, parent_key=parent_key)
    return stripped


# ---------------------------------------------------------------------------
# 6. Procedure Required Defaults
# ---------------------------------------------------------------------------

def _walk_fix_procedure_defaults(obj: Any) -> int:
    """Ensure all Procedure objects have required procedureType and code fields."""
    fixed = 0
    if isinstance(obj, dict):
        if obj.get("instanceType") == "Procedure":
            if not obj.get("procedureType"):
                obj["procedureType"] = "Clinical Procedure"
                fixed += 1
            if not obj.get("code"):
                obj["code"] = {
                    "id": _generate_uuid(),
                    "code": "C25218",
                    "codeSystem": "http://www.cdisc.org",
                    "codeSystemVersion": "2024-09-27",
                    "decode": "Clinical Intervention or Procedure",
                    "instanceType": "Code",
                }
                fixed += 1
        for value in obj.values():
            if isinstance(value, (dict, list)):
                fixed += _walk_fix_procedure_defaults(value)
    elif isinstance(obj, list):
        for item in obj:
            fixed += _walk_fix_procedure_defaults(item)
    return fixed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_for_core_compliance(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Safety-net CORE compliance normalizations applied at validation time.

    These are *fallback* fixes for data that bypassed source-level fixes
    (e.g., direct dict construction in extractors, LLM-generated dicts).

    Primary fixes now live at the correct architectural locations:
    - codeSystem: extractor schema.py ``to_dict()`` methods
    - Labels: dataclass ``to_dict()`` methods in ``usdm_types_generated.py``
    - IDs: ``_ensure_id()`` in ``USDMEntity`` / ``registry.make_code()``
    - Ordering/linkage/timing: ``pipeline/post_processing.py``

    Args:
        data: USDM JSON dict (will be deep-copied)

    Returns:
        Tuple of (normalized data, stats dict with counts per fix category)
    """
    result = copy.deepcopy(data)
    stats: Dict[str, int] = {}

    stats["codes_fixed"] = _walk_normalize_codes(result)
    stats["ids_generated"] = _walk_generate_ids(result)
    stats["labels_populated"] = _walk_populate_labels(result)
    stats["xhtml_sanitized"] = _walk_sanitize_xhtml(result)
    stats["proc_defaults"] = _walk_fix_procedure_defaults(result)
    stats["props_stripped"] = _walk_strip_non_usdm(result)

    total = sum(stats.values())
    logger.info(
        f"      CORE compliance: {total} safety-net fixes "
        f"(codes={stats['codes_fixed']}, ids={stats['ids_generated']}, "
        f"labels={stats['labels_populated']}, xhtml={stats['xhtml_sanitized']}, "
        f"stripped={stats['props_stripped']})"
    )

    return result, stats
