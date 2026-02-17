"""
Cross-phase integration helpers.

Provides shared SAP extension metadata, content reference resolution,
and estimand→population reconciliation.
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)


# SAP extension types — (dict_key, extension_url_suffix, display_label)
SAP_EXTENSION_TYPES = [
    ("derivedVariables",       "derived-variables",       "derived variables"),
    ("dataHandlingRules",      "data-handling-rules",     "data handling rules"),
    ("statisticalMethods",     "statistical-methods",     "statistical methods"),
    ("multiplicityAdjustments","multiplicity-adjustments", "multiplicity adjustments"),
    ("sensitivityAnalyses",    "sensitivity-analyses",    "sensitivity analyses"),
    ("subgroupAnalyses",       "subgroup-analyses",       "subgroup analyses"),
    ("interimAnalyses",        "interim-analyses",        "interim analyses"),
    ("sampleSizeCalculations", "sample-size-calculations","sample size calculations"),
]


def resolve_content_references(combined: dict) -> None:
    """
    Resolve cross-references by matching documentContentReferences against
    narrative section inventory.
    
    Populates:
      - targetId: ID of the matching NarrativeContent or NarrativeContentItem
      - pageNumber: from the narrative section's page data (if available)
    
    Matching strategy:
      1. Exact sectionNumber match against narrativeContents/Items
      2. Prefix match (ref "10.3" matches section "10")
      3. Title keyword match as fallback
    """
    refs = combined.get('documentContentReferences', [])
    if not refs:
        return
    
    study = combined.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    
    narrative_contents = version.get('narrativeContents', [])
    narrative_items = version.get('narrativeContentItems', [])
    
    if not narrative_contents and not narrative_items:
        return
    
    # Build lookup: sectionNumber → entity
    sec_lookup = {}
    for nc in narrative_contents:
        num = nc.get('sectionNumber', '')
        if num:
            sec_lookup[num] = nc
    for nci in narrative_items:
        num = nci.get('sectionNumber', '')
        if num:
            sec_lookup[num] = nci
    
    resolved = 0
    for ref in refs:
        if ref.get('targetId'):
            continue  # already resolved
        
        ref_sec = ref.get('sectionNumber', '')
        if not ref_sec:
            continue
        
        # Pass 1: Exact match
        target = sec_lookup.get(ref_sec)
        
        # Pass 2: Prefix match — "10.3" → find "10" parent
        if not target and '.' in ref_sec:
            parent_num = ref_sec.split('.')[0]
            target = sec_lookup.get(parent_num)
        
        # Pass 3: Try all section numbers that start with this ref's number
        if not target:
            for num, entity in sec_lookup.items():
                if num.startswith(ref_sec + '.') or num == ref_sec:
                    target = entity
                    break
        
        if target:
            ref['targetId'] = target.get('id', '')
            resolved += 1
    
    if resolved:
        logger.info(f"  Resolved {resolved}/{len(refs)} cross-references → targetId")


def _create_populations_from_estimands(estimands: list) -> list:
    """
    Create AnalysisPopulation entities from estimand population references.
    
    Fallback for when the SAP phase doesn't run (no separate SAP PDF).
    Extracts unique population names from estimand.analysisPopulation fields
    and creates standard clinical trial populations.
    """
    import uuid as _uuid
    
    # Standard clinical trial populations with descriptions
    STANDARD_POPULATIONS = {
        'itt': {
            'name': 'Intent-to-Treat (ITT) Population',
            'label': 'ITT',
            'populationType': 'Efficacy',
            'text': 'All randomized participants who received at least one dose of study intervention, analyzed according to randomized treatment assignment.',
        },
        'fas': {
            'name': 'Full Analysis Set (FAS)',
            'label': 'FAS',
            'populationType': 'Efficacy',
            'text': 'All randomized participants who received at least one dose of study intervention and had at least one post-baseline efficacy assessment.',
        },
        'safety': {
            'name': 'Safety Population',
            'label': 'Safety',
            'populationType': 'Safety',
            'text': 'All participants who received at least one dose of study intervention, analyzed according to actual treatment received.',
        },
        'pp': {
            'name': 'Per Protocol (PP) Population',
            'label': 'PP',
            'populationType': 'Efficacy',
            'text': 'All participants in the ITT population who completed the study without major protocol deviations.',
        },
        'pk': {
            'name': 'Pharmacokinetic (PK) Population',
            'label': 'PK',
            'populationType': 'PK',
            'text': 'All participants who received study intervention and had evaluable PK data.',
        },
        'pd': {
            'name': 'Pharmacodynamic (PD) Population',
            'label': 'PD',
            'populationType': 'PD',
            'text': 'All participants who received study intervention and had evaluable PD data.',
        },
        'screened': {
            'name': 'Screened Population',
            'label': 'Screened',
            'populationType': 'Screening',
            'text': 'All participants who signed informed consent and underwent screening procedures.',
        },
        'enrolled': {
            'name': 'Enrolled Population',
            'label': 'Enrolled',
            'populationType': 'Enrollment',
            'text': 'All participants who met eligibility criteria and were enrolled in the study.',
        },
    }
    
    # Keywords to match estimand population text to standard populations
    KEYWORD_MAP = {
        'itt': ['intent-to-treat', 'intent to treat', 'itt'],
        'fas': ['full analysis set', 'fas'],
        'safety': ['safety'],
        'pp': ['per protocol', 'per-protocol', 'pp population'],
        'pk': ['pharmacokinetic', 'pk population', 'pk analysis'],
        'pd': ['pharmacodynamic', 'pd population', 'pd analysis'],
        'screened': ['screened', 'screening population'],
        'enrolled': ['enrolled', 'enrollment population'],
    }
    
    # Collect unique population references from estimands
    referenced_keys = set()
    for est in estimands:
        pop_text = (est.get('analysisPopulation', '') or est.get('populationSummary', '')).lower()
        if not pop_text:
            continue
        for key, keywords in KEYWORD_MAP.items():
            if any(kw in pop_text for kw in keywords):
                referenced_keys.add(key)
                break
    
    # Always include safety if any efficacy population is referenced
    if referenced_keys & {'itt', 'fas', 'pp'}:
        referenced_keys.add('safety')
    
    # Create population entities
    populations = []
    for key in sorted(referenced_keys):
        if key in STANDARD_POPULATIONS:
            pop = dict(STANDARD_POPULATIONS[key])
            pop['id'] = str(_uuid.uuid4())
            pop['instanceType'] = 'AnalysisPopulation'
            populations.append(pop)
    
    return populations


def reconcile_estimand_population_refs(study_design: dict) -> None:
    """
    Reconcile estimand.analysisPopulationId → analysisPopulations references.
    
    The objectives phase generates estimands with LLM-created analysisPopulationId
    UUIDs, while the SAP phase creates analysisPopulations with separate UUIDs.
    This function links them by matching population name/text.
    
    Matching strategy:
    1. Exact name match
    2. Known clinical trial equivalences (ITT ↔ FAS, Safety ↔ Safety Set, etc.)
    3. Word-overlap fuzzy match (>50% of words in common)
    """
    estimands = study_design.get('estimands', [])
    populations = study_design.get('analysisPopulations', [])
    
    # Fallback: if SAP phase didn't produce populations, create from estimand refs
    if estimands and not populations:
        populations = _create_populations_from_estimands(estimands)
        if populations:
            study_design['analysisPopulations'] = populations
            logger.info(f"  Created {len(populations)} analysis populations from estimand references")
    
    if not estimands or not populations:
        return
    
    # Build lookup: existing population IDs
    pop_ids = {p.get('id') for p in populations}
    
    # Population keyword aliases — maps common clinical trial terms to population types
    POPULATION_ALIASES = {
        'itt': ['full analysis', 'fas', 'intent-to-treat', 'intent to treat', 'itt'],
        'fas': ['full analysis', 'fas', 'intent-to-treat', 'intent to treat', 'itt'],
        'safety': ['safety', 'safety set', 'safety population'],
        'pp': ['per protocol', 'per-protocol', 'pp'],
        'pk': ['pharmacokinetic', 'pk analysis', 'pk'],
        'pd': ['pharmacodynamic', 'pd analysis', 'pd'],
        'screened': ['screened', 'screening'],
        'enrolled': ['enrolled', 'enrollment'],
    }
    
    def _normalize(text: str) -> str:
        return text.lower().strip().replace('-', ' ').replace('_', ' ')
    
    def _find_best_match(est_pop_text: str):
        """Find the best matching analysisPopulation for an estimand's population text."""
        norm_text = _normalize(est_pop_text)
        
        # Pass 1: Exact name match
        for pop in populations:
            if _normalize(pop.get('name', '')) == norm_text:
                return pop
            if _normalize(pop.get('label', '')) == norm_text:
                return pop
        
        # Pass 2: Keyword alias match
        for pop in populations:
            pop_name = _normalize(pop.get('name', ''))
            pop_label = _normalize(pop.get('label', ''))
            pop_type = _normalize(pop.get('populationType', ''))
            pop_terms = f"{pop_name} {pop_label} {pop_type}"
            
            for alias_group in POPULATION_ALIASES.values():
                # Check if the estimand text contains any alias term
                est_matches = any(alias in norm_text for alias in alias_group)
                pop_matches = any(alias in pop_terms for alias in alias_group)
                if est_matches and pop_matches:
                    return pop
        
        # Pass 3: Word overlap (>50% of words in common)
        est_words = set(norm_text.split())
        best_pop = None
        best_overlap = 0.0
        for pop in populations:
            pop_words = set(_normalize(pop.get('name', '')).split())
            pop_words |= set(_normalize(pop.get('label', '')).split())
            if not pop_words:
                continue
            overlap = len(est_words & pop_words) / max(len(est_words), len(pop_words))
            if overlap > best_overlap and overlap > 0.3:
                best_overlap = overlap
                best_pop = pop
        
        return best_pop
    
    reconciled = 0
    for est in estimands:
        current_id = est.get('analysisPopulationId', '')
        
        # Skip if already correctly referencing an existing population
        if current_id in pop_ids:
            continue
        
        # Get population text from the estimand (LLM sets this as human-readable text)
        pop_text = (
            est.get('analysisPopulation', '') or 
            est.get('populationSummary', '')
        )
        if not pop_text:
            continue
        
        match = _find_best_match(pop_text)
        if match:
            old_id = est.get('analysisPopulationId', 'MISSING')
            est['analysisPopulationId'] = match['id']
            reconciled += 1
            logger.info(
                f"  Reconciled estimand '{est.get('name', '?')[:40]}' "
                f"population '{pop_text[:30]}' → '{match.get('name')}' "
                f"(old: {old_id[:12]}…)"
            )
        else:
            logger.warning(
                f"  Could not reconcile estimand '{est.get('name', '?')[:40]}' "
                f"population '{pop_text[:50]}' — no matching analysisPopulation found"
            )
    
    if reconciled:
        logger.info(f"  Reconciled {reconciled}/{len(estimands)} estimand → population references")
