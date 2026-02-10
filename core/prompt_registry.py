"""
Prompt version registry for Protocol2USDM.

Discovers all prompt constants across extraction phases, computes SHA-256
hashes, and exposes a snapshot dict suitable for embedding in run manifests.

Usage:
    from core.prompt_registry import get_prompt_versions
    versions = get_prompt_versions()
    # {'metadata': {'hash': 'a1b2c3...', 'length': 2340}, ...}
"""

import hashlib
import importlib
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Map of phase_name -> (module_path, constant_name(s))
# Each phase may export one or more prompt constants.
PROMPT_SOURCES: Dict[str, list] = {
    "metadata":          [("extraction.metadata.prompts", "METADATA_EXTRACTION_PROMPT")],
    "eligibility":       [("extraction.eligibility.prompts", "ELIGIBILITY_EXTRACTION_PROMPT")],
    "objectives":        [("extraction.objectives.prompts", "OBJECTIVES_EXTRACTION_PROMPT")],
    "studydesign":       [("extraction.studydesign.prompts", "STUDY_DESIGN_EXTRACTION_PROMPT")],
    "interventions":     [("extraction.interventions.prompts", "INTERVENTIONS_EXTRACTION_PROMPT")],
    "narrative":         [("extraction.narrative.prompts", "STRUCTURE_EXTRACTION_PROMPT")],
    "advanced":          [("extraction.advanced.prompts", "ADVANCED_EXTRACTION_PROMPT")],
    "procedures":        [("extraction.procedures.prompts", "PROCEDURES_SYSTEM_PROMPT")],
    "scheduling":        [("extraction.scheduling.prompts", "SCHEDULING_SYSTEM_PROMPT")],
    "amendments":        [("extraction.amendments.prompts", "AMENDMENTS_EXTRACTION_PROMPT")],
    "execution":         [("extraction.execution.prompts", "EXECUTION_MODEL_PROMPT")],
    "docstructure":      [("extraction.document_structure.prompts", "DOCUMENT_STRUCTURE_PROMPT")],
}


def _hash_text(text: str) -> str:
    """SHA-256 of a prompt string, truncated to 12 hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def get_prompt_versions() -> Dict[str, Dict[str, Any]]:
    """
    Discover and hash all registered prompt constants.

    Returns:
        Dict mapping phase name to {'hash': str, 'length': int, 'constant': str}.
        If a prompt module cannot be imported, it is logged and skipped.
    """
    versions: Dict[str, Dict[str, Any]] = {}

    for phase, sources in PROMPT_SOURCES.items():
        for module_path, const_name in sources:
            try:
                mod = importlib.import_module(module_path)
                text = getattr(mod, const_name, None)
                if text and isinstance(text, str):
                    versions[phase] = {
                        "hash": _hash_text(text),
                        "length": len(text),
                        "constant": f"{module_path}.{const_name}",
                    }
                else:
                    logger.debug(f"Prompt constant {const_name} not found in {module_path}")
            except ImportError as e:
                logger.debug(f"Could not import {module_path}: {e}")

    return versions


def get_prompt_fingerprint() -> str:
    """
    Single combined hash of all prompt versions.

    Useful as a quick "did any prompt change?" check.
    """
    versions = get_prompt_versions()
    combined = "|".join(f"{k}:{v['hash']}" for k, v in sorted(versions.items()))
    return _hash_text(combined)
