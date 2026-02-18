"""
Post-processing steps for the combined USDM output.

Handles entity reconciliation, activity source marking, procedure linking,
SoA footnotes, epoch filtering, and activity reference updates.
"""

from typing import Dict, Optional, Any, List
import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)

_LINK_NAME_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_link_name(value: str) -> str:
    """Normalize names for resilient, word-boundary-safe matching."""
    return _LINK_NAME_NORMALIZE_RE.sub(" ", (value or "").lower()).strip()


def _is_whole_phrase_match(phrase: str, text: str) -> bool:
    if not phrase or not text:
        return False
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def _find_best_name_match(target_name: str, candidates: Dict[str, Any]) -> Optional[Any]:
    """Find best match by exact normalized name, then whole-phrase match.

    If multiple fuzzy matches have the same score, return None to avoid
    non-deterministic linking.
    """
    normalized_target = _normalize_link_name(target_name)
    if not normalized_target:
        return None

    exact = candidates.get(normalized_target)
    if exact is not None:
        return exact

    scored_matches = []
    for candidate_name, candidate_value in candidates.items():
        if not candidate_name:
            continue
        if _is_whole_phrase_match(candidate_name, normalized_target) or _is_whole_phrase_match(normalized_target, candidate_name):
            scored_matches.append((len(candidate_name.split()), candidate_value))

    if not scored_matches:
        return None

    scored_matches.sort(key=lambda m: m[0], reverse=True)
    if len(scored_matches) > 1 and scored_matches[0][0] == scored_matches[1][0]:
        return None

    return scored_matches[0][1]


def run_reconciliation(combined: dict, expansion_results: dict, soa_data: dict) -> dict:
    """Run entity reconciliation (epochs, encounters, activities)."""
    from core.reconciliation import (
        reconcile_epochs_from_pipeline,
        reconcile_encounters_from_pipeline,
        reconcile_activities_from_pipeline,
        enrich_epoch_names_with_clinical_type,
    )
    
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        
        # Get execution data
        execution_data = None
        if expansion_results and expansion_results.get('execution'):
            exec_result = expansion_results['execution']
            if exec_result.success:
                execution_data = exec_result.data
        
        # Epoch reconciliation
        soa_epochs = study_design.get("epochs", [])
        soa_encounters = study_design.get("encounters", [])
        
        if soa_epochs:
            enrich_epoch_names_with_clinical_type(soa_epochs, soa_encounters)
            
            # Get traversal sequence
            traversal_sequence = None
            if execution_data and hasattr(execution_data, 'traversal_constraints'):
                constraints = execution_data.traversal_constraints or []
                if constraints and hasattr(constraints[0], 'required_sequence'):
                    traversal_sequence = constraints[0].required_sequence
            
            reconciled_epochs = reconcile_epochs_from_pipeline(
                soa_epochs=soa_epochs,
                traversal_sequence=traversal_sequence,
            )
            if reconciled_epochs:
                study_design["epochs"] = reconciled_epochs
                main_epochs = [e for e in reconciled_epochs if any(
                    ext.get("valueString") == "main"
                    for ext in e.get("extensionAttributes", [])
                    if ext.get("url", "").endswith("epochCategory")
                )]
                logger.info(f"  ✓ Reconciled {len(reconciled_epochs)} epochs ({len(main_epochs)} main)")
                
                # Fix dangling epochId references
                valid_epoch_ids = {e.get('id') for e in reconciled_epochs}
                fallback_epoch_id = reconciled_epochs[0].get('id') if reconciled_epochs else None
                for enc in study_design.get("encounters", []):
                    if enc.get('epochId') and enc['epochId'] not in valid_epoch_ids and fallback_epoch_id:
                        enc['epochId'] = fallback_epoch_id
        
        # Encounter reconciliation
        soa_encounters = study_design.get("encounters", [])
        if soa_encounters:
            visit_windows = None
            if execution_data and hasattr(execution_data, 'visit_windows'):
                visit_windows = [vw.__dict__ if hasattr(vw, '__dict__') else vw
                               for vw in (execution_data.visit_windows or [])]
            
            # Preserve transition rules before reconciliation (promoter adds these)
            transition_rules_by_name = {}
            for enc in soa_encounters:
                enc_name = enc.get('name', '')
                rules = {}
                if enc.get('transitionStartRule'):
                    rules['transitionStartRule'] = enc['transitionStartRule']
                if enc.get('transitionEndRule'):
                    rules['transitionEndRule'] = enc['transitionEndRule']
                if rules:
                    transition_rules_by_name[enc_name] = rules
            
            reconciled_encounters = reconcile_encounters_from_pipeline(
                soa_encounters=soa_encounters,
                visit_windows=visit_windows,
            )
            if reconciled_encounters:
                # Re-apply preserved transition rules to reconciled encounters
                for enc in reconciled_encounters:
                    rules = transition_rules_by_name.get(enc.get('name', ''))
                    if rules:
                        enc.update(rules)
                
                study_design["encounters"] = reconciled_encounters
                logger.info(f"  ✓ Reconciled {len(reconciled_encounters)} encounters")
                
                # Fix dangling SAI encounterId references + populate epochId
                valid_enc_ids = {enc.get('id') for enc in reconciled_encounters}
                enc_to_epoch = {enc.get('id'): enc.get('epochId') for enc in reconciled_encounters}
                fallback_enc_id = reconciled_encounters[0].get('id') if reconciled_encounters else None
                epochs = study_design.get('epochs', [])
                fallback_epoch_id = epochs[0].get('id') if epochs else None
                dangling_fixed = 0
                
                for timeline in study_design.get('scheduleTimelines', []):
                    for inst in timeline.get('instances', []):
                        enc_id = inst.get('encounterId')
                        # Remap dangling encounterId to nearest surviving encounter
                        if enc_id and enc_id not in valid_enc_ids:
                            inst['encounterId'] = fallback_enc_id or ''
                            dangling_fixed += 1
                        # Populate epochId from encounter mapping
                        if not inst.get('epochId'):
                            resolved_enc = inst.get('encounterId')
                            if resolved_enc and resolved_enc in enc_to_epoch:
                                inst['epochId'] = enc_to_epoch[resolved_enc]
                            elif fallback_epoch_id:
                                inst['epochId'] = fallback_epoch_id
                if dangling_fixed:
                    logger.info(f"  ✓ Fixed {dangling_fixed} dangling SAI encounterId references")
        
        # Activity reconciliation
        soa_activities = study_design.get("activities", [])
        if soa_activities:
            procedure_activities = None
            if expansion_results and expansion_results.get('procedures'):
                proc_result = expansion_results['procedures']
                if proc_result.success and proc_result.data:
                    if hasattr(proc_result.data, 'procedures'):
                        procedure_activities = [
                            p.__dict__ if hasattr(p, '__dict__') else p
                            for p in (proc_result.data.procedures or [])
                        ]
            
            execution_repetitions = None
            if execution_data and hasattr(execution_data, 'repetitions'):
                execution_repetitions = [r.__dict__ if hasattr(r, '__dict__') else r
                                        for r in (execution_data.repetitions or [])]
            
            footnote_conditions = None
            if execution_data and hasattr(execution_data, 'footnote_conditions'):
                footnote_conditions = [f.__dict__ if hasattr(f, '__dict__') else f
                                      for f in (execution_data.footnote_conditions or [])]
            
            activity_group_names = [g.get('name') for g in study_design.get('activityGroups', [])]
            
            reconciled_activities = reconcile_activities_from_pipeline(
                soa_activities=soa_activities,
                procedure_activities=procedure_activities,
                execution_repetitions=execution_repetitions,
                footnote_conditions=footnote_conditions,
                activity_group_names=activity_group_names,
            )
            if reconciled_activities:
                study_design["activities"] = reconciled_activities
                logger.info(f"  ✓ Reconciled {len(reconciled_activities)} activities")
                
                # Update activityIds in schedule instances
                update_activity_references(study_design, soa_activities, reconciled_activities)
    
    except Exception as e:
        logger.warning(f"  ⚠ Entity reconciliation skipped: {e}")
    
    return combined


def update_activity_references(study_design: dict, soa_activities: list, reconciled_activities: list) -> None:
    """Update activity references after reconciliation."""
    # Build name-to-ID mappings
    activity_name_to_new_id = {}
    for act in reconciled_activities:
        act_name = act.get('name', '').lower().strip()
        if act_name:
            activity_name_to_new_id[act_name] = act.get('id')
    
    old_id_to_new_id = {}
    for orig_act in soa_activities:
        orig_name = orig_act.get('name', '').lower().strip()
        orig_id = orig_act.get('id')
        if orig_name and orig_id and orig_name in activity_name_to_new_id:
            old_id_to_new_id[orig_id] = activity_name_to_new_id[orig_name]
    
    # Update activityGroups.childIds
    for group in study_design.get('activityGroups', []):
        old_child_ids = group.get('childIds', [])
        new_child_ids = []
        for old_id in old_child_ids:
            for orig_act in soa_activities:
                if orig_act.get('id') == old_id:
                    matched_name = orig_act.get('name', '').lower().strip()
                    if matched_name in activity_name_to_new_id:
                        new_child_ids.append(activity_name_to_new_id[matched_name])
                    break
        if new_child_ids:
            group['childIds'] = new_child_ids
    
    # Update schedule instances
    valid_activity_ids = {a.get('id') for a in reconciled_activities}
    updated = 0
    fixed_dangling = 0
    
    for timeline in study_design.get('scheduleTimelines', []):
        for inst in timeline.get('instances', []):
            old_act_ids = inst.get('activityIds', [])
            new_act_ids = [old_id_to_new_id.get(oid, oid) for oid in old_act_ids]
            
            if new_act_ids != old_act_ids:
                inst['activityIds'] = new_act_ids
                updated += 1
            
            # Fix dangling references
            valid_ids = [aid for aid in inst.get('activityIds', []) if aid in valid_activity_ids]
            if len(valid_ids) != len(inst.get('activityIds', [])):
                if valid_ids:
                    inst['activityIds'] = valid_ids
                else:
                    fallback = next(iter(valid_activity_ids), None)
                    if fallback:
                        inst['activityIds'] = [fallback]
                fixed_dangling += 1
    
    if updated > 0:
        logger.info(f"  ✓ Updated activityIds in {updated} schedule instances")
    if fixed_dangling > 0:
        logger.info(f"  ✓ Fixed {fixed_dangling} dangling activityIds")


def tag_unscheduled_encounters(combined: dict) -> dict:
    """Tag encounters as unscheduled based on name heuristics.
    
    This is a safety net for encounters that weren't tagged during
    reconciliation (e.g. loaded from existing USDM JSON).
    """
    from core.reconciliation.encounter_reconciler import is_unscheduled_encounter
    
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        encounters = study_design.get("encounters", [])
        tagged = 0
        
        for enc in encounters:
            name = enc.get("name", "")
            if not name:
                continue
            
            # Skip if already tagged
            exts = enc.get("extensionAttributes", [])
            already_tagged = any(
                e.get("url", "").endswith("x-encounterUnscheduled")
                for e in exts
            )
            if already_tagged:
                continue
            
            if is_unscheduled_encounter(name):
                if "extensionAttributes" not in enc:
                    enc["extensionAttributes"] = []
                enc["extensionAttributes"].append({
                    "id": str(uuid.uuid4()),
                    "url": "https://protocol2usdm.io/extensions/x-encounterUnscheduled",
                    "instanceType": "ExtensionAttribute",
                    "valueBoolean": True,
                })
                tagged += 1
        
        if tagged:
            logger.info(f"  ✓ Tagged {tagged} unscheduled encounter(s)")
    except Exception as e:
        logger.warning(f"  ⚠ Unscheduled encounter tagging skipped: {e}")
    
    return combined


def promote_unscheduled_to_decisions(combined: dict) -> dict:
    """Promote unscheduled encounters to ScheduledDecisionInstance entities.

    For each encounter tagged with x-encounterUnscheduled, creates:
      1. A ScheduledDecisionInstance (C201351) representing the branch point
      2. A Condition (C25457) describing the trigger event
      3. Two ConditionAssignment (C201335) entries:
         - "Event occurs" → branch to UNS encounter activities
         - Default → continue on main timeline (next scheduled encounter)
      4. Wires the SDI into the first schedule timeline's instances[]

    The encounter itself remains in the encounters list (it still holds
    activities); the SDI is a decision gate that *precedes* it.

    USDM placement:
      - ScheduledDecisionInstance → scheduleTimeline.instances[]
      - Condition → studyVersion.conditions[]
    """
    try:
        version = combined.get("study", {}).get("versions", [{}])[0]
        study_design = (version.get("studyDesigns", [{}]) or [{}])[0]
        encounters = study_design.get("encounters", [])
        timelines = study_design.get("scheduleTimelines", [])

        if not encounters or not timelines:
            return combined

        # Build ordered encounter list (for "next encounter" resolution)
        enc_order = [e.get("id") for e in encounters if e.get("id")]
        enc_by_id = {e.get("id"): e for e in encounters if e.get("id")}

        # Find the first timeline to add SDIs to
        timeline = timelines[0]
        if "instances" not in timeline:
            timeline["instances"] = []

        # Ensure conditions list exists on version
        if "conditions" not in version:
            version["conditions"] = []

        promoted = 0
        for enc in encounters:
            enc_id = enc.get("id", "")
            name = enc.get("name", "")
            exts = enc.get("extensionAttributes", [])

            # Check if tagged as unscheduled
            is_uns = any(
                e.get("url", "").endswith("x-encounterUnscheduled")
                and e.get("valueBoolean") is True
                for e in exts
            )
            if not is_uns:
                continue

            # Skip if already promoted (check for existing SDI referencing this encounter)
            already_promoted = any(
                inst.get("instanceType") == "ScheduledDecisionInstance"
                and any(
                    ca.get("conditionTargetId") == enc_id
                    for ca in inst.get("conditionAssignments", [])
                )
                for inst in timeline.get("instances", [])
            )
            if already_promoted:
                continue

            # Resolve "next scheduled encounter" for the default branch
            enc_idx = enc_order.index(enc_id) if enc_id in enc_order else -1
            next_enc_id = None
            if enc_idx >= 0:
                # Walk forward to find the next non-UNS encounter
                for j in range(enc_idx + 1, len(enc_order)):
                    candidate = enc_by_id.get(enc_order[j], {})
                    cand_exts = candidate.get("extensionAttributes", [])
                    cand_uns = any(
                        e.get("url", "").endswith("x-encounterUnscheduled")
                        and e.get("valueBoolean") is True
                        for e in cand_exts
                    )
                    if not cand_uns:
                        next_enc_id = enc_order[j]
                        break
                # If UNS is last in list, walk backward to find preceding encounter
                if next_enc_id is None:
                    for j in range(enc_idx - 1, -1, -1):
                        candidate = enc_by_id.get(enc_order[j], {})
                        cand_exts = candidate.get("extensionAttributes", [])
                        cand_uns = any(
                            e.get("url", "").endswith("x-encounterUnscheduled")
                            and e.get("valueBoolean") is True
                            for e in cand_exts
                        )
                        if not cand_uns:
                            next_enc_id = enc_order[j]
                            break

            # --- Create Condition entity ---
            condition_id = f"cond-uns-{enc_id}"
            condition = {
                "id": condition_id,
                "name": f"Unscheduled event trigger for {name}",
                "label": f"UNS trigger: {name}",
                "text": f"An event requiring an unscheduled {name} visit occurs",
                "instanceType": "Condition",
            }
            version["conditions"].append(condition)

            # --- Create ConditionAssignments ---
            # Branch 1: event occurs → go to UNS encounter
            ca_event = {
                "id": str(uuid.uuid4()),
                "condition": f"Event requiring {name} occurs",
                "conditionTargetId": enc_id,
                "instanceType": "ConditionAssignment",
            }

            # Branch 2 (default): event does not occur → next scheduled encounter
            ca_default = {
                "id": str(uuid.uuid4()),
                "condition": "No unscheduled event",
                "conditionTargetId": next_enc_id or enc_id,
                "instanceType": "ConditionAssignment",
            }

            # --- Create ScheduledDecisionInstance ---
            sdi_id = f"sdi-uns-{enc_id}"
            sdi = {
                "id": sdi_id,
                "name": f"Decision: {name}",
                "label": f"UNS Decision: {name}",
                "description": (
                    f"Branch point for unscheduled visit '{name}'. "
                    f"If the triggering event occurs, the subject proceeds to the "
                    f"unscheduled visit; otherwise continues on the main timeline."
                ),
                "epochId": enc.get("epochId"),
                "defaultConditionId": next_enc_id,
                "conditionAssignments": [ca_event, ca_default],
                "instanceType": "ScheduledDecisionInstance",
            }

            # Add UNS extension to the SDI for frontend identification
            sdi["extensionAttributes"] = [{
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-unsDecisionInstance",
                "instanceType": "ExtensionAttribute",
                "valueString": enc_id,
            }]

            timeline["instances"].append(sdi)
            promoted += 1

        if promoted:
            logger.info(f"  ✓ Promoted {promoted} UNS encounter(s) to ScheduledDecisionInstance")
    except Exception as e:
        logger.warning(f"  ⚠ UNS → SDI promotion skipped: {e}")

    return combined


def filter_enrichment_epochs(combined: dict, soa_data: Optional[dict]) -> dict:
    """Filter out epochs added by enrichment that weren't in original SoA."""
    if not soa_data:
        return combined
    
    # Get original SoA epoch names
    original_soa_epoch_names = set()
    try:
        soa_sd = soa_data.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        for epoch in soa_sd.get("epochs", []):
            original_soa_epoch_names.add(epoch.get("name", "").lower().strip())
    except (KeyError, IndexError, TypeError):
        return combined
    
    if not original_soa_epoch_names:
        return combined
    
    # Filter epochs
    try:
        post_enrich_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        if post_enrich_design.get("epochs"):
            original_epochs = []
            removed_epochs = []
            removed_epoch_ids = set()
            
            for epoch in post_enrich_design.get("epochs", []):
                epoch_name = epoch.get("name", "").lower().strip()
                if epoch_name in original_soa_epoch_names:
                    original_epochs.append(epoch)
                else:
                    removed_epochs.append(epoch.get("name", "Unknown"))
                    removed_epoch_ids.add(epoch.get("id"))
            
            if removed_epochs:
                post_enrich_design["epochs"] = original_epochs
                logger.info(f"  ✓ Filtered {len(removed_epochs)} non-SoA epochs: {removed_epochs}")

                # Clean up StudyCells that still point at removed epochs.
                cells = post_enrich_design.get("studyCells", [])
                if isinstance(cells, list):
                    filtered_cells = []
                    removed_cells = 0
                    for cell in cells:
                        if not isinstance(cell, dict):
                            filtered_cells.append(cell)
                            continue
                        if cell.get("epochId") in removed_epoch_ids:
                            removed_cells += 1
                            continue
                        filtered_cells.append(cell)

                    if removed_cells:
                        post_enrich_design["studyCells"] = filtered_cells
                        logger.info(f"  ✓ Removed {removed_cells} studyCell(s) tied to removed epochs")
                
                # Clean up timeline instances (preserve anchor instances)
                if removed_epoch_ids:
                    for timeline in post_enrich_design.get("scheduleTimelines", []):
                        instances = timeline.get("instances", [])
                        cleaned = []
                        for inst in instances:
                            if inst.get("epochId") not in removed_epoch_ids:
                                cleaned.append(inst)
                            else:
                                # Preserve anchor instances (they have anchorClassification extension)
                                ext_attrs = inst.get("extensionAttributes", [])
                                is_anchor = any(
                                    'anchorClassification' in (e.get('url', '') or '')
                                    for e in ext_attrs
                                )
                                if is_anchor:
                                    # Re-assign to first surviving epoch instead of dropping
                                    surviving_epochs = post_enrich_design.get("epochs", [])
                                    if surviving_epochs:
                                        inst["epochId"] = surviving_epochs[0].get("id")
                                    cleaned.append(inst)
                        if len(cleaned) < len(instances):
                            timeline["instances"] = cleaned
                            logger.info(f"  ✓ Cleaned {len(instances) - len(cleaned)} timeline instances")
        # Final guard: drop any StudyCell that references a non-existent epoch.
        valid_epoch_ids = {
            epoch.get("id")
            for epoch in post_enrich_design.get("epochs", [])
            if isinstance(epoch, dict) and isinstance(epoch.get("id"), str)
        }
        cells = post_enrich_design.get("studyCells", [])
        if valid_epoch_ids and isinstance(cells, list):
            pruned_cells = []
            invalid_cells = 0
            for cell in cells:
                if not isinstance(cell, dict):
                    pruned_cells.append(cell)
                    continue
                epoch_id = cell.get("epochId")
                if isinstance(epoch_id, str) and epoch_id and epoch_id not in valid_epoch_ids:
                    invalid_cells += 1
                    continue
                pruned_cells.append(cell)

            if invalid_cells:
                post_enrich_design["studyCells"] = pruned_cells
                logger.info(f"  ✓ Removed {invalid_cells} studyCell(s) with unresolved epochId")
    except Exception as e:
        logger.warning(f"  ⚠ Epoch filtering failed: {e}")
    
    return combined


def promote_activity_groups_to_parents(study_design: dict) -> None:
    """Convert non-schema activityGroups[] into parent Activity entities with childIds.

    USDM v4.0 has no ``activityGroups`` property on InterventionalStudyDesign.
    Activity grouping is expressed via ``Activity.childIds`` — parent activities
    that reference child activities.  This function:

    1. Takes each entry in ``studyDesign.activityGroups``
    2. Creates a parent Activity with ``childIds`` pointing to the group's members
    3. Prepends parent activities to ``studyDesign.activities``
    4. Removes the non-schema ``activityGroups`` array

    Must run **before** ``mark_activity_sources`` and CORE compliance.
    """
    groups = study_design.get('activityGroups', [])
    if not groups:
        return

    activities = study_design.get('activities', [])
    existing_ids = {a.get('id') for a in activities}

    parent_activities = []
    for group in groups:
        group_id = group.get('id', '')
        group_name = group.get('name', '')
        child_ids = group.get('childIds', group.get('activityIds', []))

        if not group_name:
            continue

        # Skip if a parent activity with this id already exists
        if group_id and group_id in existing_ids:
            # Just ensure childIds is set on the existing activity
            for act in activities:
                if act.get('id') == group_id:
                    act['childIds'] = child_ids
                    break
            continue

        parent = {
            'id': group_id or str(uuid.uuid4()),
            'name': group_name,
            'label': group_name,
            'description': group.get('description', group_name),
            'childIds': child_ids,
            'instanceType': 'Activity',
        }
        parent_activities.append(parent)

    if parent_activities:
        # Prepend parent activities so they appear before their children
        study_design['activities'] = parent_activities + activities
        logger.info(f"  ✓ Promoted {len(parent_activities)} activityGroups to parent Activities with childIds")

    # Remove the non-schema array
    study_design.pop('activityGroups', None)


def mark_activity_sources(study_design: dict) -> None:
    """Mark activities with their source (soa vs procedure_enrichment)."""
    try:
        scheduleTimelines = study_design.get('scheduleTimelines', [])
        if not scheduleTimelines:
            return
        
        instances = scheduleTimelines[0].get('instances', [])
        activity_ids_with_ticks = set()
        for inst in instances:
            activity_ids_with_ticks.update(inst.get('activityIds', []))
        
        soa_count = 0
        procedure_count = 0
        
        for activity in study_design.get('activities', []):
            act_id = activity.get('id')
            has_ticks = act_id in activity_ids_with_ticks
            
            if 'extensionAttributes' not in activity:
                activity['extensionAttributes'] = []
            
            # Remove existing activitySource
            activity['extensionAttributes'] = [
                ext for ext in activity['extensionAttributes']
                if not ext.get('url', '').endswith('activitySource')
            ]
            
            # Parent activities (with childIds) are SoA group headers even without direct ticks
            is_parent = bool(activity.get('childIds'))
            source = 'soa' if (has_ticks or is_parent) else 'procedure_enrichment'
            activity['extensionAttributes'].append({
                'id': f"ext_source_{act_id[:8] if act_id else 'unknown'}",
                'url': 'https://protocol2usdm.io/extensions/x-activitySource',
                'valueString': source,
                'instanceType': 'ExtensionAttribute'
            })
            
            if has_ticks:
                soa_count += 1
            else:
                procedure_count += 1
        
        logger.info(f"  ✓ Marked activities: {soa_count} SoA, {procedure_count} procedure enrichment")
        
        # Update parent activities' childIds to only include SoA activities
        for activity in study_design.get('activities', []):
            child_ids = activity.get('childIds', [])
            if child_ids:
                activity['childIds'] = [cid for cid in child_ids if cid in activity_ids_with_ticks]
    
    except Exception as e:
        logger.warning(f"  ⚠ Activity source marking skipped: {e}")


def link_procedures_to_activities(study_design: dict) -> None:
    """Link procedures to activities via definedProcedures."""
    try:
        procedures = study_design.get('procedures', [])
        activities = study_design.get('activities', [])
        
        if not procedures or not activities:
            return
        
        # Enrich procedure codes with multi-system terminology
        try:
            from core.procedure_codes import enrich_procedure_codes
            enriched = 0
            for proc in procedures:
                enrich_procedure_codes(proc)
                if any(e.get("url", "").endswith("x-procedureCodes") for e in proc.get("extensionAttributes", [])):
                    enriched += 1
            if enriched:
                logger.info(f"  ✓ Enriched {enriched}/{len(procedures)} procedures with multi-system codes")
        except Exception as e:
            logger.debug(f"  ⚠ Procedure code enrichment skipped: {e}")

        # Sanitize procedure codes
        for proc in procedures:
            code = proc.get('code')
            if code and isinstance(code, dict) and not code.get('code'):
                proc_type = proc.get('procedureType', 'Clinical Procedure')
                type_codes = {
                    'Diagnostic Procedure': ('C18020', 'Diagnostic Procedure'),
                    'Therapeutic Procedure': ('C49236', 'Therapeutic Procedure'),
                    'Surgical Procedure': ('C15329', 'Surgical Procedure'),
                    'Biospecimen Collection': ('C70945', 'Biospecimen Collection'),
                    'Diagnostic Imaging Testing': ('C16502', 'Diagnostic Imaging Testing'),
                    'Clinical Intervention or Procedure': ('C25218', 'Clinical Intervention or Procedure'),
                }
                default_code, default_decode = type_codes.get(proc_type, ('C25218', 'Clinical Procedure'))
                proc['code'] = {
                    'id': code.get('id') or str(uuid.uuid4()),
                    'code': default_code,
                    'codeSystem': 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl',
                    'codeSystemVersion': '25.01d',
                    'decode': default_decode,
                    'instanceType': 'Code',
                }
        
        # Build normalized name lookup
        proc_by_name = {
            _normalize_link_name(proc.get('name', '')): proc
            for proc in procedures
            if _normalize_link_name(proc.get('name', ''))
        }
        
        # Link procedures to activities
        linked_count = 0
        for activity in activities:
            matched_proc = _find_best_name_match(activity.get('name', ''), proc_by_name)
            
            if matched_proc:
                if 'definedProcedures' not in activity:
                    activity['definedProcedures'] = []
                existing_ids = {
                    (p.get('procedureId') or p.get('id'))
                    for p in activity['definedProcedures']
                    if isinstance(p, dict)
                }
                proc_id = matched_proc.get('id')
                if proc_id and proc_id not in existing_ids:
                    proc_ref = dict(matched_proc)
                    proc_ref.setdefault('procedureId', proc_id)
                    activity['definedProcedures'].append(proc_ref)
                    linked_count += 1
        
        if linked_count > 0:
            logger.info(f"  ✓ Linked {linked_count} procedures to activities")
    
    except Exception as e:
        logger.warning(f"  ⚠ Procedure-Activity linking skipped: {e}")


def link_administrations_to_products(combined: dict) -> dict:
    """H8: Link Administration.administrableProductId by name matching.
    
    Matches administrations to products by comparing normalized names
    (exact, then whole-phrase fuzzy matching).
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        products = sv.get("administrableProducts", [])
        administrations = combined.get("administrations", [])
        
        if not products or not administrations:
            return combined
        
        # Build normalized product name lookup (normalized name → id)
        prod_by_name = {}
        for p in products:
            name = _normalize_link_name(p.get("name") or "")
            if name:
                prod_by_name[name] = p.get("id")
        
        linked = 0
        for admin in administrations:
            if admin.get("administrableProductId"):
                continue  # already linked
            if not _normalize_link_name(admin.get("name") or ""):
                continue

            prod_id = _find_best_name_match(admin.get("name") or "", prod_by_name)
            
            if prod_id:
                admin["administrableProductId"] = prod_id
                linked += 1
        
        if linked:
            logger.info(f"  ✓ Linked {linked} administration(s) to products (H8)")
    except Exception as e:
        logger.warning(f"  ⚠ Administration→Product linking skipped: {e}")
    
    return combined


def nest_ingredients_in_products(combined: dict) -> dict:
    """H9: Nest Ingredient entities inside AdministrableProduct.ingredients.
    
    Matches ingredients to products by substance name overlap.
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        products = sv.get("administrableProducts", [])
        substances = combined.get("substances", [])
        
        if not products or not substances:
            return combined
        
        # Build substance id → name lookup
        substance_names = {s.get("id"): (s.get("name") or "").lower().strip() for s in substances}
        
        # Build ingredient list from substances (each substance becomes an ingredient)
        # Ingredients are typically stored flat in combined["substances"]
        # We need to nest them inside the matching product
        nested = 0
        for product in products:
            if product.get("ingredients"):
                continue  # already has ingredients
            
            prod_name = (product.get("name") or "").lower().strip()
            prod_substance_ids = product.get("substanceIds", [])
            
            matched_substances = []
            for sub in substances:
                sub_name = (sub.get("name") or "").lower().strip()
                sub_id = sub.get("id")
                
                # Match by explicit substanceIds link
                if sub_id in prod_substance_ids:
                    matched_substances.append(sub)
                    continue
                
                # Match by name overlap
                if sub_name and (sub_name in prod_name or prod_name in sub_name):
                    matched_substances.append(sub)
            
            if matched_substances:
                product["ingredients"] = []
                for sub in matched_substances:
                    ingredient = {
                        "id": f"ing_{sub.get('id', 'unknown')[:8]}",
                        "instanceType": "Ingredient",
                        "role": {
                            "code": "C82510",
                            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                            "codeSystemVersion": "25.01d",
                            "decode": "Active Moiety",
                            "instanceType": "Code",
                        },
                        "substance": sub,
                    }
                    product["ingredients"].append(ingredient)
                nested += len(matched_substances)
        
        if nested:
            logger.info(f"  ✓ Nested {nested} ingredient(s) in products (H9)")
    except Exception as e:
        logger.warning(f"  ⚠ Ingredient nesting skipped: {e}")
    
    return combined


def link_ingredient_strengths(combined: dict) -> dict:
    """H10: Link Ingredient.strengthId to matching Strength entity.
    
    If a product has a 'strength' string (e.g. '15 mg'), create a Strength
    entity and link it from the ingredient.
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        products = sv.get("administrableProducts", [])
        
        if not products:
            return combined
        
        linked = 0
        for product in products:
            strength_str = product.get("strength")
            ingredients = product.get("ingredients", [])
            
            if not strength_str or not ingredients:
                continue
            
            # Create a Strength entity for this product
            strength_id = f"str_{product.get('id', 'unknown')[:8]}"
            strength_entity = {
                "id": strength_id,
                "instanceType": "Quantity",
                "value": strength_str,
            }
            
            # Store strength entities on the product (USDM doesn't have a top-level strengths array)
            # Link each ingredient to this strength
            for ing in ingredients:
                if not ing.get("strengthId"):
                    ing["strengthId"] = strength_id
                    linked += 1
            
            # Store strength entities on the product for reference.
            # (USDM v4.0 has no top-level strengths collection.)
            if "strengths" not in product:
                product["strengths"] = []
            product["strengths"].append(strength_entity)
        
        if linked:
            logger.info(f"  ✓ Linked {linked} ingredient strength(s) (H10)")
    except Exception as e:
        logger.warning(f"  ⚠ Ingredient strength linking skipped: {e}")
    
    return combined


def link_cohorts_to_population(combined: dict) -> dict:
    """M3/M9: Link studyCohorts to StudyDesignPopulation.cohortIds."""
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        cohorts = study_design.get("studyCohorts", [])
        population = study_design.get("population")
        
        if cohorts and population:
            cohort_ids = [c.get("id") for c in cohorts if c.get("id")]
            if cohort_ids and not population.get("cohortIds"):
                population["cohortIds"] = cohort_ids
                logger.info(f"  ✓ Linked {len(cohort_ids)} cohort(s) to population (M3/M9)")
    except Exception as e:
        logger.warning(f"  ⚠ Cohort-population linking skipped: {e}")
    
    return combined


def add_soa_footnotes(study_design: dict, output_dir: str) -> None:
    """Add authoritative SoA footnotes from header_structure.json.
    
    Creates footnotes in two forms:
    1. x-soaFootnotes extension (backward compat for SoA table rendering)
    2. CommentAnnotation entities on Activity.notes[] and StudyDesign.notes[]
       (USDM v4.0 aligned — makes footnote IDs discoverable as proper entities)
    """
    try:
        header_path = os.path.join(output_dir, "4_header_structure.json")
        if not os.path.exists(header_path):
            return
        
        with open(header_path, 'r', encoding='utf-8') as f:
            header_data = json.load(f)
        
        soa_footnotes = header_data.get('footnotes', [])
        if not soa_footnotes:
            return
        
        if 'extensionAttributes' not in study_design:
            study_design['extensionAttributes'] = []
        
        # Remove existing SoA footnotes
        study_design['extensionAttributes'] = [
            ext for ext in study_design['extensionAttributes']
            if not ext.get('url', '').endswith('soaFootnotes')
        ]
        
        # Convert plain strings to objects with IDs so footnoteId refs resolve
        markers = 'abcdefghijklmnopqrstuvwxyz'
        footnote_objects = []
        for idx, fn in enumerate(soa_footnotes):
            if isinstance(fn, str):
                fn_obj = {
                    'id': f"fn_{idx + 1}",
                    'text': fn,
                }
                if idx < len(markers):
                    fn_obj['marker'] = markers[idx]
                footnote_objects.append(fn_obj)
            elif isinstance(fn, dict):
                if 'id' not in fn:
                    fn['id'] = f"fn_{idx + 1}"
                footnote_objects.append(fn)
        
        study_design['extensionAttributes'].append({
            'id': f"ext_soa_footnotes_{study_design.get('id', 'sd')[:8]}",
            'url': 'https://protocol2usdm.io/extensions/x-soaFootnotes',
            'valueString': json.dumps(footnote_objects),
            'instanceType': 'ExtensionAttribute'
        })
        logger.info(f"  ✓ Added {len(footnote_objects)} authoritative SoA footnotes (with IDs)")
        
        # --- USDM-aligned: promote to CommentAnnotation on Activity/StudyDesign notes ---
        _promote_footnotes_to_notes(study_design, footnote_objects, output_dir)
    
    except Exception as e:
        logger.warning(f"  ⚠ SoA footnotes addition skipped: {e}")


def _promote_footnotes_to_notes(
    study_design: dict,
    footnote_objects: list,
    output_dir: str,
) -> None:
    """Promote SoA footnotes to CommentAnnotation entities on USDM notes[] arrays.
    
    Uses the SoA provenance cellFootnotes mapping to place footnotes on the
    correct Activity.notes[] for cell-mapped footnotes, and on
    StudyDesign.notes[] for design-level footnotes.
    """
    markers = 'abcdefghijklmnopqrstuvwxyz'
    
    # Build marker → footnote object mapping
    marker_to_fn = {}
    for fn_obj in footnote_objects:
        m = fn_obj.get('marker', '')
        if m:
            marker_to_fn[m] = fn_obj
    
    # Load SoA provenance for cell-level footnote mapping
    prov_path = os.path.join(output_dir, "9_final_soa_provenance.json")
    cell_footnotes = {}
    if os.path.exists(prov_path):
        try:
            with open(prov_path, 'r', encoding='utf-8') as f:
                prov = json.load(f)
            cell_footnotes = prov.get('cellFootnotes', {})
        except Exception:
            pass
    
    # Load pre-reconciliation SoA to get act_N → activity name mapping
    soa_path = os.path.join(output_dir, "9_final_soa.json")
    act_n_to_name = {}
    if os.path.exists(soa_path):
        try:
            with open(soa_path, 'r', encoding='utf-8') as f:
                soa_data = json.load(f)
            soa_sd = soa_data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
            for i, act in enumerate(soa_sd.get('activities', [])):
                act_n_to_name[f"act_{i + 1}"] = act.get('name', '')
        except Exception:
            pass
    
    # Build reconciled activity name → activity dict (lowercase normalized)
    act_name_to_entity = {}
    norm_re = re.compile(r'[^a-z0-9]')
    for act in study_design.get('activities', []):
        name = act.get('name', '')
        if name:
            act_name_to_entity[name.lower()] = act
            act_name_to_entity[norm_re.sub('', name.lower())] = act
    
    # Build marker → set of reconciled activity dicts
    marker_to_activities: Dict[str, list] = {}
    for cell_key, fn_markers in cell_footnotes.items():
        act_key = cell_key.split('|')[0]
        soa_name = act_n_to_name.get(act_key, '')
        if not soa_name:
            continue
        # Find reconciled activity
        act_entity = act_name_to_entity.get(soa_name.lower())
        if not act_entity:
            act_entity = act_name_to_entity.get(norm_re.sub('', soa_name.lower()))
        if not act_entity:
            # Substring fallback
            for key, ent in act_name_to_entity.items():
                if len(key) > 3 and (soa_name.lower() in key or key in soa_name.lower()):
                    act_entity = ent
                    break
        if act_entity:
            for m in fn_markers:
                marker_to_activities.setdefault(m, [])
                if act_entity not in marker_to_activities[m]:
                    marker_to_activities[m].append(act_entity)
    
    # Place CommentAnnotation entities
    cell_placed = 0
    design_placed = 0
    
    for fn_obj in footnote_objects:
        m = fn_obj.get('marker', '')
        annotation = {
            'id': fn_obj['id'],
            'text': fn_obj.get('text', ''),
            'codes': [],
            'instanceType': 'CommentAnnotation',
        }
        
        target_activities = marker_to_activities.get(m, [])
        if target_activities:
            # Place on each mapped activity's notes[]
            for act in target_activities:
                act.setdefault('notes', [])
                # Avoid duplicates
                existing_ids = {n.get('id') for n in act['notes']}
                if annotation['id'] not in existing_ids:
                    act['notes'].append(annotation)
                    cell_placed += 1
        else:
            # Design-level footnote → StudyDesign.notes[]
            study_design.setdefault('notes', [])
            existing_ids = {n.get('id') for n in study_design['notes']}
            if annotation['id'] not in existing_ids:
                study_design['notes'].append(annotation)
                design_placed += 1
    
    if cell_placed or design_placed:
        logger.info(
            f"  ✓ Promoted {cell_placed + design_placed} footnotes to CommentAnnotation "
            f"({cell_placed} on Activity.notes[], {design_placed} on StudyDesign.notes[])"
        )


def validate_anchor_consistency(combined: dict, expansion_results: dict) -> dict:
    """Validate time anchor dayValues against SoA encounters.
    
    Checks that each extracted time anchor has a corresponding encounter
    in the SoA at the expected day value. Logs warnings for mismatches
    and stores validation results as an extension attribute.
    """
    import re as _re
    
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        encounters = study_design.get("encounters", [])
        
        # Get time anchors from execution data
        execution_data = None
        if expansion_results and expansion_results.get('execution'):
            exec_result = expansion_results['execution']
            if exec_result.success and exec_result.data:
                execution_data = exec_result.data
        
        if not execution_data or not hasattr(execution_data, 'time_anchors'):
            return combined
        
        time_anchors = execution_data.time_anchors or []
        if not time_anchors:
            return combined
        
        # Build set of day values present in SoA encounters
        encounter_days = set()
        encounter_names_lower = set()
        for enc in encounters:
            name = enc.get('name', '')
            encounter_names_lower.add(name.lower().strip())
            day_match = _re.search(r'day\s*[-]?\s*(\d+)', name.lower())
            if day_match:
                encounter_days.add(int(day_match.group(1)))
        
        # Validate each anchor
        validation_results = []
        warnings_count = 0
        
        for anchor in time_anchors:
            anchor_type = getattr(anchor, 'anchor_type', None)
            type_str = anchor_type.value if hasattr(anchor_type, 'value') else str(anchor_type or 'Unknown')
            day_value = getattr(anchor, 'day_value', None)
            definition = getattr(anchor, 'definition', '')
            
            result = {
                "anchorType": type_str,
                "dayValue": day_value,
                "definition": definition,
                "status": "ok",
                "message": "",
            }
            
            if day_value is not None:
                abs_day = abs(day_value)
                if abs_day in encounter_days or day_value in encounter_days:
                    result["status"] = "ok"
                    result["message"] = f"Day {day_value} has matching SoA encounter"
                else:
                    result["status"] = "warning"
                    result["message"] = f"Day {day_value} has no matching SoA encounter (available: {sorted(encounter_days)[:10]})"
                    warnings_count += 1
                    logger.warning(f"  ⚠ Anchor '{type_str}' (Day {day_value}): no matching SoA encounter")
            else:
                result["status"] = "info"
                result["message"] = "No day value specified"
            
            validation_results.append(result)
        
        # Store validation results as extension
        if validation_results:
            study_design.setdefault('extensionAttributes', []).append({
                'id': f"ext_anchor_validation_{study_design.get('id', 'sd')[:8]}",
                'url': 'https://protocol2usdm.io/extensions/x-anchorValidation',
                'valueString': json.dumps(validation_results),
                'instanceType': 'ExtensionAttribute'
            })
        
        ok_count = sum(1 for r in validation_results if r['status'] == 'ok')
        logger.info(f"  ✓ Anchor validation: {ok_count}/{len(validation_results)} anchors match SoA encounters"
                    + (f" ({warnings_count} warnings)" if warnings_count else ""))
    
    except Exception as e:
        logger.warning(f"  ⚠ Anchor consistency validation skipped: {e}")
    
    return combined


# ---------------------------------------------------------------------------
# Structural CORE Compliance Fixes
# (Run after reconciliation, before validation/UUID conversion)
# ---------------------------------------------------------------------------

def _extract_sort_key(name: str) -> float:
    """Extract a numeric sort key from an encounter/epoch name.

    Strategies (in order):
      1. Day number  — "Day -7", "Day 1", "Day 360"
      2. Week number — "Week -3", "Week 52"
      3. Visit number — "Visit 1", "V3a"
      4. Fallback    — large number (pushed to end)
    """
    if not name:
        return 9999.0
    low = name.lower()

    m = re.search(r'day\s*(-?\d+)', low)
    if m:
        return float(m.group(1))

    m = re.search(r'week\s*(-?\d+)', low)
    if m:
        return float(m.group(1)) * 7

    m = re.search(r'(?:visit|v)\s*(\d+)', low)
    if m:
        return float(m.group(1)) * 0.01

    terminal_kw = ("eos", "et ", "ptdv", "scv", "early termination",
                   "end of study", "end of treatment", "unscheduled",
                   "follow-up", "safety follow", "study closure",
                   "final treatment", "premature")
    for kw in terminal_kw:
        if kw in low:
            return 9990.0

    return 9999.0


def build_ordering_chains(study_design: Dict[str, Any]) -> int:
    """
    Populate ``previousId`` / ``nextId`` on epochs and encounters.

    **Epochs**: Use array position directly. The epoch reconciler
    (``_post_reconcile``) already sorts by ``(category, sequence_order)``
    which reflects the SoA column ordering — the authoritative source.
    Re-sorting would destroy this correct order.

    **Encounters**: Sort by temporal key (Day/Week/Visit number) with
    array index as stable tiebreaker for encounters that lack numeric names.

    Returns the number of links set.
    """
    epochs: List[Dict] = study_design.get("epochs", [])
    encounters: List[Dict] = study_design.get("encounters", [])

    if not epochs and not encounters:
        return 0

    linked = 0

    # --- Encounter chain: sort by temporal key, array index as tiebreaker ---
    if len(encounters) > 1:
        indexed = [(i, enc) for i, enc in enumerate(encounters)]
        indexed.sort(key=lambda t: (_extract_sort_key(t[1].get("name", "")), t[0]))
        sorted_encs = [enc for _, enc in indexed]
        for i, enc in enumerate(sorted_encs):
            if i > 0:
                enc["previousId"] = sorted_encs[i - 1].get("id")
                linked += 1
            else:
                enc.pop("previousId", None)
            if i < len(sorted_encs) - 1:
                enc["nextId"] = sorted_encs[i + 1].get("id")
                linked += 1
            else:
                enc.pop("nextId", None)

    # --- Epoch chain: use array position (reconciler order is authoritative) ---
    if len(epochs) > 1:
        for i, ep in enumerate(epochs):
            if i > 0:
                ep["previousId"] = epochs[i - 1].get("id")
                linked += 1
            else:
                ep.pop("previousId", None)
            if i < len(epochs) - 1:
                ep["nextId"] = epochs[i + 1].get("id")
                linked += 1
            else:
                ep.pop("nextId", None)

    return linked


_PRIMARY_OBJECTIVE_CODES = {"C85826"}
_PRIMARY_ENDPOINT_CODES = {"C94496", "C98772"}


def fix_primary_endpoint_linkage(study_design: Dict[str, Any]) -> int:
    """
    Ensure at least one primary endpoint is nested in a primary objective
    (CORE-000874) and that one primary endpoint exists (CORE-001036).

    Per USDM v4.0, endpoints are nested inline inside Objective.endpoints.
    Returns number of links fixed.
    """
    objectives: List[Dict] = study_design.get("objectives", [])
    if not objectives:
        return 0

    # Collect all endpoints from inside objectives
    all_endpoints = []
    for obj in objectives:
        all_endpoints.extend(obj.get("endpoints", []))

    if not all_endpoints:
        return 0

    fixed = 0

    def _get_code(code_obj):
        if isinstance(code_obj, dict):
            return code_obj.get("code", "")
        return ""

    primary_objs = [o for o in objectives
                    if _get_code(o.get("level")) in _PRIMARY_OBJECTIVE_CODES]
    primary_eps = [e for e in all_endpoints
                   if _get_code(e.get("level")) in _PRIMARY_ENDPOINT_CODES]

    if not primary_objs or not primary_eps:
        return 0

    for obj in primary_objs:
        obj_eps = obj.get("endpoints", [])
        has_primary = any(
            _get_code(ep.get("level")) in _PRIMARY_ENDPOINT_CODES
            for ep in obj_eps
        )
        if not has_primary:
            obj.setdefault("endpoints", []).append(primary_eps[0])
            fixed += 1

    return fixed


def fix_timing_references(study_design: Dict[str, Any]) -> int:
    """
    Populate ``relativeToScheduledInstanceId`` on timings that have a
    ``relativeFromScheduledInstanceId`` but are missing the "to" reference.

    Uses encounter-name matching to find the correct target SAI, falling
    back to the timeline anchor only when no encounter match is found.

    Returns number of timing references fixed.
    """
    timelines: List[Dict] = study_design.get("scheduleTimelines", [])
    if not timelines:
        return 0

    # Build encounter name → id lookup and day-range index
    encounters: List[Dict] = study_design.get("encounters", [])
    enc_by_name: Dict[str, str] = {}
    enc_day_ranges: List[tuple] = []
    for enc in encounters:
        ename = (enc.get("name") or "").strip()
        eid = enc.get("id", "")
        if ename and eid:
            enc_by_name[ename.lower()] = eid
            nums = [int(n) for n in re.findall(r"-?\d+", ename)]
            if nums:
                enc_day_ranges.append((eid, min(nums), max(nums)))

    fixed = 0
    for tl in timelines:
        entry_id = tl.get("entryId")
        instances = tl.get("instances", [])
        if not entry_id and instances:
            entry_id = instances[0].get("id")

        # Build encounter_id → first SAI id
        enc_to_sai: Dict[str, str] = {}
        for inst in instances:
            eid = inst.get("encounterId", "")
            if eid and eid not in enc_to_sai:
                enc_to_sai[eid] = inst.get("id", "")

        for timing in tl.get("timings", []):
            has_from = timing.get("relativeFromScheduledInstanceId")
            has_to = timing.get("relativeToScheduledInstanceId")
            if has_from and not has_to:
                # Try to resolve via encounter name matching
                tname = timing.get("name", timing.get("label", ""))
                m = re.match(r"Timing for (.+)", tname, re.IGNORECASE)
                enc_part = (m.group(1).strip() if m else tname).lower()

                matched_enc = enc_by_name.get(enc_part)
                if not matched_enc:
                    for ename_lower, eid in enc_by_name.items():
                        if enc_part in ename_lower or ename_lower in enc_part:
                            matched_enc = eid
                            break
                if not matched_enc:
                    day_m = re.search(r"(?:Day\s*)?(\d+)", enc_part, re.IGNORECASE)
                    if day_m:
                        target_day = int(day_m.group(1))
                        for eid, lo, hi in enc_day_ranges:
                            if lo <= target_day <= hi:
                                matched_enc = eid
                                break

                target_sai = enc_to_sai.get(matched_enc) if matched_enc else None
                if target_sai and target_sai != has_from:
                    timing["relativeToScheduledInstanceId"] = target_sai
                elif entry_id:
                    timing["relativeToScheduledInstanceId"] = entry_id
                fixed += 1

    return fixed


def resolve_name_as_id_references(combined: dict) -> int:
    """
    Resolve remaining name-as-ID references for substanceId, fromElementId, toElementId.
    
    These fields contain entity names instead of UUIDs. This function matches
    them to existing entities or creates new ones as needed.
    
    Returns count of resolved references.
    """
    resolved = 0
    sd = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
    sv = combined.get("study", {}).get("versions", [{}])[0]
    
    # --- substanceId resolution ---
    # Build substance name→ID lookup from existing substances
    substances = combined.get("substances", [])
    substance_lookup = {}
    for s in substances:
        sid = s.get("id", "")
        sname = s.get("name", "").lower()
        if sid and sname:
            substance_lookup[sname] = sid
            substance_lookup[re.sub(r'[^a-z0-9]', '', sname)] = sid
    
    # Also collect substance info from interventions
    for si in sv.get("studyInterventions", []):
        si_name = (si.get("name") or "").lower()
        si_id = si.get("id", "")
        # Intervention names often match substance names
        if si_name and si_id:
            for s in substances:
                if si_name in s.get("name", "").lower() or s.get("name", "").lower() in si_name:
                    substance_lookup[si_name] = s.get("id", "")
    
    UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    
    # Fix substanceId in _temp_ingredients and anywhere else
    for key in ("_temp_ingredients", "ingredients"):
        for ing in combined.get(key, []):
            sub_id = ing.get("substanceId", "")
            if sub_id and not UUID_RE.match(sub_id):
                # Name-as-ID: try lookup, else create substance
                name_lower = sub_id.lower()
                norm = re.sub(r'[^a-z0-9]', '', name_lower)
                match_id = substance_lookup.get(name_lower) or substance_lookup.get(norm)
                if not match_id:
                    # Substring match
                    for sname, sid in substance_lookup.items():
                        if name_lower in sname or sname in name_lower:
                            match_id = sid
                            break
                if not match_id:
                    # Create new substance entity
                    new_id = str(uuid.uuid4())
                    substances.append({
                        "id": new_id,
                        "name": sub_id,
                        "strengths": [{
                            "id": str(uuid.uuid4()),
                            "name": "Not specified",
                            "numerator": {
                                "id": str(uuid.uuid4()),
                                "value": 0,
                                "instanceType": "Quantity",
                            },
                            "instanceType": "Strength",
                        }],
                        "instanceType": "Substance",
                    })
                    substance_lookup[name_lower] = new_id
                    substance_lookup[norm] = new_id
                    match_id = new_id
                    combined["substances"] = substances
                
                ing["substanceId"] = match_id
                resolved += 1
    
    # --- fromElementId / toElementId resolution ---
    # Build element/epoch name→ID lookup
    element_lookup = {}
    for el in sd.get("elements", []):
        el_name = (el.get("name") or "").lower()
        el_id = el.get("id", "")
        if el_name and el_id:
            element_lookup[el_name] = el_id
            element_lookup[re.sub(r'[^a-z0-9]', '', el_name)] = el_id
    # Also include epochs (transition rules may reference epochs)
    for ep in sd.get("epochs", []):
        ep_name = (ep.get("name") or "").lower()
        ep_id = ep.get("id", "")
        if ep_name and ep_id:
            element_lookup[ep_name] = ep_id
            element_lookup[re.sub(r'[^a-z0-9]', '', ep_name)] = ep_id
    
    # Build dose amount→element mapping for dosing-related refs (e.g. "15 mg/day" → "Dose Step 1")
    dose_step_elements = sorted(
        [(el.get("name", ""), el.get("id", "")) for el in sd.get("elements", [])
         if "dose" in (el.get("name") or "").lower() and "step" in (el.get("name") or "").lower()],
        key=lambda x: x[0],  # Sort by name (Dose Step 1, Dose Step 2, ...)
    )
    
    # Fix transition rules
    for tr in combined.get("transitionRules", []):
        for field in ("fromElementId", "toElementId"):
            val = tr.get(field, "")
            if val and not UUID_RE.match(val):
                name_lower = val.lower()
                norm = re.sub(r'[^a-z0-9]', '', name_lower)
                match_id = element_lookup.get(name_lower) or element_lookup.get(norm)
                if not match_id:
                    for ename, eid in element_lookup.items():
                        if name_lower in ename or ename in name_lower:
                            match_id = eid
                            break
                # Dosing-specific fallback: match dose amounts to dose step elements
                if not match_id and dose_step_elements and re.search(r'\d+\s*mg', val):
                    dose_match = re.search(r'(\d+(?:\.\d+)?)\s*mg', val)
                    if dose_match:
                        dose_val = float(dose_match.group(1))
                        # Collect all dose refs in transition rules to determine ordering
                        all_doses = set()
                        for tr2 in combined.get("transitionRules", []):
                            for f2 in ("fromElementId", "toElementId"):
                                v2 = tr2.get(f2, "")
                                m2 = re.search(r'(\d+(?:\.\d+)?)\s*mg', v2) if v2 else None
                                if m2:
                                    all_doses.add(float(m2.group(1)))
                        sorted_doses = sorted(all_doses)
                        if dose_val in sorted_doses:
                            idx = sorted_doses.index(dose_val)
                            if idx < len(dose_step_elements):
                                match_id = dose_step_elements[idx][1]
                if match_id:
                    tr[field] = match_id
                    resolved += 1
    
    if resolved:
        logger.info(f"  ✓ Resolved {resolved} name-as-ID references (substance/element)")
    
    return resolved


def _build_enrollment_quantity(n: int) -> dict:
    """Build a USDM Range for plannedEnrollmentNumber.
    
    Per USDM v4.0: QuantityRange is abstract; concrete types are Quantity and Range.
    Range.minValue/maxValue are Quantity objects. Quantity.unit is an AliasCode.
    """
    def _make_unit_alias_code() -> dict:
        """Build an AliasCode for the 'Participant' unit."""
        return {
            'id': str(uuid.uuid4()),
            'standardCode': {
                'id': str(uuid.uuid4()),
                'code': 'C25613',
                'codeSystem': 'http://www.cdisc.org',
                'codeSystemVersion': '2024-09-27',
                'decode': 'Participant',
                'instanceType': 'Code',
            },
            'instanceType': 'AliasCode',
        }
    
    return {
        'id': str(uuid.uuid4()),
        'minValue': {
            'id': str(uuid.uuid4()),
            'value': n,
            'unit': _make_unit_alias_code(),
            'instanceType': 'Quantity',
        },
        'maxValue': {
            'id': str(uuid.uuid4()),
            'value': n,
            'unit': _make_unit_alias_code(),
            'instanceType': 'Quantity',
        },
        'isApproximate': True,
        'instanceType': 'Range',
    }


def enrich_enrollment_number(combined: dict) -> bool:
    """
    G1: Populate plannedEnrollmentNumber using a keyword-guided approach.
    
    Fallback chain (first match wins):
      1. Keyword-guided LLM extraction from protocol PDF
      2. Keyword-guided LLM extraction from SAP PDF (if available)
      3. SAP extension targetSampleSize (already extracted, no LLM cost)
      4. Metadata _temp_planned_enrollment (from LLM synopsis extraction)
    
    Returns True if a value was populated.
    """
    sv = combined.get('study', {}).get('versions', [{}])[0]
    sd = (sv.get('studyDesigns') or [{}])[0]
    pop = sd.get('population', {})
    if not pop or pop.get('plannedEnrollmentNumber'):
        return False
    
    # --- Tier 1: Keyword-guided LLM from protocol PDF ---
    pdf_path = combined.get('_pdf_path')
    if pdf_path:
        try:
            from extraction.enrollment_finder import find_planned_enrollment
            enrollment = find_planned_enrollment(pdf_path)
            if enrollment:
                pop['plannedEnrollmentNumber'] = _build_enrollment_quantity(enrollment)
                logger.info(f"  ✓ plannedEnrollmentNumber={enrollment} (keyword-guided, protocol PDF)")
                return True
        except Exception as e:
            logger.debug(f"  Keyword-guided enrollment from protocol PDF failed: {e}")
    
    # --- Tier 2: Keyword-guided LLM from SAP PDF ---
    output_dir = combined.get('_output_dir')
    if output_dir:
        sap_source = _find_sap_source_file(output_dir)
        if sap_source:
            try:
                from extraction.enrollment_finder import find_planned_enrollment
                enrollment = find_planned_enrollment(sap_source)
                if enrollment:
                    pop['plannedEnrollmentNumber'] = _build_enrollment_quantity(enrollment)
                    logger.info(f"  ✓ plannedEnrollmentNumber={enrollment} (keyword-guided, SAP PDF)")
                    return True
            except Exception as e:
                logger.debug(f"  Keyword-guided enrollment from SAP PDF failed: {e}")
    
    # --- Tier 3: SAP extension targetSampleSize ---
    for ext in sd.get('extensionAttributes', []):
        if ext.get('url', '').endswith('sample-size-calculations'):
            vs = ext.get('valueString', '')
            if not vs:
                continue
            try:
                calcs = json.loads(vs)
                if isinstance(calcs, list):
                    for calc in calcs:
                        target = calc.get('targetSampleSize')
                        if target and isinstance(target, (int, float)) and target > 0:
                            pop['plannedEnrollmentNumber'] = _build_enrollment_quantity(int(target))
                            logger.info(f"  ✓ plannedEnrollmentNumber={int(target)} (SAP extension)")
                            return True
            except (json.JSONDecodeError, TypeError):
                pass
    
    # --- Tier 4: Metadata LLM extraction ---
    enrollment = combined.get('_temp_planned_enrollment')
    if enrollment and isinstance(enrollment, (int, float)) and enrollment > 0:
        pop['plannedEnrollmentNumber'] = _build_enrollment_quantity(int(enrollment))
        logger.info(f"  ✓ plannedEnrollmentNumber={int(enrollment)} (metadata extraction)")
        return True
    
    return False


def _find_sap_source_file(output_dir: str) -> Optional[str]:
    """Find the SAP PDF path from the saved SAP extraction output."""
    sap_file = os.path.join(output_dir, '11_sap_populations.json')
    if not os.path.exists(sap_file):
        return None
    try:
        with open(sap_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        source = data.get('sourceFile')
        if source and os.path.exists(source):
            return source
    except (json.JSONDecodeError, OSError):
        pass
    return None


def clean_orphan_cross_refs(combined: dict) -> int:
    """
    B9: Clean up orphan cross-references that point to non-existent entities.
    
    Handles:
    - studyIdentifiers[].scopeId → must reference a valid Organization
    - exitEpochIds[] in traversal constraints → must reference valid epochs
    
    Returns count of cleaned refs.
    """
    cleaned = 0
    sv = combined.get("study", {}).get("versions", [{}])[0]
    sd = (sv.get("studyDesigns") or [{}])[0]
    
    # Collect valid entity IDs
    valid_org_ids = {
        org.get("id") for org in sv.get("organizations", [])
        if isinstance(org, dict) and org.get("id")
    }
    valid_epoch_ids = {
        e.get("id") for e in sd.get("epochs", [])
        if isinstance(e, dict) and e.get("id")
    }
    
    # Fix scopeId on studyIdentifiers
    for si in sv.get("studyIdentifiers", []):
        scope_id = si.get("scopeId")
        if scope_id and isinstance(scope_id, str) and scope_id not in valid_org_ids:
            si["scopeId"] = None
            cleaned += 1
            logger.debug(f"  Nullified orphan scopeId: {scope_id[:30]}")
    
    # Fix exitEpochIds in extension attributes (traversal constraints)
    def _clean_epoch_refs(obj):
        nonlocal cleaned
        if isinstance(obj, dict):
            if "exitEpochIds" in obj and isinstance(obj["exitEpochIds"], list):
                original = obj["exitEpochIds"]
                obj["exitEpochIds"] = [
                    eid for eid in original
                    if not isinstance(eid, str) or eid in valid_epoch_ids
                ]
                removed = len(original) - len(obj["exitEpochIds"])
                if removed:
                    cleaned += removed
                    logger.debug(f"  Removed {removed} orphan exitEpochIds")
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    _clean_epoch_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    _clean_epoch_refs(item)
    
    _clean_epoch_refs(sd.get("extensionAttributes", []))
    
    return cleaned


def ensure_eos_study_cell(combined: dict) -> dict:
    """P6: Ensure every epoch has at least one StudyCell.

    The USDM v4.0 schema requires studyCells [1..*].  Terminal epochs
    (EOS, ET, follow-up) are often missing a cell because the extractor
    only creates cells for treatment epochs.  This function creates a
    follow-up StudyElement and a StudyCell for any uncovered epoch.
    """
    try:
        sd = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        epochs = sd.get("epochs", [])
        cells = sd.get("studyCells", [])
        arms = sd.get("arms", [])
        elements = sd.get("elements", [])

        if not epochs or not arms:
            return combined

        covered_epoch_ids = {c.get("epochId") for c in cells if c.get("epochId")}
        arm_id = arms[0].get("id", "arm_1")

        added_cells = 0
        for epoch in epochs:
            epoch_id = epoch.get("id")
            if not epoch_id or epoch_id in covered_epoch_ids:
                continue

            # Create a follow-up element for the uncovered epoch
            elem_id = f"elem_followup_{epoch_id}"
            element = {
                "id": elem_id,
                "name": f"{epoch.get('name', 'Follow-up')} Element",
                "label": f"{epoch.get('name', 'Follow-up')} Element",
                "description": f"Study element for the {epoch.get('name', '')} epoch",
                "instanceType": "StudyElement",
            }
            elements.append(element)

            cell = {
                "id": f"cell_{arm_id}_{epoch_id}",
                "armId": arm_id,
                "epochId": epoch_id,
                "elementIds": [elem_id],
                "instanceType": "StudyCell",
            }
            cells.append(cell)
            added_cells += 1

        if added_cells:
            sd["studyCells"] = cells
            sd["elements"] = elements
            logger.info(f"  ✓ Created {added_cells} StudyCell(s) for uncovered epochs (P6)")
    except Exception as e:
        logger.warning(f"  ⚠ EOS/ET StudyCell creation skipped: {e}")

    return combined


def _sanitize_study_site(site: dict) -> dict:
    """Strip non-schema fields from StudySite, moving useful ones to extensions.

    Per USDM v4.0 schema, StudySite only has: id, name, label, description,
    country (Code), extensionAttributes, instanceType.
    """
    _STUDYSITE_SCHEMA_KEYS = {
        "id", "name", "label", "description", "country",
        "extensionAttributes", "instanceType",
    }
    ext_attrs = list(site.get("extensionAttributes", []))

    # Preserve siteNumber as extension (useful for site identification)
    site_number = site.get("siteNumber")
    if site_number:
        ext_attrs.append({
            "id": f"{site.get('id', 'site')}_ext_siteNumber",
            "url": "http://www.example.org/usdm/studySite/siteNumber",
            "valueString": str(site_number),
            "instanceType": "ExtensionAttribute",
        })

    # Preserve status as extension if present
    status = site.get("status")
    if status and status != "Active":
        ext_attrs.append({
            "id": f"{site.get('id', 'site')}_ext_status",
            "url": "http://www.example.org/usdm/studySite/status",
            "valueString": str(status),
            "instanceType": "ExtensionAttribute",
        })

    # Build sanitized site with only schema keys
    sanitized = {k: v for k, v in site.items() if k in _STUDYSITE_SCHEMA_KEYS}
    if ext_attrs:
        sanitized["extensionAttributes"] = ext_attrs
    sanitized.setdefault("instanceType", "StudySite")
    return sanitized


def _backfill_organization(org: dict) -> None:
    """Backfill required Organization fields per USDM v4.0 schema.

    Required: id, name, identifier (1), identifierScheme (1), type (1 Code),
    instanceType.
    """
    org.setdefault("instanceType", "Organization")

    # identifier is required (cardinality 1)
    if not org.get("identifier"):
        org["identifier"] = org.get("id", str(uuid.uuid4()))

    # identifierScheme is required (cardinality 1)
    if not org.get("identifierScheme"):
        org["identifierScheme"] = "USDM"

    # type is required (Code, cardinality 1) — skip if already present and valid
    if not org.get("type") or not isinstance(org.get("type"), dict):
        org["type"] = {
            "id": f"{org.get('id', 'org')}_type",
            "code": "C21541",
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": "Healthcare Facility",
            "instanceType": "Code",
        }


def nest_sites_in_organizations(combined: dict) -> dict:
    """P3: Nest StudySite entities into Organization.managedSites.

    Matches sites to organizations by comparing site name / organization
    name / identifier overlap.  Per USDM v4.0:
    - Organization.managedSites owns the StudySite entities (Value relationship)
    - There is NO studyDesigns[].studySites — sites ONLY live inside orgs
    - Organization requires: id, name, identifier, identifierScheme, type
    - StudySite requires: id, name, country (Code)
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        sd = (sv.get("studyDesigns") or [{}])[0]
        sites = sd.get("studySites", [])
        orgs = sv.get("organizations", [])

        if not sites or not orgs:
            return combined

        # Sanitize all StudySite entities (strip non-schema fields)
        sites = [_sanitize_study_site(s) for s in sites]

        # Build org lookup by normalized name
        org_by_name: Dict[str, dict] = {}
        for org in orgs:
            name = (org.get("name") or "").lower().strip()
            if name:
                org_by_name[name] = org
                org_by_name[_normalize_link_name(name)] = org

        nested = 0
        unmatched_sites: List[dict] = []

        for site in sites:
            site_name = (site.get("name") or "").lower().strip()
            matched_org = None

            # Exact match
            matched_org = org_by_name.get(site_name) or org_by_name.get(_normalize_link_name(site_name))

            # Substring match
            if not matched_org:
                for oname, org in org_by_name.items():
                    if len(oname) > 3 and (oname in site_name or site_name in oname):
                        matched_org = org
                        break

            if matched_org:
                matched_org.setdefault("managedSites", [])
                existing_ids = {s.get("id") for s in matched_org["managedSites"]}
                if site.get("id") not in existing_ids:
                    matched_org["managedSites"].append(site)
                    nested += 1
            else:
                unmatched_sites.append(site)

        # For unmatched sites, create a new Organization for each one.
        # Each clinical site should be its own org with exactly one managedSite.
        if unmatched_sites:
            for site in unmatched_sites:
                site_name = site.get("name", "Unknown Site")
                site_id = site.get("id", "unknown")
                new_org = {
                    "id": f"org_{site_id}",
                    "name": site_name,
                    "identifier": f"org_{site_id}",
                    "identifierScheme": "USDM",
                    "type": {
                        "id": f"org_{site_id}_type",
                        "code": "C21541",
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": "Healthcare Facility",
                        "instanceType": "Code",
                    },
                    "instanceType": "Organization",
                    "managedSites": [site],
                }
                orgs.append(new_org)
                nested += 1
            logger.info(f"  ✓ Created {len(unmatched_sites)} new Organization(s) for unmatched sites")

        # Backfill required Organization fields on ALL orgs (including pre-existing)
        for org in orgs:
            _backfill_organization(org)

        # Remove studySites from studyDesign — not a USDM schema path.
        # Sites now live exclusively inside Organization.managedSites[].
        sd.pop("studySites", None)

        if nested:
            logger.info(f"  ✓ Nested {nested} StudySite(s) into Organization.managedSites (P3)")
    except Exception as e:
        logger.warning(f"  ⚠ Site nesting skipped: {e}")

    return combined


def wire_document_layer(combined: dict) -> dict:
    """P5: Wire root-level document structures into Study.documentedBy.

    Moves root-level studyDefinitionDocument, documentContentReferences,
    inlineCrossReferences, commentAnnotations, and protocolFigures into
    the canonical USDM v4.0 path:
      Study.documentedBy → StudyDefinitionDocument
        .versions[0] → StudyDefinitionDocumentVersion
          .contents[] → NarrativeContent

    Also:
    - Backfills missing SDD metadata (templateName, type, language)
    - Wires contentItemId on NarrativeContent → NarrativeContentItem
    - Builds childIds hierarchy from section numbers
    - Sets required boolean fields (displaySectionTitle, displaySectionNumber)
    """
    try:
        study = combined.get("study", {})
        sv = study.get("versions", [{}])[0]

        # Gather root-level doc structures
        sdd = combined.pop("studyDefinitionDocument", None)
        sdd_versions = combined.pop("studyDefinitionDocumentVersions", None)
        doc_refs = combined.get("documentContentReferences", [])
        inline_xrefs = combined.get("inlineCrossReferences", [])
        annotations = combined.get("commentAnnotations", [])
        figures = combined.get("protocolFigures", [])

        if not sdd and not sv.get("narrativeContentItems"):
            return combined

        # Build or backfill the StudyDefinitionDocument
        if not sdd:
            sdd = {
                "id": str(uuid.uuid4()),
                "name": "Protocol Document",
                "instanceType": "StudyDefinitionDocument",
            }

        # Backfill missing metadata on existing SDD (required fields per schema)
        if not sdd.get("templateName") or sdd.get("templateName") == "?":
            sdd["templateName"] = "ICH M11"
        if not sdd.get("language") or sdd.get("language") == "?" or (
            isinstance(sdd.get("language"), str) and sdd["language"] in ("en", "eng")
        ):
            sdd["language"] = {
                "id": str(uuid.uuid4()),
                "code": "eng",
                "codeSystem": "ISO 639-2",
                "codeSystemVersion": "2024",
                "decode": "English",
                "instanceType": "Code",
            }
        if not sdd.get("type") or sdd.get("type") == "?" or not isinstance(sdd.get("type"), dict):
            sdd["type"] = {
                "id": str(uuid.uuid4()),
                "code": "C70817",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Protocol",
                "instanceType": "Code",
            }
        if not sdd.get("label"):
            sdd["label"] = sdd.get("name", "Protocol Document")
        if not sdd.get("description"):
            sdd["description"] = "Clinical protocol document"

        # Build document version
        doc_version = None
        if sdd_versions and isinstance(sdd_versions, list) and sdd_versions:
            doc_version = sdd_versions[0]
        elif isinstance(sdd.get("versions"), list) and sdd["versions"]:
            doc_version = sdd["versions"][0]
        else:
            doc_version = {
                "id": str(uuid.uuid4()),
                "instanceType": "StudyDefinitionDocumentVersion",
            }

        # Backfill doc version metadata
        if not doc_version.get("version"):
            doc_version["version"] = "1.0"
        if not doc_version.get("status") or not isinstance(doc_version.get("status"), dict):
            status_text = doc_version.get("status", "Final")
            if isinstance(status_text, str) and status_text != "Final":
                status_text = status_text
            else:
                status_text = "Final"
            doc_version["status"] = {
                "id": str(uuid.uuid4()),
                "code": "C132349",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": status_text,
                "instanceType": "Code",
            }

        # Populate contents from narrativeContentItems
        narrative_items = sv.get("narrativeContentItems", [])
        if narrative_items:
            # Build NarrativeContentItem ID lookup by section number and name
            nci_by_section: Dict[str, str] = {}
            nci_by_name: Dict[str, str] = {}
            for item in narrative_items:
                item_id = item.get("id")
                sec_num = item.get("sectionNumber", "")
                item_name = (item.get("name") or "").lower().strip()
                if sec_num and item_id:
                    nci_by_section[sec_num] = item_id
                if item_name and item_id:
                    nci_by_name[item_name] = item_id

            contents = []
            content_by_section: Dict[str, dict] = {}

            for item in narrative_items:
                sec_num = item.get("sectionNumber", "")
                content_id = str(uuid.uuid4())
                content = {
                    "id": content_id,
                    "name": item.get("name", ""),
                    "sectionNumber": sec_num,
                    "sectionTitle": item.get("sectionTitle", item.get("name", "")),
                    "displaySectionTitle": True,
                    "displaySectionNumber": bool(sec_num),
                    "text": item.get("text", ""),
                    "instanceType": "NarrativeContent",
                }

                # Wire contentItemId → NarrativeContentItem
                item_id = item.get("id")
                if item_id:
                    content["contentItemId"] = item_id

                contents.append(content)
                if sec_num:
                    content_by_section[sec_num] = content

            # Build childIds hierarchy from section numbers
            # e.g., §2 gets children [§2.1, §2.2, §2.3]
            for sec_num, content in content_by_section.items():
                child_ids = []
                for other_sec, other_content in content_by_section.items():
                    if other_sec == sec_num:
                        continue
                    # Check if other_sec is a direct child (e.g., "2.1" is child of "2")
                    if other_sec.startswith(sec_num + "."):
                        remainder = other_sec[len(sec_num) + 1:]
                        # Direct child has no more dots (e.g., "1" not "1.2")
                        if "." not in remainder:
                            child_ids.append(other_content["id"])
                if child_ids:
                    content["childIds"] = child_ids

            # Build previousId/nextId ordering chain
            for i, content in enumerate(contents):
                if i > 0:
                    content["previousId"] = contents[i - 1]["id"]
                if i < len(contents) - 1:
                    content["nextId"] = contents[i + 1]["id"]

            doc_version["contents"] = contents

        # Wire into SDD
        sdd["versions"] = [doc_version]

        # Wire into Study.documentedBy (cardinality 0..* → must be a list)
        study["documentedBy"] = [sdd]

        doc_count = len(doc_version.get("contents", []))
        logger.info(f"  ✓ Wired document layer into Study.documentedBy ({doc_count} contents) (P5)")
    except Exception as e:
        logger.warning(f"  ⚠ Document layer wiring skipped: {e}")

    return combined


def nest_cohorts_in_population(combined: dict) -> dict:
    """P4: Nest StudyCohort entities into StudyDesignPopulation.cohorts.

    Moves studyCohorts from the flat design-level collection into the
    population.cohorts[] array per USDM v4.0 schema.  If no cohorts
    exist but the population has characteristics suggesting subgroups,
    this is a no-op (cohort creation requires protocol-specific data).
    """
    try:
        sd = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        cohorts = sd.get("studyCohorts", [])
        population = sd.get("population")

        if not population:
            return combined

        if cohorts:
            # Move into population.cohorts
            existing = population.get("cohorts", [])
            existing_ids = {c.get("id") for c in existing}
            for cohort in cohorts:
                if cohort.get("id") not in existing_ids:
                    # Ensure required fields per schema
                    cohort.setdefault("instanceType", "StudyCohort")
                    cohort.setdefault("includesHealthySubjects", False)
                    cohort.setdefault("label", cohort.get("name", ""))
                    existing.append(cohort)
            population["cohorts"] = existing
            logger.info(f"  ✓ Nested {len(cohorts)} StudyCohort(s) into population.cohorts (P4)")
    except Exception as e:
        logger.warning(f"  ⚠ Cohort nesting skipped: {e}")

    return combined


def promote_footnotes_to_conditions(combined: dict) -> dict:
    """P7: Promote SoA footnote conditions to USDM Condition entities.

    SoA footnotes that describe conditional application of activities
    (e.g. 'At screening and Day 1 only', 'For female participants only')
    are promoted to Condition entities at StudyVersion.conditions[] with
    contextIds and appliesToIds linking them to activities and encounters.
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        sd = (sv.get("studyDesigns") or [{}])[0]

        # Get existing conditions
        existing_conditions = sv.get("conditions", [])
        existing_texts = {c.get("text", "").lower().strip() for c in existing_conditions}

        # Get footnote conditions from execution model extensions
        activities = sd.get("activities", [])
        activity_by_id = {a.get("id"): a for a in activities if a.get("id")}
        activity_by_name = {}
        for a in activities:
            name = (a.get("name") or "").lower().strip()
            if name and a.get("id"):
                activity_by_name[name] = a["id"]

        # Parse footnote conditions from the SoA footnotes extension
        footnotes_ext = None
        for ext in sd.get("extensionAttributes", []):
            if ext.get("url", "").endswith("soaFootnotes"):
                try:
                    footnotes_ext = json.loads(ext.get("valueString", "[]"))
                except (json.JSONDecodeError, TypeError):
                    pass

        if not footnotes_ext:
            return combined

        # Build encounter name → id lookup
        enc_by_name = {}
        for enc in sd.get("encounters", []):
            name = (enc.get("name") or "").lower().strip()
            if name:
                enc_by_name[name] = enc.get("id")

        promoted = 0
        for fn in footnotes_ext:
            fn_text = fn.get("text", "").strip()
            if not fn_text:
                continue

            # Skip if already a condition
            if fn_text.lower().strip() in existing_texts:
                continue

            # Only promote footnotes that look like conditions (contain temporal/gender/procedural qualifiers)
            text_lower = fn_text.lower()
            is_conditional = any(kw in text_lower for kw in (
                "only", "if ", "when ", "unless", "prior to", "before ",
                "after ", "within ", "at screening", "at check-in",
                "for women", "for female", "for male",
                "predose", "fasting", "as needed", "at the discretion",
            ))
            if not is_conditional:
                continue

            fn_id = fn.get("id", str(uuid.uuid4()))
            condition = {
                "id": f"cond_fn_{fn_id}",
                "name": fn_text[:80],
                "label": fn_text[:80],
                "description": fn_text,
                "text": fn_text,
                "instanceType": "Condition",
                "contextIds": [],
                "appliesToIds": [],
            }

            # --- Link to activities mentioned in the footnote ---
            matched_activity_ids = set()
            for act_name, act_id in activity_by_name.items():
                if len(act_name) >= 4 and act_name in text_lower:
                    matched_activity_ids.add(act_id)
            if matched_activity_ids:
                condition["appliesToIds"] = list(matched_activity_ids)

            # --- Link to encounters mentioned in the footnote ---
            matched_encounter_ids = set()
            for enc_name, enc_id in enc_by_name.items():
                if len(enc_name) >= 4 and enc_name in text_lower:
                    matched_encounter_ids.add(enc_id)
            # Also match "day N" patterns in text
            day_matches = re.findall(r'day\s+(\d+)', text_lower)
            for day_num in day_matches:
                for enc_name, enc_id in enc_by_name.items():
                    if f"day {day_num}" in enc_name or f"day{day_num}" in enc_name.replace(" ", ""):
                        matched_encounter_ids.add(enc_id)

            # --- Link to SAI instances that connect matched activities and encounters ---
            context_ids = set()
            if matched_activity_ids or matched_encounter_ids:
                for tl in sd.get("scheduleTimelines", []):
                    for inst in tl.get("instances", []):
                        if inst.get("instanceType") != "ScheduledActivityInstance":
                            continue
                        inst_act_ids = set(inst.get("activityIds", []))
                        inst_enc_id = inst.get("encounterId")
                        # Match if SAI has a matched activity at a matched encounter
                        if inst_act_ids & matched_activity_ids and inst_enc_id in matched_encounter_ids:
                            context_ids.add(inst.get("id"))
                        # Also add if SAI matches just activity (when no encounters matched)
                        elif not matched_encounter_ids and inst_act_ids & matched_activity_ids:
                            context_ids.add(inst.get("id"))
            if context_ids:
                condition["contextIds"] = list(context_ids)
            elif matched_encounter_ids:
                condition["contextIds"] = list(matched_encounter_ids)

            existing_conditions.append(condition)
            existing_texts.add(fn_text.lower().strip())
            promoted += 1

        if promoted:
            sv["conditions"] = existing_conditions
            logger.info(f"  ✓ Promoted {promoted} SoA footnotes to Condition entities (P7)")
    except Exception as e:
        logger.warning(f"  ⚠ Footnote→Condition promotion skipped: {e}")

    return combined


def _deduplicate_ids(combined: dict) -> int:
    """
    CORE-001015: Ensure every entity instance has a unique ``id``.

    Walks the entire USDM tree. For objects that have both ``id`` and
    ``instanceType`` (i.e. proper entity instances), if the same id appears
    more than once, regenerate all but the first occurrence.

    Returns count of IDs regenerated.
    """
    seen: Dict[str, bool] = {}
    regenerated = 0

    def _walk(obj: Any) -> None:
        nonlocal regenerated
        if isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            oid = obj.get("id")
            itype = obj.get("instanceType")
            if oid and itype and isinstance(oid, str):
                if oid in seen:
                    obj["id"] = str(uuid.uuid4())
                    regenerated += 1
                else:
                    seen[oid] = True
            for v in obj.values():
                _walk(v)

    _walk(combined)
    return regenerated


def _fix_activity_child_ordering(study_design: Dict[str, Any]) -> int:
    """
    CORE-001066: For parent activities (with childIds), ``nextId`` must
    point to the first child, and children must be chained together.

    Returns count of links set.
    """
    activities: List[Dict] = study_design.get("activities", [])
    if not activities:
        return 0

    act_by_id: Dict[str, Dict] = {a["id"]: a for a in activities if "id" in a}
    linked = 0

    for act in activities:
        child_ids = act.get("childIds", [])
        if not child_ids:
            continue

        # Parent's nextId → first child
        children = [act_by_id[cid] for cid in child_ids if cid in act_by_id]
        if not children:
            continue

        act["nextId"] = children[0]["id"]
        children[0]["previousId"] = act["id"]
        linked += 1

        # Chain children sequentially
        for i in range(len(children)):
            if i > 0:
                children[i]["previousId"] = children[i - 1]["id"]
                linked += 1
            if i < len(children) - 1:
                children[i]["nextId"] = children[i + 1]["id"]
                linked += 1
            else:
                # Last child: clear nextId (don't chain to next parent)
                children[i].pop("nextId", None)

    return linked


# Endpoint level decode corrections per DDF codelist C188726
_ENDPOINT_DECODE_FIX = {
    "Study Primary Endpoint": "Primary Endpoint",
    "Study Secondary Endpoint": "Secondary Endpoint",
    "Study Exploratory Endpoint": "Exploratory Endpoint",
}


def _fix_endpoint_level_decodes(study_design: Dict[str, Any]) -> int:
    """
    CORE-000940: Fix endpoint level decodes to match DDF codelist C188726.

    The codes (C94496, C139173, C170559) are correct but decodes had a
    "Study " prefix that doesn't match the DDF codelist.
    """
    fixed = 0
    for obj in study_design.get("objectives", []):
        for ep in obj.get("endpoints", []):
            lvl = ep.get("level")
            if isinstance(lvl, dict):
                decode = lvl.get("decode", "")
                if decode in _ENDPOINT_DECODE_FIX:
                    lvl["decode"] = _ENDPOINT_DECODE_FIX[decode]
                    fixed += 1
    return fixed


_DAY_NUM_RE = re.compile(r"(?:Day\s*)?(\d+)", re.IGNORECASE)


def _fix_timing_relative_refs(study_design: Dict[str, Any]) -> int:
    """
    CORE-000423: For non-Fixed-Reference timings, ``relativeFromScheduledInstanceId``
    and ``relativeToScheduledInstanceId`` must point to two *different* SAIs.

    Strategy: match timing names to encounters (exact, substring, then
    day-number range), resolve to SAIs via encounter→SAI map, and set
    relativeToScheduledInstanceId to the encounter's first SAI.
    """
    encounters: List[Dict] = study_design.get("encounters", [])
    enc_by_name: Dict[str, str] = {}
    enc_day_ranges: List[tuple] = []  # (enc_id, lo, hi)
    for enc in encounters:
        ename = (enc.get("name") or "").strip()
        eid = enc.get("id", "")
        if ename and eid:
            enc_by_name[ename.lower()] = eid
            # Parse day ranges like "Day 4-7", "Day -42 to -9"
            nums = [int(n) for n in re.findall(r"-?\d+", ename)]
            if nums:
                enc_day_ranges.append((eid, min(nums), max(nums)))

    fixed = 0
    for tl in study_design.get("scheduleTimelines", []):
        instances = tl.get("instances", [])

        # Build encounter_id → first SAI id
        enc_to_sai: Dict[str, str] = {}
        for inst in instances:
            eid = inst.get("encounterId", "")
            if eid and eid not in enc_to_sai:
                enc_to_sai[eid] = inst.get("id", "")

        for timing in tl.get("timings", []):
            ttype = timing.get("type", {})
            if isinstance(ttype, dict) and ttype.get("code") == "C201358":
                continue  # Fixed Reference — skip

            rel_from = timing.get("relativeFromScheduledInstanceId", "")
            rel_to = timing.get("relativeToScheduledInstanceId", "")

            if not (rel_from and rel_to and rel_from == rel_to):
                continue

            # Extract encounter name from "Timing for X"
            tname = timing.get("name", timing.get("label", ""))
            m = re.match(r"Timing for (.+)", tname, re.IGNORECASE)
            enc_part = (m.group(1).strip() if m else tname).lower()

            # Try exact match
            matched_enc = enc_by_name.get(enc_part)

            # Try substring match
            if not matched_enc:
                for ename_lower, eid in enc_by_name.items():
                    if enc_part in ename_lower or ename_lower in enc_part:
                        matched_enc = eid
                        break

            # Try day-number range match
            if not matched_enc:
                day_m = _DAY_NUM_RE.search(enc_part)
                if day_m:
                    target_day = int(day_m.group(1))
                    for eid, lo, hi in enc_day_ranges:
                        if lo <= target_day <= hi:
                            matched_enc = eid
                            break

            if matched_enc:
                target_sai = enc_to_sai.get(matched_enc)
                if target_sai and target_sai != rel_from:
                    timing["relativeToScheduledInstanceId"] = target_sai
                    fixed += 1

    return fixed


def _normalize_country_decodes(combined: dict) -> int:
    """
    CORE-000427: Ensure code/decode is one-to-one within a codeSystem.

    Fix: normalize all ``decode`` values for ISO 3166-1 country codes
    (e.g. code="USA" must always decode to "United States", not "USA").
    """
    _COUNTRY_DECODE = {
        "USA": "United States", "GBR": "United Kingdom",
        "DEU": "Germany", "FRA": "France", "ESP": "Spain",
        "CHE": "Switzerland", "JPN": "Japan", "CAN": "Canada",
        "AUS": "Australia", "ITA": "Italy", "NLD": "Netherlands",
        "BEL": "Belgium", "AUT": "Austria", "SWE": "Sweden",
        "DNK": "Denmark", "NOR": "Norway", "FIN": "Finland",
        "POL": "Poland", "CZE": "Czech Republic", "HUN": "Hungary",
        "IRL": "Ireland", "PRT": "Portugal", "GRC": "Greece",
        "BRA": "Brazil", "MEX": "Mexico", "ARG": "Argentina",
        "CHL": "Chile", "COL": "Colombia", "KOR": "Korea, Republic of",
        "CHN": "China", "IND": "India", "ISR": "Israel",
        "ZAF": "South Africa", "NZL": "New Zealand", "SGP": "Singapore",
        "TWN": "Taiwan", "THA": "Thailand", "MYS": "Malaysia",
        "RUS": "Russian Federation", "TUR": "Turkey", "UKR": "Ukraine",
    }
    fixed = 0

    def _walk(obj: Any) -> None:
        nonlocal fixed
        if isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            # Check if this is a Code with an ISO country codeSystem
            cs = obj.get("codeSystem", "")
            if "3166" in str(cs) or "country" in str(cs).lower():
                code = obj.get("code", "")
                expected = _COUNTRY_DECODE.get(code)
                if expected and obj.get("decode") != expected:
                    obj["decode"] = expected
                    fixed += 1
            for v in obj.values():
                _walk(v)

    _walk(combined)
    return fixed


def _fix_window_durations(study_design: Dict[str, Any]) -> int:
    """
    CORE-000825: ``windowLower`` must be a non-negative ISO 8601 duration.

    Fix: strip leading '-' from window values (e.g. "-P7D" → "P7D").
    """
    fixed = 0
    for tl in study_design.get("scheduleTimelines", []):
        for timing in tl.get("timings", []):
            for field in ("windowLower", "windowUpper"):
                val = timing.get(field, "")
                if isinstance(val, str) and val.startswith("-"):
                    timing[field] = val.lstrip("-")
                    fixed += 1
    return fixed


def _normalize_code_system_versions(combined: dict) -> int:
    """
    CORE-000808: Only one ``codeSystemVersion`` per ``codeSystem``.

    Fix: normalize all CDISC codes to "2024-09-27" and ISO 3166-1 to "2024".
    """
    _VERSION_MAP = {
        "http://www.cdisc.org": "2024-09-27",
        "http://www.nlm.nih.gov/mesh": "2024",
    }
    fixed = 0

    def _walk(obj: Any) -> None:
        nonlocal fixed
        if isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            cs = obj.get("codeSystem", "")
            expected_ver = _VERSION_MAP.get(cs)
            if expected_ver and obj.get("codeSystemVersion") and obj["codeSystemVersion"] != expected_ver:
                obj["codeSystemVersion"] = expected_ver
                fixed += 1
            for v in obj.values():
                _walk(v)

    _walk(combined)
    return fixed


def _remove_non_usdm_properties(combined: dict) -> int:
    """
    CORE-000937: Remove properties not defined in the USDM v4.0 schema.

    Known non-USDM properties:
    - MedicalDevice.deviceType (no such attribute in schema)
    - NarrativeContent.text (narrative text belongs in NarrativeContentItem)
    """
    fixed = 0

    # MedicalDevice.deviceType → remove
    ver = combined.get("study", {}).get("versions", [{}])[0]
    for md in ver.get("medicalDevices", []):
        if "deviceType" in md:
            md.pop("deviceType")
            fixed += 1

    # NarrativeContent.text → move to extensionAttribute if present
    sdd_list = combined.get("study", {}).get("documentedBy", [])
    for sdd in sdd_list:
        for sdd_ver in sdd.get("versions", []):
            for nc in sdd_ver.get("contents", []):
                if "text" in nc:
                    text_val = nc.pop("text")
                    # Preserve content as an extensionAttribute
                    if text_val and isinstance(text_val, str):
                        ext_attrs = nc.setdefault("extensionAttributes", [])
                        ext_attrs.append({
                            "id": str(uuid.uuid4()),
                            "url": "http://www.example.org/usdmExtensions/narrativeText",
                            "valueString": text_val,
                            "instanceType": "ExtensionAttribute",
                        })
                    fixed += 1

    return fixed


def _ensure_leaf_activity_procedures(study_design: Dict[str, Any]) -> int:
    """
    CORE-001076: Every leaf activity (no childIds) must reference at least
    one procedure, biomedical concept, or child.

    Fix: auto-create a Procedure from the activity name for leaf activities
    that have empty ``definedProcedures``.
    """
    activities: List[Dict] = study_design.get("activities", [])
    if not activities:
        return 0

    fixed = 0
    for act in activities:
        child_ids = act.get("childIds") or []
        procedures = act.get("definedProcedures") or []
        bc_ids = act.get("biomedicalConceptIds") or []
        bc_cats = act.get("bcCategoryIds") or act.get("bcCategories") or []
        bc_surr = act.get("bcSurrogateIds") or act.get("bcSurrogates") or []

        if child_ids or procedures or bc_ids or bc_cats or bc_surr:
            continue

        # Leaf activity with no references — create a procedure from name
        act_name = act.get("name", act.get("label", "Unknown"))
        proc = {
            "id": str(uuid.uuid4()),
            "name": act_name,
            "label": act_name,
            "description": act_name,
            "procedureType": {
                "id": str(uuid.uuid4()),
                "code": "C25218",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Procedure",
                "instanceType": "Code",
            },
            "instanceType": "Procedure",
        }
        act["definedProcedures"] = [proc]
        fixed += 1

    return fixed


def _fix_timing_values(study_design: Dict[str, Any]) -> int:
    """
    CORE-000820: Timing ``value`` must be a non-negative ISO 8601 duration.

    Fix: strip embedded minus signs (e.g., ``P-14D`` → ``P14D``).
    """
    fixed = 0
    for tl in study_design.get("scheduleTimelines", []):
        for timing in tl.get("timings", []):
            val = timing.get("value", "")
            if isinstance(val, str) and val.startswith("P") and "-" in val[1:]:
                timing["value"] = val[0] + val[1:].replace("-", "")
                fixed += 1
    return fixed


def _fix_amendment_reason_codesystem(combined: dict) -> int:
    """
    CORE-000930: Amendment reason ``code.codeSystem`` must be
    ``http://www.cdisc.org`` (codelist C207415).

    Fix: remap NCI EVS codeSystem to CDISC for known amendment reason codes.
    """
    _AMENDMENT_REASON_CODES = {
        "C132347",  # Protocol Amendment
        "C17649",   # Other
        "C156631", "C156632", "C156633", "C156634", "C156635",
    }
    fixed = 0
    ver = combined.get("study", {}).get("versions", [{}])[0]
    for amend in ver.get("amendments", []):
        for reason_field in ("primaryReason", "secondaryReasons"):
            reasons = amend.get(reason_field)
            if reasons is None:
                continue
            if isinstance(reasons, dict):
                reasons = [reasons]
            for reason in reasons:
                code_obj = reason.get("code")
                if isinstance(code_obj, dict) and code_obj.get("code") in _AMENDMENT_REASON_CODES:
                    if code_obj.get("codeSystem") != "http://www.cdisc.org":
                        code_obj["codeSystem"] = "http://www.cdisc.org"
                        code_obj["codeSystemVersion"] = "2024-09-27"
                        fixed += 1
    return fixed


def _fix_empty_amendment_changes(combined: dict) -> int:
    """
    CORE-000938: ``StudyAmendment.changes`` must have at least one entry.

    Fix: create a placeholder ``StudyChange`` if changes list is empty.
    """
    fixed = 0
    ver = combined.get("study", {}).get("versions", [{}])[0]
    for amend in ver.get("amendments", []):
        changes = amend.get("changes", [])
        if isinstance(changes, list) and len(changes) == 0:
            amend["changes"] = [{
                "id": str(uuid.uuid4()),
                "summary": amend.get("summary", "Amendment change"),
                "instanceType": "StudyChange",
            }]
            fixed += 1
    return fixed


def _fix_unit_codes(combined: dict) -> int:
    """
    CORE-001060 / CORE-001061: Unit codes must use the correct codeSystem.

    Fix: ensure unit Code objects for known units (Year, %) have
    ``codeSystem`` set to ``http://www.cdisc.org``.
    """
    _UNIT_CODE_MAP = {
        "Year": ("C29848", "Year"),
        "YEARS": ("C29848", "Year"),
        "year": ("C29848", "Year"),
        "%": ("C25613", "Percentage"),
        "Percentage": ("C25613", "Percentage"),
        "kg/m2": ("C49671", "Kilogram Per Square Meter"),
        "mg": ("C28253", "Milligram"),
    }
    fixed = 0

    def _walk(obj: Any) -> None:
        nonlocal fixed
        if isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            # Look for unit Code objects
            if obj.get("instanceType") == "Code":
                decode = obj.get("decode", "")
                if decode in _UNIT_CODE_MAP and not obj.get("codeSystem"):
                    code_val, decode_val = _UNIT_CODE_MAP[decode]
                    obj["code"] = code_val
                    obj["decode"] = decode_val
                    obj["codeSystem"] = "http://www.cdisc.org"
                    obj["codeSystemVersion"] = "2024-09-27"
                    fixed += 1
            for v in obj.values():
                _walk(v)

    _walk(combined)
    return fixed


def _fix_amendment_other_reason(combined: dict) -> int:
    """
    CORE-000413: ``otherReason`` should only be populated when
    ``code.code`` is C17649 ('Other'). Remove it otherwise.
    """
    fixed = 0
    ver = combined.get("study", {}).get("versions", [{}])[0]
    for amend in ver.get("amendments", []):
        for reason_field in ("primaryReason", "secondaryReasons"):
            reasons = amend.get(reason_field)
            if reasons is None:
                continue
            items = reasons if isinstance(reasons, list) else [reasons]
            for reason in items:
                if not isinstance(reason, dict):
                    continue
                code_obj = reason.get("code", {})
                code_val = code_obj.get("code", "") if isinstance(code_obj, dict) else ""
                if code_val != "C17649" and reason.get("otherReason"):
                    reason.pop("otherReason", None)
                    fixed += 1
    return fixed


def run_structural_compliance(combined: dict) -> dict:
    """
    Apply structural CORE compliance fixes after reconciliation.

    These fixes require cross-entity context (all epochs, encounters,
    objectives, endpoints) and must run before UUID conversion.
    """
    try:
        sd = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]

        ordering = build_ordering_chains(sd)
        if ordering:
            logger.info(f"  ✓ Built ordering chains: {ordering} links")

        ep_links = fix_primary_endpoint_linkage(sd)
        if ep_links:
            logger.info(f"  ✓ Fixed primary endpoint linkage: {ep_links} links")

        timing_refs = fix_timing_references(sd)
        if timing_refs:
            logger.info(f"  ✓ Fixed timing references: {timing_refs} refs")

        # G1: Keyword-guided enrollment number enrichment
        enrich_enrollment_number(combined)

        # B9: Clean orphan cross-references
        orphan_count = clean_orphan_cross_refs(combined)
        if orphan_count:
            logger.info(f"  ✓ Cleaned {orphan_count} orphan cross-references")

        # ── CORE compliance batch fixes ──────────────────────────────
        dedup = _deduplicate_ids(combined)
        if dedup:
            logger.info(f"  ✓ CORE-001015: Deduplicated {dedup} entity IDs")

        act_order = _fix_activity_child_ordering(sd)
        if act_order:
            logger.info(f"  ✓ CORE-001066: Fixed {act_order} activity child ordering links")

        ep_decode = _fix_endpoint_level_decodes(sd)
        if ep_decode:
            logger.info(f"  ✓ CORE-000940: Fixed {ep_decode} endpoint level decodes")

        timing_rel = _fix_timing_relative_refs(sd)
        if timing_rel:
            logger.info(f"  ✓ CORE-000423: Fixed {timing_rel} timing relativeFrom/To refs")

        country = _normalize_country_decodes(combined)
        if country:
            logger.info(f"  ✓ CORE-000427: Normalized {country} country decodes")

        window = _fix_window_durations(sd)
        if window:
            logger.info(f"  ✓ CORE-000825: Fixed {window} window durations")

        csv = _normalize_code_system_versions(combined)
        if csv:
            logger.info(f"  ✓ CORE-000808: Normalized {csv} codeSystemVersions")

        amend = _fix_amendment_other_reason(combined)
        if amend:
            logger.info(f"  ✓ CORE-000413: Removed {amend} invalid otherReason values")

        non_usdm = _remove_non_usdm_properties(combined)
        if non_usdm:
            logger.info(f"  ✓ CORE-000937: Removed {non_usdm} non-USDM properties")

        leaf_procs = _ensure_leaf_activity_procedures(sd)
        if leaf_procs:
            logger.info(f"  ✓ CORE-001076: Created procedures for {leaf_procs} leaf activities")

        timing_vals = _fix_timing_values(sd)
        if timing_vals:
            logger.info(f"  ✓ CORE-000820: Fixed {timing_vals} timing value durations")

        amend_cs = _fix_amendment_reason_codesystem(combined)
        if amend_cs:
            logger.info(f"  ✓ CORE-000930: Fixed {amend_cs} amendment reason codeSystems")

        amend_changes = _fix_empty_amendment_changes(combined)
        if amend_changes:
            logger.info(f"  ✓ CORE-000938: Populated {amend_changes} empty amendment changes")

        unit_codes = _fix_unit_codes(combined)
        if unit_codes:
            logger.info(f"  ✓ CORE-001060: Fixed {unit_codes} unit codes")

    except (KeyError, IndexError, TypeError) as e:
        logger.debug(f"Structural compliance skipped: {e}")

    return combined
