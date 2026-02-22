"""
Stratification Cross-Phase Linker

Links stratification factors extracted in Phase 4C to other pipeline phases:
  B1: Factor levels → EligibilityCriterion (criterion_id on FactorLevel)
  B2: Factors → SAP statistical method covariates (coherence warnings)
  B3: Scheme → Study arms (allocation weight per arm)
  B4: Scheme → Analysis populations

Called during post-processing after all phases have completed.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# B1: Link factors → eligibility criteria
# ─────────────────────────────────────────────────────────────

def link_factors_to_eligibility(combined: dict) -> List[Dict[str, Any]]:
    """
    Match stratification factor levels to EligibilityCriterion entities.

    For each FactorLevel, find the eligibility criterion whose text best
    matches the level definition (e.g., "Age ≥65" → criterion about age).
    Populates criterionId on matching FactorLevel dicts in-place.

    Returns a list of link records for diagnostics.
    """
    links: List[Dict[str, Any]] = []

    scheme = _get_randomization_scheme(combined)
    if not scheme:
        return links

    criteria = _get_eligibility_criteria(combined)
    if not criteria:
        logger.debug("No eligibility criteria found for factor→criterion linking")
        return links

    factors = scheme.get("stratificationFactors", [])
    for factor in factors:
        factor_name = factor.get("name", "").lower()
        for level in factor.get("factorLevels", []):
            if level.get("criterionId"):
                continue  # Already linked

            label = level.get("label", "")
            definition = level.get("definition", "")
            search_text = f"{factor_name} {label} {definition}".lower()

            best_crit, best_score = _find_best_criterion(search_text, criteria)
            if best_crit and best_score >= 0.3:
                level["criterionId"] = best_crit["id"]
                links.append({
                    "factorName": factor.get("name"),
                    "levelLabel": label,
                    "criterionId": best_crit["id"],
                    "criterionText": best_crit.get("_text", "")[:100],
                    "score": round(best_score, 3),
                })

    if links:
        logger.info(f"  ✓ Linked {len(links)} factor level(s) to eligibility criteria (B1)")
    return links


def _find_best_criterion(
    search_text: str, criteria: List[Dict[str, Any]]
) -> Tuple[Optional[Dict], float]:
    """Find the eligibility criterion best matching the search text."""
    best = None
    best_score = 0.0

    search_words = set(re.findall(r'\w+', search_text.lower()))
    if not search_words:
        return None, 0.0

    for crit in criteria:
        crit_text = crit.get("_text", "").lower()
        crit_words = set(re.findall(r'\w+', crit_text))
        if not crit_words:
            continue

        overlap = len(search_words & crit_words)
        score = overlap / max(len(search_words), 1)

        if score > best_score:
            best_score = score
            best = crit

    return best, best_score


# ─────────────────────────────────────────────────────────────
# B2: Link factors → SAP covariates
# ─────────────────────────────────────────────────────────────

def link_factors_to_sap_covariates(combined: dict) -> List[Dict[str, Any]]:
    """
    Cross-reference stratification factors against SAP statistical method
    covariates. Per ICH E9, stratification factors used in randomization
    should be included as covariates in the primary analysis model.

    Returns a list of coherence findings (warnings for missing links).
    """
    findings: List[Dict[str, Any]] = []

    scheme = _get_randomization_scheme(combined)
    if not scheme:
        return findings

    factors = scheme.get("stratificationFactors", [])
    if not factors:
        return findings

    # Get SAP statistical methods
    methods = _get_sap_methods(combined)
    if not methods:
        findings.append({
            "type": "info",
            "message": "No SAP statistical methods found — cannot verify covariate alignment",
        })
        return findings

    # Collect all covariates across methods
    all_covariates: List[str] = []
    for method in methods:
        covs = method.get("covariates", [])
        if isinstance(covs, list):
            all_covariates.extend([c.lower() for c in covs if isinstance(c, str)])

    covariates_text = " ".join(all_covariates)

    for factor in factors:
        factor_name = factor.get("name", "")
        name_lower = factor_name.lower()

        # Check if factor appears in any covariate list
        found = (
            name_lower in covariates_text
            or any(_fuzzy_match(name_lower, cov) for cov in all_covariates)
            or "stratification" in covariates_text  # Generic reference
        )

        if found:
            findings.append({
                "type": "ok",
                "factorName": factor_name,
                "message": f"Stratification factor '{factor_name}' found in SAP covariates",
            })
        else:
            findings.append({
                "type": "warning",
                "factorName": factor_name,
                "message": (
                    f"Stratification factor '{factor_name}' not found as covariate in "
                    f"primary analysis model (ICH E9 recommends inclusion)"
                ),
            })

    ok_count = sum(1 for f in findings if f["type"] == "ok")
    warn_count = sum(1 for f in findings if f["type"] == "warning")
    if findings:
        logger.info(f"  ✓ SAP covariate check: {ok_count} linked, {warn_count} warnings (B2)")
    return findings


# ─────────────────────────────────────────────────────────────
# B3: Link scheme → study arms
# ─────────────────────────────────────────────────────────────

def link_scheme_to_arms(combined: dict) -> List[Dict[str, Any]]:
    """
    Decompose allocation ratio into per-arm weights.
    
    For "2:1" with arms [Drug, Placebo], Drug gets weight 2, Placebo gets 1.
    Stores arm_allocation_weights on the randomization scheme extension.

    Returns the arm-weight mapping list.
    """
    scheme = _get_randomization_scheme(combined)
    if not scheme:
        return []

    arms = _get_arms(combined)
    ratio_str = scheme.get("ratio", "1:1")

    # Parse ratio
    weights = [int(w) for w in re.findall(r'\d+', ratio_str)]
    if not weights:
        weights = [1]

    # Match weights to arms
    arm_weights: List[Dict[str, Any]] = []
    for idx, arm in enumerate(arms):
        weight = weights[idx] if idx < len(weights) else weights[-1]
        arm_weights.append({
            "armId": arm.get("id", ""),
            "armName": arm.get("name", ""),
            "allocationWeight": weight,
        })

    # Store back on scheme
    if arm_weights:
        scheme["armAllocationWeights"] = arm_weights
        logger.info(f"  ✓ Linked allocation ratio {ratio_str} to {len(arm_weights)} arms (B3)")

    return arm_weights


# ─────────────────────────────────────────────────────────────
# B4: Link scheme → analysis populations
# ─────────────────────────────────────────────────────────────

def link_scheme_to_populations(combined: dict) -> List[Dict[str, Any]]:
    """
    Connect stratification scheme to analysis populations.
    
    Tags analysis populations that reference stratification-based subgroups.
    Returns link records.
    """
    links: List[Dict[str, Any]] = []

    scheme = _get_randomization_scheme(combined)
    if not scheme:
        return links

    factors = scheme.get("stratificationFactors", [])
    if not factors:
        return links

    factor_names = [f.get("name", "").lower() for f in factors]

    # Get analysis populations from SAP or study design
    sd = _get_study_design(combined)
    analysis_pops = sd.get("analysisPopulations", [])

    for pop in analysis_pops:
        pop_name = pop.get("name", "").lower()
        pop_desc = pop.get("description", "").lower()
        search = f"{pop_name} {pop_desc}"

        for fname in factor_names:
            if fname in search or _fuzzy_match(fname, search):
                links.append({
                    "populationId": pop.get("id", ""),
                    "populationName": pop.get("name", ""),
                    "factorName": fname,
                    "type": "stratified_subgroup",
                })
                break

    if links:
        logger.info(f"  ✓ Linked {len(links)} analysis population(s) to stratification factors (B4)")
    return links


# ─────────────────────────────────────────────────────────────
# Master entry point
# ─────────────────────────────────────────────────────────────

def run_stratification_linking(combined: dict) -> Dict[str, Any]:
    """
    Run all stratification cross-phase linking steps.
    
    Called from post-processing after all phases complete.
    Stores results as extension attribute on study design.
    
    Returns summary dict with all linking results.
    """
    scheme = _get_randomization_scheme(combined)
    if not scheme:
        logger.debug("No randomization scheme — skipping stratification linking")
        return {}

    logger.info("Cross-phase stratification linking (Sprint B):")

    results: Dict[str, Any] = {}

    # B1: Factor → Eligibility
    results["eligibilityLinks"] = link_factors_to_eligibility(combined)

    # B2: Factor → SAP Covariates
    results["sapCovariateFindings"] = link_factors_to_sap_covariates(combined)

    # B3: Scheme → Arms
    results["armWeights"] = link_scheme_to_arms(combined)

    # B4: Scheme → Analysis Populations
    results["populationLinks"] = link_scheme_to_populations(combined)

    # Store linking results as extension on the scheme
    if any(results.values()):
        scheme["crossPhaseLinks"] = results
        _store_linking_extension(combined, results)

    return results


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_study_design(combined: dict) -> dict:
    """Get the first study design from combined USDM."""
    try:
        return (
            combined.get("study", {})
            .get("versions", [{}])[0]
            .get("studyDesigns", [{}])[0]
        )
    except (IndexError, AttributeError):
        return {}


def _get_randomization_scheme(combined: dict) -> Optional[dict]:
    """Get the randomization scheme from execution model extensions."""
    sd = _get_study_design(combined)
    for ext in sd.get("extensionAttributes", []):
        if isinstance(ext, dict) and "randomizationScheme" in ext.get("url", ""):
            # Value may be in valueString (JSON) or directly as valueObject
            val = ext.get("valueObject", ext.get("value"))
            if isinstance(val, str):
                import json
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return None
            return val
    return None


def _get_eligibility_criteria(combined: dict) -> List[Dict[str, Any]]:
    """Get eligibility criteria with their text for matching."""
    version = combined.get("study", {}).get("versions", [{}])[0]

    # Criteria items hold the text
    items_by_id = {}
    for item in version.get("eligibilityCriterionItems", []):
        items_by_id[item.get("id", "")] = item.get("text", "")

    # Criteria hold category + link to items
    criteria = []
    sd = _get_study_design(combined)
    pop = sd.get("population", {})
    
    # Criteria may be on version.eligibilityCriterionItems or design.eligibilityCriteria
    for crit in sd.get("eligibilityCriteria", []):
        crit_item_id = crit.get("criterionItemId", crit.get("criterion", {}).get("id", ""))
        text = items_by_id.get(crit_item_id, crit.get("text", ""))
        criteria.append({**crit, "_text": text})

    # Also check population.criterionIds → match back
    if not criteria:
        for crit_id in pop.get("criterionIds", []):
            if crit_id in items_by_id:
                criteria.append({"id": crit_id, "_text": items_by_id[crit_id]})

    return criteria


def _get_sap_methods(combined: dict) -> List[Dict[str, Any]]:
    """Get SAP statistical methods from extensions."""
    sd = _get_study_design(combined)
    for ext in sd.get("extensionAttributes", []):
        if isinstance(ext, dict) and "statistical-methods" in ext.get("url", ""):
            val = ext.get("valueString", ext.get("value", ext.get("valueObject")))
            if isinstance(val, str):
                import json
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return []
            if isinstance(val, list):
                return val
    return []


def _get_arms(combined: dict) -> List[Dict[str, Any]]:
    """Get study arms from the study design."""
    sd = _get_study_design(combined)
    return sd.get("arms", sd.get("studyArms", []))


def _fuzzy_match(needle: str, haystack: str) -> bool:
    """Check if needle words overlap significantly with haystack."""
    needle_words = set(re.findall(r'\w{3,}', needle.lower()))
    haystack_words = set(re.findall(r'\w{3,}', haystack.lower()))
    if not needle_words:
        return False
    overlap = len(needle_words & haystack_words)
    return overlap / len(needle_words) >= 0.5


def _store_linking_extension(combined: dict, results: Dict[str, Any]) -> None:
    """Store cross-phase linking results as an extension attribute."""
    sd = _get_study_design(combined)
    extensions = sd.setdefault("extensionAttributes", [])

    # Remove existing linking extension
    extensions[:] = [
        e for e in extensions
        if not (isinstance(e, dict) and "stratification-links" in e.get("url", ""))
    ]

    import uuid
    extensions.append({
        "id": f"ext_strat_links_{uuid.uuid4()}",
        "url": "https://protocol2usdm.io/extensions/x-stratification-links",
        "instanceType": "ExtensionAttribute",
        "valueObject": results,
    })
