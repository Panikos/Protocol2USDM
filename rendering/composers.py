"""
M11 entity composers — generate section text from USDM entities.

Each composer reads structured USDM entities and produces formatted text
for a specific M11 section. Composers work independently of PDF extraction,
enabling future USDM-first authoring.

Composers:
  - _compose_synopsis       → §1.1.2 Overall Design
  - _compose_objectives     → §3 Objectives and Endpoints
  - _compose_study_design   → §4 Trial Design
  - _compose_eligibility    → §5 Study Population
  - _compose_interventions  → §6 Trial Interventions
  - _compose_discontinuation→ §7 Discontinuation
  - _compose_estimands      → §3.1 Estimands
  - _compose_safety         → §9 Adverse Events / Safety
  - _compose_statistics     → §10 Statistical Considerations
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _has_section_type(item: Dict[str, Any], expected: str) -> bool:
    """Return True when an item has a matching sectionType code/decode."""
    section_type = item.get('sectionType', {})
    if not isinstance(section_type, dict):
        return False

    expected_norm = expected.strip().lower()
    code = str(section_type.get('code', '')).strip().lower()
    decode = str(section_type.get('decode', '')).strip().lower()
    return code == expected_norm or decode == expected_norm


def _extract_participant_count_from_narrative(usdm: Dict) -> Optional[str]:
    """Extract participant count from narrative text as fallback.

    Scans synopsis (§1) and population (§5) narrative sections for patterns
    like 'approximately N participants', 'enroll N subjects', etc.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])

    # Collect text from synopsis and population sections
    texts = []
    for item in nc + nci:
        if not isinstance(item, dict):
            continue
        num = item.get('sectionNumber', '')
        if num.startswith('1') or num.startswith('5'):
            texts.append(item.get('text', ''))

    combined = ' '.join(texts)
    if not combined:
        return None

    # Pattern: "approximately N participants/subjects/patients"
    m = re.search(
        r'(?:approximately|up\s+to|total\s+of|enroll(?:ing)?|planned|target)\s+'
        r'(\d+)\s*(?:participants?|subjects?|patients?)',
        combined, re.IGNORECASE
    )
    if m:
        return m.group(1)

    # Pattern: "N participants/subjects" (simple)
    m = re.search(r'\b(\d{1,4})\s+(?:participants?|subjects?|patients?)\b', combined, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 10000:  # Reasonable trial size
            return str(n)

    return None


def _compose_synopsis(usdm: Dict) -> str:
    """Compose Section 1.1.2 Overall Design from USDM study design entities.

    The M11 Synopsis Overall Design block has ~27 structured fields with
    controlled-terminology pick-lists.  This composer extracts what is
    available in the USDM and formats them as a labelled field list that
    the renderer can emit as a structured table or text block.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    fields: List[tuple] = []

    # ---- Intervention Model ----
    model = design.get('model', design.get('interventionModel', {}))
    if isinstance(model, dict) and model.get('decode'):
        fields.append(('Intervention Model', model['decode']))

    # ---- Population Type ----
    pop = design.get('population', design.get('populations', {}))
    if isinstance(pop, list):
        pop = pop[0] if pop else {}
    if isinstance(pop, dict):
        healthy = pop.get('includesHealthySubjects', None)
        if healthy is True:
            fields.append(('Population Type', 'Healthy Volunteers'))
        elif healthy is False:
            fields.append(('Population Type', 'Patient'))

    # ---- Population Diagnosis or Condition ----
    indications = design.get('indications', [])
    if indications:
        cond_names = [ind.get('name', '') for ind in indications
                      if isinstance(ind, dict) and ind.get('name')]
        if cond_names:
            fields.append(('Population Diagnosis or Condition', '; '.join(cond_names)))

    # ---- Control Type ----
    arms = design.get('arms', design.get('studyArms', []))
    arm_types = []
    for arm in arms:
        if isinstance(arm, dict):
            at = arm.get('type', {})
            decode = at.get('decode', '') if isinstance(at, dict) else ''
            if decode:
                arm_types.append(decode)
    # Infer control type from arm types
    control_types = [t for t in arm_types if any(
        kw in t.lower() for kw in ['placebo', 'comparator', 'control', 'sham', 'no intervention'])]
    if control_types:
        fields.append(('Control Type', ', '.join(set(control_types))))
    elif len(arms) == 1:
        fields.append(('Control Type', 'None'))

    # ---- Population Age (min/max) ----
    if isinstance(pop, dict):
        # USDM v4.0: plannedAge is a Range {minValue: Quantity, maxValue: Quantity}
        planned_age = pop.get('plannedAge', {})
        if isinstance(planned_age, dict) and (planned_age.get('minValue') or planned_age.get('maxValue')):
            raw_min = planned_age.get('minValue', '')
            raw_max = planned_age.get('maxValue', '')
            # Support both Quantity objects and raw ints (backward compat)
            age_min = raw_min.get('value', raw_min) if isinstance(raw_min, dict) else raw_min
            age_max = raw_max.get('value', raw_max) if isinstance(raw_max, dict) else raw_max
            # Unit may be on the Quantity or on the Range itself (legacy)
            age_unit = planned_age.get('unit', 'Years')
            if isinstance(age_unit, dict):
                age_unit = age_unit.get('decode', age_unit.get('standardCode', {}).get('decode', 'Years'))
            if isinstance(raw_min, dict) and raw_min.get('unit'):
                u = raw_min['unit']
                age_unit = u.get('standardCode', {}).get('decode', u.get('decode', 'Years')) if isinstance(u, dict) else u
        else:
            # Fallback: legacy field names
            age_min = pop.get('plannedMinimumAgeOfSubjects', pop.get('minimumAge', ''))
            age_max = pop.get('plannedMaximumAgeOfSubjects', pop.get('maximumAge', ''))
            age_unit = pop.get('ageUnit', 'Years')
            if isinstance(age_unit, dict):
                age_unit = age_unit.get('decode', 'Years')
        if age_min or age_max:
            fields.append(('Population Age',
                           f'{age_min or "N/A"} to {age_max or "N/A"} {age_unit}'))

    # ---- Intervention Assignment Method ----
    rand_type = design.get('randomizationType', {})
    if isinstance(rand_type, dict) and rand_type.get('code'):
        fields.append(('Intervention Assignment Method',
                       rand_type.get('decode', rand_type.get('code', ''))))
    elif isinstance(rand_type, str) and rand_type:
        fields.append(('Intervention Assignment Method', rand_type))

    # ---- Stratification Indicator ----
    # Check randomization scheme extension for detailed stratification info
    _strat_text = None
    for _ext in design.get('extensionAttributes', []):
        if isinstance(_ext, dict) and 'randomizationScheme' in _ext.get('url', ''):
            _val = _ext.get('valueObject', _ext.get('value'))
            _scheme = None
            if isinstance(_val, str):
                try:
                    _scheme = json.loads(_val)
                except Exception:
                    pass
            elif isinstance(_val, dict):
                _scheme = _val
            if _scheme:
                _factors = _scheme.get('stratificationFactors', [])
                if _factors:
                    _parts = []
                    for _f in _factors:
                        _fname = _f.get('name', '')
                        _levels = _f.get('factorLevels', [])
                        _cats = _f.get('categories', [])
                        _n = len(_levels) if _levels else len(_cats)
                        _parts.append(f"{_fname} ({_n} levels)" if _n else _fname)
                    _method = _scheme.get('method', '')
                    _strat_text = f"Stratified by {', '.join(_parts)}"
                    if _method:
                        _strat_text += f" using {_method.lower()}"
            break

    if _strat_text:
        fields.append(('Stratification', _strat_text))
    else:
        cohorts = design.get('studyCohorts', [])
        pop = design.get('population', {})
        pop_cohorts = pop.get('cohorts', []) if isinstance(pop, dict) else []
        if cohorts or pop_cohorts:
            fields.append(('Stratification Indicator', 'Yes'))
        else:
            fields.append(('Stratification Indicator', 'No'))

    # ---- Site Distribution ----
    # Per USDM v4.0, StudySites live inside Organization.managedSites[]
    sites = []
    for org in version.get('organizations', []):
        sites.extend(org.get('managedSites', []))
    if len(sites) > 1:
        fields.append(('Site Distribution', 'Multi-site'))
    elif len(sites) == 1:
        fields.append(('Site Distribution', 'Single Site'))

    # ---- Site Geographic Scope ----
    if sites:
        countries = set()
        for site in sites:
            if isinstance(site, dict):
                country = site.get('country', {})
                if isinstance(country, dict):
                    decode = country.get('decode', '')
                    if decode:
                        countries.add(decode)
                elif isinstance(country, str) and country:
                    countries.add(country)
        if len(countries) > 1:
            fields.append(('Site Geographic Scope', 'Multi-Country'))
        elif len(countries) == 1:
            fields.append(('Site Geographic Scope', 'Single Country'))

    # ---- Master Protocol Indicator ----
    fields.append(('Master Protocol Indicator', 'No'))

    # ---- Drug/Device Combination Indicator ----
    fields.append(('Drug/Device Combination Product Indicator', 'No'))

    # ---- Adaptive Trial Design Indicator ----
    fields.append(('Adaptive Trial Design Indicator', 'No'))

    # ---- Number of Arms ----
    if arms:
        fields.append(('Number of Arms', str(len(arms))))

    # ---- Trial Blind Schema ----
    blinding = design.get('blindingSchema', {})
    if isinstance(blinding, dict):
        std_code = blinding.get('standardCode', blinding)
        if isinstance(std_code, dict):
            blind_text = std_code.get('decode', std_code.get('code', ''))
        else:
            blind_text = str(std_code) if std_code else ''
        if blind_text:
            fields.append(('Trial Blind Schema', blind_text))

    # ---- Blinded Roles ----
    masking_roles = design.get('maskingRoles', [])
    if masking_roles:
        role_texts = []
        for mr in masking_roles:
            if isinstance(mr, dict):
                if mr.get('isMasked'):
                    role_texts.append(mr.get('role', mr.get('text', '')))
                elif mr.get('text') and not mr.get('isMasked', True):
                    role_texts.append(mr.get('text', ''))
        if role_texts:
            fields.append(('Blinded Roles', '; '.join(role_texts)))

    # ---- Number of Participants ----
    if isinstance(pop, dict):
        # USDM v4.0: plannedEnrollmentNumber is a QuantityRange {maxValue, unit}
        enrollment = pop.get('plannedEnrollmentNumber', {})
        if isinstance(enrollment, dict):
            target_n = enrollment.get('maxValue', '')
        else:
            target_n = enrollment or ''
        # Fallback: legacy field names
        if not target_n:
            target_n = pop.get('plannedNumberOfSubjects', '')
        max_n = pop.get('plannedMaximumNumberOfSubjects', '')
        # Fallback: scan narrative for participant count
        if not target_n and not max_n:
            target_n = _extract_participant_count_from_narrative(usdm)
        if target_n or max_n:
            parts = []
            if target_n:
                parts.append(f'Target: {target_n}')
            if max_n:
                parts.append(f'Maximum: {max_n}')
            fields.append(('Number of Participants', ', '.join(parts)))
        # USDM v4.0: plannedCompletionNumber
        completion = pop.get('plannedCompletionNumber', {})
        if isinstance(completion, dict) and completion.get('maxValue'):
            fields.append(('Planned Completers', str(completion['maxValue'])))

    # ---- Duration ----
    epochs = design.get('epochs', design.get('studyEpochs', []))
    if epochs:
        epoch_names = [e.get('name', '') for e in epochs if isinstance(e, dict)]
        fields.append(('Trial Duration (epochs)', ' → '.join(epoch_names)))

    # ---- Committees ----
    # Check for DMC/DSMB mentions in conditions or extension attributes
    conditions = version.get('conditions', design.get('conditions', []))
    committee_names = []
    for cond in conditions:
        if isinstance(cond, dict):
            name = cond.get('name', '')
            if any(kw in name.lower() for kw in ['committee', 'dmc', 'dsmb', 'src', 'adjudication']):
                committee_names.append(name)
    if committee_names:
        fields.append(('Committees', '; '.join(committee_names)))

    if not fields:
        return ''

    # Format as structured field list
    lines = ['**Overall Design**', '']
    for label, value in fields:
        lines.append(f'  **{label}**: {value}')

    return '\n'.join(lines)


def _compose_interventions(usdm: Dict) -> str:
    """Compose Section 6 overview table from USDM intervention entities.

    M11 §6 starts with an optional overview table containing:
    Arm Name | Intervention Name | Type | Dose Form | Strength |
    Route | IMP/NIMP

    Data is assembled by joining studyInterventions → administrations → products.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    interventions = version.get('studyInterventions', [])
    if not interventions:
        return ''

    # Build lookup maps for cross-referencing by ID
    admins_list = version.get('administrations', design.get('administrations', []))
    admin_map = {a['id']: a for a in admins_list if isinstance(a, dict) and 'id' in a}

    products_list = version.get('administrableProducts', [])
    product_map = {p['id']: p for p in products_list if isinstance(p, dict) and 'id' in p}

    arms = design.get('arms', design.get('studyArms', []))
    arm_names = [a.get('name', '') for a in arms if isinstance(a, dict)]

    lines = ['**Trial Intervention Overview**', '']

    for si in interventions:
        if not isinstance(si, dict):
            continue

        name = si.get('name', '')
        desc = si.get('description', '')
        role = si.get('role', si.get('type', {}))
        role_decode = role.get('decode', '') if isinstance(role, dict) else ''

        # Classify IMP vs NIMP (C41161 = Experimental Intervention per USDM CT)
        role_lower = role_decode.lower()
        imp_class = 'IMP' if ('investigational' in role_lower or 'experimental' in role_lower) else 'NIMP'

        # Get administration details (route, frequency)
        # USDM v4.0: admins are inline in si.administrations[]; fall back to legacy administrationIds
        inline_admins = si.get('administrations', [])
        if not inline_admins:
            inline_admins = [admin_map.get(aid, {}) for aid in si.get('administrationIds', [])]
        routes = []
        for admin in inline_admins:
            if not isinstance(admin, dict):
                continue
            route = admin.get('route', {})
            route_text = route.get('decode', '') if isinstance(route, dict) else ''
            if route_text:
                routes.append(route_text)
            admin_desc = admin.get('description', '')
            if admin_desc and not routes:
                routes.append(admin_desc)

        # Get product details (dose form, strength)
        product_ids = si.get('productIds', [])
        dose_forms = []
        strengths = []
        for pid in product_ids:
            prod = product_map.get(pid, {})
            df = prod.get('administrableDoseForm', {})
            df_text = df.get('decode', '') if isinstance(df, dict) else ''
            if df_text:
                dose_forms.append(df_text)
            strength = prod.get('strength', '')
            if strength:
                strengths.append(str(strength))

        # Build intervention entry
        lines.append(f'  **{name}** ({imp_class})')
        if desc:
            lines.append(f'    Description: {desc}')
        if role_decode:
            lines.append(f'    Type: {role_decode}')
        if dose_forms:
            lines.append(f'    Dose Form: {", ".join(dose_forms)}')
        if strengths:
            lines.append(f'    Strength: {", ".join(strengths)}')
        if routes:
            lines.append(f'    Route: {", ".join(set(routes))}')
        lines.append('')

    # Arm assignment summary
    if arm_names:
        lines.append(f'**Arms**: {", ".join(arm_names)}')

    return '\n'.join(lines)


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

        # Endpoints (USDM v4.0: 'endpoints' inline, legacy: 'objectiveEndpoints')
        ep_list = obj.get('endpoints', obj.get('objectiveEndpoints', []))
        for ep in ep_list:
            if isinstance(ep, dict):
                ep_text = ep.get('text', ep.get('endpointText', ''))
                ep_level = ep.get('level', ep.get('endpointLevel', {}))
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

    # §4.3 Method of Treatment Assignment
    assignment_text = _compose_treatment_assignment(usdm)
    if assignment_text:
        lines.append('')
        lines.append(assignment_text)

    # §4.3 Blinding Procedures (M11-1)
    blinding_text = _compose_blinding_procedures(usdm)
    if blinding_text:
        lines.append('')
        lines.append(blinding_text)

    return '\n'.join(lines)


def _compose_treatment_assignment(usdm: Dict) -> str:
    """Compose §4.3 Method of Treatment Assignment from randomization scheme.

    ICH M11 §4.3 requires:
      - Method of randomization
      - Stratification factors and their levels
      - Allocation ratio
      - IWRS/IXRS system
      - Allocation concealment method

    Data sourced from x-executionModel-randomizationScheme extension.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # Find the randomization scheme extension
    scheme = None
    for ext in design.get('extensionAttributes', []):
        if isinstance(ext, dict) and 'randomizationScheme' in ext.get('url', ''):
            val = ext.get('valueObject', ext.get('value'))
            if isinstance(val, str):
                try:
                    scheme = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(val, dict):
                scheme = val
            break

    if not scheme:
        return ''

    lines = ['**4.3 Method of Treatment Assignment**', '']

    # Method
    method = scheme.get('method', '')
    if method:
        lines.append(f"Participants will be assigned to treatment using {method.lower()}.")

    # Allocation ratio
    ratio = scheme.get('ratio', '')
    arms = design.get('studyArms', design.get('arms', []))
    if ratio:
        arm_names = [a.get('name', '') for a in arms if isinstance(a, dict) and a.get('name')]
        if arm_names:
            lines.append(
                f"The allocation ratio will be {ratio} "
                f"({' : '.join(arm_names)})."
            )
        else:
            lines.append(f"The allocation ratio will be {ratio}.")

    # Block size
    block_sizes = scheme.get('blockSizes', [])
    block_size = scheme.get('blockSize')
    if block_sizes and len(block_sizes) > 1:
        sizes_str = ', '.join(str(s) for s in block_sizes)
        lines.append(f"Variable block sizes of {sizes_str} will be used.")
    elif block_size:
        lines.append(f"A fixed block size of {block_size} will be used.")

    # Stratification factors
    factors = scheme.get('stratificationFactors', [])
    if factors:
        lines.append('')
        lines.append('Randomization will be stratified by the following factors:')
        lines.append('')
        for factor in factors:
            fname = factor.get('name', '')
            levels = factor.get('factorLevels', [])
            categories = factor.get('categories', [])
            level_labels = [fl.get('label', '') for fl in levels] if levels else categories

            if level_labels:
                levels_str = ', '.join(level_labels)
                lines.append(f"  - **{fname}**: {levels_str}")
            else:
                lines.append(f"  - **{fname}**")
        lines.append('')

    # IWRS / central randomization
    iwrs = scheme.get('iwrsSystem')
    central = scheme.get('centralRandomization', False)
    if iwrs:
        lines.append(
            f"Treatment assignment will be managed through an interactive "
            f"response technology system ({iwrs})."
        )
    elif central:
        lines.append(
            "Treatment assignment will be managed through a central "
            "interactive response technology system."
        )

    # Allocation concealment
    concealment = scheme.get('concealmentMethod')
    if concealment:
        lines.append(f"Allocation concealment will be maintained via {concealment.lower()}.")

    # Adaptive design note
    if scheme.get('isAdaptive'):
        rules = scheme.get('adaptiveRules', '')
        if rules:
            lines.append(f"\nThis study uses response-adaptive randomization. {rules}")
        else:
            lines.append("\nThis study uses response-adaptive randomization.")

    return '\n'.join(lines)


def _compose_blinding_procedures(usdm: Dict) -> str:
    """Compose §4.3 Blinding Procedures from USDM masking data.

    ICH M11 §4.3 requires:
      - Description of the blinding/masking schema
      - Who is blinded (subjects, investigators, outcome assessors, etc.)
      - Measures to maintain blinding (matching placebos, packaging, etc.)
      - Emergency unblinding procedures
      - Conditions under which unblinding is permissible

    Data sourced from:
      - studyDesign.blindingSchema (Code)
      - studyDesign.maskingRoles (list of {role, isMasked})
      - studyDesign.masking (Masking entity with role[] codes)
      - Narrative content for §4 (unblinding procedures)
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # --- Blinding Schema ---
    blinding = design.get('blindingSchema', {})
    blind_text = ''
    if isinstance(blinding, dict):
        std_code = blinding.get('standardCode', blinding)
        if isinstance(std_code, dict):
            blind_text = std_code.get('decode', std_code.get('code', ''))
        else:
            blind_text = str(std_code) if std_code else ''
    elif isinstance(blinding, str):
        blind_text = blinding

    if not blind_text:
        return ''

    is_open = 'open' in blind_text.lower()
    lines = ['**4.3 Blinding**', '']

    if is_open:
        lines.append(f'This is an {blind_text.lower()} study. '
                      'No blinding or masking procedures are employed.')
        return '\n'.join(lines)

    # --- Describe the schema ---
    lines.append(f'This is a {blind_text.lower()} study.')

    # --- Masked Roles ---
    masking_roles = design.get('maskingRoles', [])
    masked = []
    unmasked = []
    for mr in masking_roles:
        if not isinstance(mr, dict):
            continue
        role_name = mr.get('role', mr.get('text', ''))
        if not role_name:
            continue
        if mr.get('isMasked', True):
            masked.append(role_name)
        else:
            unmasked.append(role_name)

    # Also check USDM masking.role[] codes
    masking_entity = design.get('masking', {})
    if isinstance(masking_entity, dict):
        for role_code in masking_entity.get('role', []):
            if isinstance(role_code, dict):
                role_decode = role_code.get('decode', '')
                if role_decode and role_decode not in masked:
                    masked.append(role_decode)

    if masked:
        roles_str = ', '.join(masked)
        lines.append(f'The following parties will be blinded to treatment assignment: {roles_str}.')

    if unmasked:
        roles_str = ', '.join(unmasked)
        lines.append(f'The following parties will not be blinded: {roles_str}.')

    # --- Blinding measures from narrative (only if present in source) ---
    blinding_narrative = (_find_narrative_about(version, 'maintain blind')
                          or _find_narrative_about(version, 'blinding procedure'))
    if blinding_narrative:
        lines.append('')
        lines.append(blinding_narrative)

    # --- Emergency unblinding from narrative (only if present in source) ---
    unblinding_text = _find_narrative_about(version, 'unblind')
    if unblinding_text:
        lines.append('')
        lines.append('**Emergency Unblinding**')
        lines.append('')
        lines.append(unblinding_text)

    return '\n'.join(lines)


def _find_narrative_about(version: dict, keyword: str) -> str:
    """Search narrative content items for text about a specific topic."""
    doc = version.get('documentedBy', version.get('studyDefinitionDocument', {}))
    if isinstance(doc, dict):
        contents = []
        for v in doc.get('versions', []):
            contents.extend(v.get('contents', []) if isinstance(v, dict) else [])
        if not contents:
            contents = doc.get('contents', [])
    else:
        contents = []

    for content in contents:
        if not isinstance(content, dict):
            continue
        for item in content.get('contentItems', content.get('items', [])):
            if not isinstance(item, dict):
                continue
            text = item.get('text', '')
            if keyword.lower() in text.lower() and len(text) > 50:
                return text

    return ''


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
            lines.append("**Inclusion Criteria**")
            for i, c in enumerate(inc, 1):
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"{i}. {text}")
            lines.append('')

        if exc:
            lines.append("**Exclusion Criteria**")
            for i, c in enumerate(exc, 1):
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"{i}. {text}")
            lines.append('')

        if other:
            lines.append("**Other Criteria**")
            for i, c in enumerate(other, 1):
                text = c.get('text', c.get('criterionText', ''))
                if text:
                    lines.append(f"{i}. {text}")

    return '\n'.join(lines)


def _compose_estimands(usdm: Dict) -> str:
    """Compose estimands subsection from USDM estimand entities.

    Handles three scenarios per ICH E9(R1) and M11 §3.1:
    1. Estimands explicitly defined → render full estimand framework
    2. Descriptive/exploratory study → note that estimands are not applicable
    3. Confirmatory study with missing estimands → note the gap
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    estimands = design.get('estimands', [])

    # Determine analysis approach from objectives summary (stored during extraction)
    approach = _get_analysis_approach(usdm)

    if not estimands:
        if approach == 'descriptive':
            return (
                'Estimands are not formally defined for this study. '
                'Per ICH E9(R1), the estimand framework is intended for confirmatory trials '
                'with pre-specified hypotheses. This study uses descriptive statistics only; '
                'statistical analyses are summarized in Section 10.'
            )
        elif approach == 'confirmatory':
            return (
                'No estimands were identified in the protocol. '
                'For confirmatory studies, ICH E9(R1) recommends defining estimands '
                'with all five attributes (treatment, population, variable, '
                'intercurrent events, and summary measure).'
            )
        return ''

    lines = ['Estimands (ICH E9(R1)):']
    for i, est in enumerate(estimands):
        if not isinstance(est, dict):
            continue
        name = est.get('name', f'Estimand {i+1}')
        summary = est.get('summaryMeasure', est.get('summary', ''))
        treatment = est.get('treatment', '')
        population = est.get('analysisPopulation', est.get('populationSummary', ''))
        variable = est.get('variableOfInterest', '')

        lines.append(f"\n  {name}:")
        if population:
            lines.append(f"    Population: {population}")
        if treatment:
            lines.append(f"    Treatment: {treatment}")
        if variable:
            lines.append(f"    Variable of Interest: {variable}")
        if summary:
            lines.append(f"    Summary Measure: {summary}")

        # Intercurrent events
        ices = est.get('intercurrentEvents', [])
        if ices:
            lines.append("    Intercurrent Events:")
            for ice in ices:
                if isinstance(ice, dict):
                    ice_name = ice.get('name', ice.get('intercurrentEventName', ''))
                    strategy = ice.get('strategy', ice.get('intercurrentEventStrategy', ''))
                    ice_text = ice.get('text', '')
                    if ice_name:
                        line = f"      - {ice_name}: Strategy = {strategy}"
                        if ice_text and ice_text != ice_name:
                            line += f" ({ice_text})"
                        lines.append(line)

    return '\n'.join(lines)


def _get_analysis_approach(usdm: Dict) -> str:
    """Extract analysisApproach from the objectives summary in USDM data.

    The approach is stored by the objectives extractor in the combined output
    under studyDesign > objectives summary, or as an extension attribute.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    # Check extension attributes for x-analysisApproach
    for ext in design.get('extensionAttributes', []):
        url = ext.get('url', '')
        if 'x-analysisApproach' in url:
            return ext.get('valueString', 'unknown').lower()

    return 'unknown'


def _compose_statistics(usdm: Dict) -> str:
    """Compose Section 10 content from SAP extension attributes."""
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


def _compose_safety(usdm: Dict) -> str:
    """Compose Section 9 content from narrative text containing safety info.

    Strategy: prefer sectionType-tagged items (extraction-time tagging),
    fall back to keyword scanning for older USDM outputs that lack tags.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}
    design = (version.get('studyDesigns', [{}]) or [{}])[0]

    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])
    all_items = nc + nci

    # --- Pass 1: sectionType-based filtering (preferred) ---
    tagged_items = []
    untagged_items = []
    for item in all_items:
        if not isinstance(item, dict):
            continue
        text = item.get('text', '')
        if not text or text == item.get('sectionTitle', item.get('name', '')):
            continue
        if _has_section_type(item, 'Safety'):
            tagged_items.append(item)
        else:
            untagged_items.append(item)

    # If we found tagged items, use them directly (no keyword scanning needed)
    if tagged_items:
        lines = []
        for item in tagged_items:
            title = item.get('sectionTitle', item.get('name', ''))
            text = item.get('text', '')
            source = item.get('sectionNumber', '')
            header = f'{source} {title}'.strip() if source else title
            lines.append(f'**{header}**\n{text}')
        return '\n\n'.join(lines)

    # --- Pass 2: keyword fallback for untagged USDM ---
    logger.warning("Safety composer: no sectionType='Safety' items found; "
                   "falling back to keyword scanning (legacy USDM)")
    safety_categories = {
        'ae_definition': {
            'keywords': ['adverse event', 'definition of ae', 'ae is defined',
                         'adverse experience'],
            'heading': 'Adverse Events',
        },
        'sae_definition': {
            'keywords': ['serious adverse event', 'definition of sae',
                         'sae is defined', 'serious adverse experience'],
            'heading': 'Serious Adverse Events',
        },
        'aesi': {
            'keywords': ['special interest', 'aesi', 'adverse event of special'],
            'heading': 'Adverse Events of Special Interest',
        },
        'reporting': {
            'keywords': ['reporting', 'pharmacovigilance', 'report to sponsor',
                         'expedited reporting', 'regulatory reporting',
                         'safety report'],
            'heading': 'Reporting Requirements',
        },
        'pregnancy': {
            'keywords': ['pregnancy', 'postpartum', 'contraception requirement',
                         'pregnancy test'],
            'heading': 'Pregnancy and Postpartum Information',
        },
        'follow_up': {
            'keywords': ['follow-up', 'follow up of ae', 'ae follow',
                         'safety follow'],
            'heading': 'Follow-up of AEs and SAEs',
        },
        'general_safety': {
            'keywords': ['safety', 'tolerability', 'adverse', 'toxicity',
                         'overdose', 'medication error'],
            'heading': 'General Safety',
        },
    }

    categorized: Dict[str, List[str]] = {k: [] for k in safety_categories}

    for item in untagged_items:
        title = item.get('sectionTitle', item.get('name', ''))
        text = item.get('text', '')
        combined = f'{title} {text[:1000]}'.lower()

        for cat_key, cat_def in safety_categories.items():
            if any(kw in combined for kw in cat_def['keywords']):
                source = item.get('sectionNumber', '')
                header = f'{source} {title}'.strip() if source else title
                categorized[cat_key].append(f'**{header}**\n{text}')
                break

    # Also check conditions for safety-related stopping rules
    conditions = version.get('conditions', design.get('conditions', []))
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        name = cond.get('name', '')
        desc = cond.get('description', '')
        cond_text = cond.get('text', '')
        combined = f'{name} {desc} {cond_text}'.lower()
        if any(kw in combined for kw in ['safety', 'stopping', 'liver', 'toxicity']):
            categorized['general_safety'].append(
                f'**Safety Condition: {name}**\n{desc}\n{cond_text}'.strip()
            )

    lines = []
    for cat_key, cat_def in safety_categories.items():
        fragments = categorized.get(cat_key, [])
        if fragments:
            lines.append(f'**{cat_def["heading"]}**')
            lines.extend(fragments)
            lines.append('')

    if not lines:
        return ''

    return '\n\n'.join(lines)


def _compose_discontinuation(usdm: Dict) -> str:
    """Compose Section 7 content from narrative text containing discontinuation info.

    Many protocols embed discontinuation/withdrawal rules within the Study
    Intervention section (§6) or Study Population section (§5).

    Strategy: prefer sectionType-tagged items (extraction-time tagging),
    fall back to keyword scanning for older USDM outputs that lack tags.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])
    all_items = nc + nci

    # --- Pass 1: sectionType-based filtering (preferred) ---
    tagged_items = []
    untagged_items = []
    for item in all_items:
        if not isinstance(item, dict):
            continue
        text = item.get('text', '')
        if not text or text == item.get('sectionTitle', item.get('name', '')):
            continue
        if _has_section_type(item, 'Discontinuation'):
            tagged_items.append(item)
        else:
            untagged_items.append(item)

    if tagged_items:
        fragments = []
        for item in tagged_items:
            title = item.get('sectionTitle', item.get('name', ''))
            text = item.get('text', '')
            source = item.get('sectionNumber', '')
            header = f'{source} {title}'.strip() if source else title
            fragments.append(f'**{header}**\n{text}')
        return '\n\n'.join(fragments)

    # --- Pass 2: keyword fallback for untagged USDM ---
    logger.warning("Discontinuation composer: no sectionType='Discontinuation' items found; "
                   "falling back to keyword scanning (legacy USDM)")
    discontinuation_keywords = [
        'discontinu', 'withdraw', 'dropout', 'drop-out', 'drop out',
        'early termination', 'stopping rule', 'lost to follow',
        'premature', 'removal from study',
    ]

    pattern = re.compile('|'.join(discontinuation_keywords), re.IGNORECASE)

    fragments = []
    for item in untagged_items:
        title = item.get('sectionTitle', item.get('name', ''))
        text = item.get('text', '')

        if pattern.search(title) or pattern.search(text[:500]):
            source = item.get('sectionNumber', '')
            header = f'{source} {title}'.strip() if source else title
            fragments.append(f'**{header}**\n{text}')

    if not fragments:
        return ''

    return '\n\n'.join(fragments)


def _compose_glossary(usdm: Dict) -> str:
    """Compose Section 13 Glossary from USDM abbreviation entities.

    M11 §13 requires a glossary of terms and abbreviations.
    The narrative extractor populates `version.abbreviations[]` with
    Abbreviation entities that have `abbreviatedText` and `expansionText`.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    abbreviations = version.get('abbreviations', [])
    if not abbreviations:
        return ''

    # Sort alphabetically by abbreviated text
    sorted_abbrs = sorted(
        [a for a in abbreviations if isinstance(a, dict)],
        key=lambda a: (a.get('abbreviatedText', '') or a.get('name', '')).upper()
    )

    if not sorted_abbrs:
        return ''

    lines = ['**Abbreviations and Acronyms**', '']
    for abbr in sorted_abbrs:
        short = abbr.get('abbreviatedText', abbr.get('name', ''))
        expanded = abbr.get('expansionText', abbr.get('text', ''))
        if short and expanded:
            lines.append(f'  **{short}**: {expanded}')

    return '\n'.join(lines)


def _compose_references(usdm: Dict) -> str:
    """Compose Section 14 References from narrative content.

    Scans narrative sections for reference-related content.
    """
    study = usdm.get('study', {})
    versions = study.get('versions', [{}])
    version = versions[0] if versions else {}

    nc = version.get('narrativeContents', [])
    nci = version.get('narrativeContentItems', [])

    for item in nc + nci:
        if not isinstance(item, dict):
            continue
        num = item.get('sectionNumber', '')
        title = (item.get('sectionTitle', '') or item.get('name', '')).lower()
        if num.startswith('14') or 'reference' in title:
            text = item.get('text', '')
            if text and text != item.get('sectionTitle', ''):
                return text

    return ''
