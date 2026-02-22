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


def _get_analysis_approach_from_design(study_design: dict) -> str:
    """Read analysisApproach from studyDesign extension attributes.
    
    Returns 'confirmatory', 'descriptive', or 'unknown'.
    The approach is stored by the objectives phase as an x-analysisApproach
    extension attribute during extraction.
    """
    for ext in study_design.get('extensionAttributes', []):
        url = ext.get('url', '')
        if 'x-analysisApproach' in url:
            return ext.get('valueString', 'unknown').lower()
    return 'unknown'


def _create_populations_from_estimands(estimands: list) -> list:
    """
    Create AnalysisPopulation entities from estimand population references.
    
    Fallback for when the SAP phase doesn't run (no separate SAP PDF).
    Uses the actual population text from estimands — never boilerplate definitions.
    Each population is sourced from the estimand's own analysisPopulation field
    which was extracted from protocol language by the LLM.
    """
    import uuid as _uuid
    
    # Keywords for classifying populationType (NOT for generating definitions)
    _TYPE_KEYWORDS = {
        'Efficacy': ['intent-to-treat', 'intent to treat', 'itt', 'full analysis set', 'fas',
                      'per protocol', 'per-protocol', 'pp population', 'efficacy'],
        'Safety': ['safety'],
        'PK': ['pharmacokinetic', 'pk population', 'pk analysis'],
        'PD': ['pharmacodynamic', 'pd population', 'pd analysis'],
        'Screening': ['screened', 'screening population'],
        'Enrollment': ['enrolled', 'enrollment population'],
    }
    
    def _classify_population_type(text: str) -> str:
        """Classify populationType from text using keywords. Default to 'Analysis'."""
        text_lower = text.lower()
        for pop_type, keywords in _TYPE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return pop_type
        return 'Analysis'
    
    # Collect unique population references from estimands using actual extracted text
    seen_names = {}  # normalized_name → (name, text, pop_type)
    for est in estimands:
        pop_text = est.get('analysisPopulation', '') or ''
        pop_summary = est.get('populationSummary', '') or ''
        
        # Use the most specific text available
        name = pop_text or pop_summary
        if not name or not name.strip():
            continue
        
        # Deduplicate by normalized name
        norm_key = name.strip().lower()
        if norm_key in seen_names:
            continue
        
        pop_type = _classify_population_type(name)
        seen_names[norm_key] = (name.strip(), pop_text or pop_summary, pop_type)
    
    # Create population entities from actual extracted references
    populations = []
    for norm_key, (name, description, pop_type) in sorted(seen_names.items()):
        pop = {
            'id': str(_uuid.uuid4()),
            'name': name,
            'label': name,
            'populationType': pop_type,
            'text': description,
            'populationDescription': description,
            'instanceType': 'AnalysisPopulation',
        }
        populations.append(pop)
    
    if populations:
        logger.info(
            f"  Created {len(populations)} analysis populations from estimand references "
            f"(using extracted protocol text, not boilerplate)"
        )
    
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
    
    # Check analysis approach — descriptive studies should not have populations
    # inferred from estimands (which themselves may be inappropriate)
    analysis_approach = _get_analysis_approach_from_design(study_design)
    
    # Fallback: if SAP phase didn't produce populations, create from estimand refs
    # BUT only for confirmatory studies where estimands are expected
    if estimands and not populations:
        if analysis_approach == 'descriptive':
            logger.info(
                "  Skipping population creation from estimand refs: "
                "study uses descriptive statistics (no formal estimand framework)"
            )
        else:
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
            # Create a new AnalysisPopulation so the reference resolves
            import uuid as _uuid
            new_pop = {
                "id": str(_uuid.uuid4()),
                "name": pop_text[:80] or "Analysis Population",
                "label": pop_text[:40] or "Analysis Population",
                "description": pop_text or "Analysis population referenced by estimand",
                "text": pop_text or "Analysis population referenced by estimand",
                "instanceType": "AnalysisPopulation",
            }
            populations.append(new_pop)
            pop_ids.add(new_pop["id"])
            est['analysisPopulationId'] = new_pop['id']
            reconciled += 1
            logger.info(
                f"  Created AnalysisPopulation for estimand '{est.get('name', '?')[:40]}' "
                f"population '{pop_text[:50]}'"
            )
    
    if reconciled:
        logger.info(f"  Reconciled {reconciled}/{len(estimands)} estimand → population references")


def reconcile_estimand_endpoint_refs(study_design: dict) -> None:
    """
    Reconcile estimand.variableOfInterestId → Endpoint references.

    The objectives phase generates estimands with LLM-created endpoint IDs
    (often synthetic like ``{id}_var``) while endpoints are nested inside
    objectives with separate UUIDs.  This function links them by matching
    endpoint name/text.

    Matching strategy:
      1. Already valid — variableOfInterestId exists in endpoint set
      2. Exact name match (estimand.variableOfInterest text == endpoint.name)
      3. Level-based match (primary estimand → primary endpoint, etc.)
      4. Word-overlap fuzzy match (>30% of words in common)
    """
    estimands = study_design.get('estimands', [])
    if not estimands:
        return

    # Collect all endpoints nested inside objectives
    all_endpoints = []
    for obj in study_design.get('objectives', []):
        if isinstance(obj, dict):
            all_endpoints.extend(obj.get('endpoints', []))

    if not all_endpoints:
        return

    ep_ids = {ep.get('id') for ep in all_endpoints if ep.get('id')}

    def _normalize(text: str) -> str:
        return text.lower().strip().replace('-', ' ').replace('_', ' ')

    def _get_level(entity: dict) -> str:
        level = entity.get('level', {})
        if isinstance(level, dict):
            return _normalize(level.get('decode', ''))
        return _normalize(str(level)) if level else ''

    def _find_best_endpoint(est: dict):
        var_text = _normalize(est.get('variableOfInterest', '') or est.get('name', ''))
        est_level = _get_level(est)

        # Pass 1: Exact name match
        for ep in all_endpoints:
            if _normalize(ep.get('name', '')) == var_text:
                return ep
            if _normalize(ep.get('text', '')) == var_text:
                return ep

        # Pass 2: Level-based match (primary estimand → primary endpoint)
        if est_level:
            level_matches = [ep for ep in all_endpoints if _get_level(ep) == est_level]
            if len(level_matches) == 1:
                return level_matches[0]

        # Pass 3: Word overlap
        var_words = set(var_text.split())
        if not var_words:
            return None
        best_ep = None
        best_overlap = 0.0
        for ep in all_endpoints:
            ep_words = set(_normalize(ep.get('name', '')).split())
            ep_words |= set(_normalize(ep.get('text', '')).split())
            if not ep_words:
                continue
            overlap = len(var_words & ep_words) / max(len(var_words), len(ep_words))
            if overlap > best_overlap and overlap > 0.3:
                best_overlap = overlap
                best_ep = ep
        return best_ep

    reconciled = 0
    for est in estimands:
        current_id = est.get('variableOfInterestId', '')
        if current_id in ep_ids:
            continue  # Already valid

        match = _find_best_endpoint(est)
        if match:
            est['variableOfInterestId'] = match['id']
            reconciled += 1
            logger.info(
                f"  Reconciled estimand '{est.get('name', '?')[:40]}' "
                f"endpoint → '{match.get('name', '?')[:40]}'"
            )
        else:
            # Last resort: assign the first endpoint to avoid dangling ref
            if all_endpoints:
                est['variableOfInterestId'] = all_endpoints[0]['id']
                reconciled += 1
                logger.info(
                    f"  Fallback: estimand '{est.get('name', '?')[:40]}' "
                    f"→ first endpoint '{all_endpoints[0].get('name', '?')[:40]}'"
                )

    if reconciled:
        logger.info(f"  Reconciled {reconciled}/{len(estimands)} estimand → endpoint references")


def reconcile_estimand_intervention_refs(study_design: dict, study_version: dict) -> None:
    """
    Reconcile estimand.interventionIds → StudyIntervention references.

    Per USDM v4.0, Estimand.interventionIds is a 1..* array referencing
    StudyIntervention entities on StudyVersion.  The objectives phase
    generates estimands with LLM-created placeholder IDs (e.g. "{id}_int")
    that don't resolve to real entities.  This function links them by
    matching treatment text against intervention names.

    Matching strategy (per expert panel consensus):
      1. Already valid — interventionId exists in the StudyIntervention set
      2. Exact name match (estimand.treatment text == intervention.name)
      3. Keyword / alias match (brand↔generic, INN↔trade name patterns)
      4. Word-overlap fuzzy match (>30 % of words in common)
      5. Arm-type heuristic — investigational arm interventions for primary
         estimands, all interventions otherwise

    ICH E9(R1) Attribute 1: Treatment condition must be specified.
    """
    estimands = study_design.get('estimands', [])
    if not estimands:
        return

    interventions = study_version.get('studyInterventions', [])
    if not interventions:
        return

    int_ids = {si.get('id') for si in interventions if si.get('id')}

    # Build a rich text index for each intervention
    # (name + administration names + product names for broader matching)
    int_text_index: list = []  # [(intervention_dict, set_of_normalized_terms)]
    for si in interventions:
        terms: set = set()
        name = (si.get('name') or '').strip()
        if name:
            terms.add(_norm_intv(name))
            terms |= set(_norm_intv(name).split())
        label = (si.get('label') or '').strip()
        if label:
            terms.add(_norm_intv(label))
        # Nested administrations
        for adm in si.get('administrations', []):
            adm_name = (adm.get('name') or '').strip()
            if adm_name:
                terms.add(_norm_intv(adm_name))
                terms |= set(_norm_intv(adm_name).split())
        int_text_index.append((si, terms))

    # Intervention role classification
    _IMP_ROLES = {'experimental intervention', 'investigational', 'active comparator'}

    def _is_investigational(si: dict) -> bool:
        role = si.get('role', {})
        if isinstance(role, dict):
            decode = (role.get('decode') or '').lower()
        elif isinstance(role, str):
            decode = role.lower()
        else:
            decode = ''
        return any(r in decode for r in _IMP_ROLES)

    def _find_matching_interventions(est: dict) -> list:
        """Return list of matching StudyIntervention IDs for an estimand."""
        treatment_text = _norm_intv(
            est.get('treatment', '') or est.get('name', '')
        )
        if not treatment_text:
            return []

        # Pass 1: Exact name match
        for si, terms in int_text_index:
            if treatment_text in terms or _norm_intv(si.get('name', '')) == treatment_text:
                return [si['id']]

        # Pass 2: Keyword overlap — if treatment text contains an intervention name
        for si, terms in int_text_index:
            si_name = _norm_intv(si.get('name', ''))
            if si_name and (si_name in treatment_text or treatment_text in si_name):
                return [si['id']]

        # Pass 3: Word-overlap fuzzy match
        treat_words = set(treatment_text.split())
        if not treat_words:
            return []
        best_si = None
        best_overlap = 0.0
        for si, terms in int_text_index:
            if not terms:
                continue
            overlap = len(treat_words & terms) / max(len(treat_words), len(terms))
            if overlap > best_overlap and overlap > 0.3:
                best_overlap = overlap
                best_si = si
        if best_si:
            return [best_si['id']]

        # Pass 4: Heuristic — for primary estimands, use investigational interventions;
        #          otherwise return all interventions
        imp_ids = [si['id'] for si in interventions if _is_investigational(si)]
        if imp_ids:
            return imp_ids
        return [si['id'] for si in interventions]

    reconciled = 0
    for est in estimands:
        current_ids = est.get('interventionIds', [])

        # Check if all current IDs are already valid
        if current_ids and all(cid in int_ids for cid in current_ids):
            continue

        matches = _find_matching_interventions(est)
        if matches:
            est['interventionIds'] = matches
            reconciled += 1
            matched_names = [
                si.get('name', '?')[:30]
                for si in interventions if si.get('id') in matches
            ]
            logger.info(
                f"  Reconciled estimand '{est.get('name', '?')[:40]}' "
                f"interventionIds → {matched_names}"
            )

    if reconciled:
        logger.info(
            f"  Reconciled {reconciled}/{len(estimands)} "
            f"estimand → intervention references"
        )


def _norm_intv(text: str) -> str:
    """Normalize intervention text for matching."""
    return text.lower().strip().replace('-', ' ').replace('_', ' ')


def reconcile_method_estimand_refs(study_design: dict) -> None:
    """SAP-1: Reconcile SAP statistical methods → estimand references.

    Per ICH E9(R1), each estimand should be linked to the statistical method
    used to estimate it.  The SAP phase extracts ``statisticalMethods`` as an
    extension attribute on StudyDesign.  This function cross-links each method
    to the estimand(s) it targets by matching the method's endpoint reference
    to the estimand's endpoint.

    Matching strategy:
      1. Exact endpoint name match (method.endpointName == endpoint.name)
      2. Endpoint level match (method targets "primary" → primary estimands)
      3. Word-overlap fuzzy match (>40% overlap)

    Creates ``estimandId`` on each matched method and ``methodIds`` extension
    on each matched estimand.
    """
    estimands = study_design.get('estimands', [])
    if not estimands:
        return

    # Find statistical methods from extension
    methods = []
    methods_ext = None
    for ext in study_design.get('extensionAttributes', []):
        if isinstance(ext, dict) and 'statistical-methods' in ext.get('url', ''):
            val = ext.get('valueObject')
            if isinstance(val, list):
                methods = val
                methods_ext = ext
            break

    if not methods:
        return

    # Build endpoint lookup from objectives
    ep_by_id: dict = {}
    ep_by_name: dict = {}
    for obj in study_design.get('objectives', []):
        if not isinstance(obj, dict):
            continue
        for ep in obj.get('endpoints', []):
            if not isinstance(ep, dict):
                continue
            ep_id = ep.get('id', '')
            ep_name = (ep.get('name') or '').lower().strip()
            if ep_id:
                ep_by_id[ep_id] = ep
            if ep_name:
                ep_by_name[ep_name] = ep

    # Build estimand → endpoint mapping
    est_by_endpoint: dict = {}  # endpoint_id → [estimand]
    est_by_level: dict = {}     # level_str → [estimand]
    for est in estimands:
        if not isinstance(est, dict):
            continue
        var_id = est.get('variableOfInterestId', '')
        if var_id:
            est_by_endpoint.setdefault(var_id, []).append(est)
        # Level
        level = est.get('level', {})
        if isinstance(level, dict):
            lvl_decode = (level.get('decode') or '').lower()
        elif isinstance(level, str):
            lvl_decode = level.lower()
        else:
            lvl_decode = ''
        if lvl_decode:
            est_by_level.setdefault(lvl_decode, []).append(est)

    reconciled = 0
    for method in methods:
        if not isinstance(method, dict):
            continue

        method_ep_name = (method.get('endpointName') or method.get('endpoint') or '').lower().strip()
        method_level = (method.get('level') or method.get('endpointLevel') or '').lower().strip()

        matched_estimands = []

        # Pass 1: Exact endpoint name → find endpoint → find estimand
        if method_ep_name and method_ep_name in ep_by_name:
            ep = ep_by_name[method_ep_name]
            ep_id = ep.get('id', '')
            if ep_id in est_by_endpoint:
                matched_estimands = est_by_endpoint[ep_id]

        # Pass 2: Endpoint name substring match
        if not matched_estimands and method_ep_name:
            for epn, ep in ep_by_name.items():
                if method_ep_name in epn or epn in method_ep_name:
                    ep_id = ep.get('id', '')
                    if ep_id in est_by_endpoint:
                        matched_estimands = est_by_endpoint[ep_id]
                        break

        # Pass 3: Level-based match (primary method → primary estimand)
        if not matched_estimands and method_level:
            for lvl_key in ('primary', 'secondary', 'exploratory'):
                if lvl_key in method_level and lvl_key in est_by_level:
                    matched_estimands = est_by_level[lvl_key]
                    break

        # Pass 4: Word-overlap fuzzy match on endpoint name
        if not matched_estimands and method_ep_name:
            method_words = set(method_ep_name.split())
            best_est_list = []
            best_overlap = 0.0
            for ep_id, ests in est_by_endpoint.items():
                ep = ep_by_id.get(ep_id, {})
                ep_name = (ep.get('name') or '').lower()
                ep_words = set(ep_name.split())
                if not ep_words:
                    continue
                overlap = len(method_words & ep_words) / max(len(method_words), len(ep_words))
                if overlap > best_overlap and overlap > 0.4:
                    best_overlap = overlap
                    best_est_list = ests
            if best_est_list:
                matched_estimands = best_est_list

        # Apply binding
        if matched_estimands:
            method['estimandIds'] = [e.get('id') for e in matched_estimands if e.get('id')]
            for est in matched_estimands:
                method_ids = est.setdefault('_methodIds', [])
                mid = method.get('id') or method.get('name', '')
                if mid and mid not in method_ids:
                    method_ids.append(mid)
            reconciled += 1

    # Update the extension in place
    if methods_ext and reconciled:
        methods_ext['valueObject'] = methods

    if reconciled:
        logger.info(
            f"  ✓ SAP-1: Linked {reconciled}/{len(methods)} "
            f"statistical methods to estimands"
        )
