"""
Post-processing steps for the combined USDM output.

Handles entity reconciliation, activity source marking, procedure linking,
SoA footnotes, epoch filtering, and activity reference updates.
"""

from typing import Dict, Optional, Any, List
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)


def run_reconciliation(combined: dict, expansion_results: dict, soa_data: dict) -> dict:
    """Run entity reconciliation (epochs, encounters, activities)."""
    from core.reconciliation import (
        reconcile_epochs_from_pipeline,
        reconcile_encounters_from_pipeline,
        reconcile_activities_from_pipeline,
    )
    from core.epoch_reconciler import enrich_epoch_names_with_clinical_type
    
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
    except Exception as e:
        logger.warning(f"  ⚠ Epoch filtering failed: {e}")
    
    return combined


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
            
            source = 'soa' if has_ticks else 'procedure_enrichment'
            activity['extensionAttributes'].append({
                'id': f"ext_source_{act_id[:8] if act_id else 'unknown'}",
                'url': 'http://example.org/usdm/activitySource',
                'valueString': source,
                'instanceType': 'ExtensionAttribute'
            })
            
            if has_ticks:
                soa_count += 1
            else:
                procedure_count += 1
        
        logger.info(f"  ✓ Marked activities: {soa_count} SoA, {procedure_count} procedure enrichment")
        
        # Update activityGroups.childIds to only include SoA activities
        for group in study_design.get('activityGroups', []):
            child_ids = group.get('childIds', [])
            group['childIds'] = [cid for cid in child_ids if cid in activity_ids_with_ticks]
    
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
        
        # Build name lookup
        proc_by_name = {proc.get('name', '').lower().strip(): proc for proc in procedures if proc.get('name')}
        
        # Link procedures to activities
        linked_count = 0
        for activity in activities:
            act_name = activity.get('name', '').lower().strip()
            
            matched_proc = proc_by_name.get(act_name)
            if not matched_proc:
                for proc_name, proc in proc_by_name.items():
                    if proc_name in act_name or act_name in proc_name:
                        matched_proc = proc
                        break
            
            if matched_proc:
                if 'definedProcedures' not in activity:
                    activity['definedProcedures'] = []
                existing_ids = {p.get('id') for p in activity['definedProcedures']}
                if matched_proc.get('id') not in existing_ids:
                    activity['definedProcedures'].append(matched_proc)
                    linked_count += 1
        
        if linked_count > 0:
            logger.info(f"  ✓ Linked {linked_count} procedures to activities")
    
    except Exception as e:
        logger.warning(f"  ⚠ Procedure-Activity linking skipped: {e}")


def link_administrations_to_products(combined: dict) -> dict:
    """H8: Link Administration.administrableProductId by name matching.
    
    Matches administrations to products by comparing names (exact then substring).
    """
    try:
        sv = combined.get("study", {}).get("versions", [{}])[0]
        products = sv.get("administrableProducts", [])
        administrations = combined.get("administrations", [])
        
        if not products or not administrations:
            return combined
        
        # Build product name lookup (lowercase → id)
        prod_by_name = {}
        for p in products:
            name = (p.get("name") or "").lower().strip()
            if name:
                prod_by_name[name] = p.get("id")
        
        linked = 0
        for admin in administrations:
            if admin.get("administrableProductId"):
                continue  # already linked
            admin_name = (admin.get("name") or "").lower().strip()
            if not admin_name:
                continue
            
            # Exact match
            prod_id = prod_by_name.get(admin_name)
            if not prod_id:
                # Substring match (admin name contains product name or vice versa)
                for pname, pid in prod_by_name.items():
                    if pname in admin_name or admin_name in pname:
                        prod_id = pid
                        break
            
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
            
            # Store the strength as an extension on the product for reference
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
    """Add authoritative SoA footnotes from header_structure.json."""
    try:
        header_path = os.path.join(output_dir, "4_header_structure.json")
        if not os.path.exists(header_path):
            return
        
        with open(header_path, 'r', encoding='utf-8') as f:
            header_data = json.load(f)
        
        soa_footnotes = header_data.get('footnotes', [])
        if soa_footnotes:
            if 'extensionAttributes' not in study_design:
                study_design['extensionAttributes'] = []
            
            # Remove existing SoA footnotes
            study_design['extensionAttributes'] = [
                ext for ext in study_design['extensionAttributes']
                if not ext.get('url', '').endswith('soaFootnotes')
            ]
            
            study_design['extensionAttributes'].append({
                'id': f"ext_soa_footnotes_{study_design.get('id', 'sd')[:8]}",
                'url': 'https://protocol2usdm.io/extensions/x-soaFootnotes',
                'valueString': json.dumps(soa_footnotes),
                'instanceType': 'ExtensionAttribute'
            })
            logger.info(f"  ✓ Added {len(soa_footnotes)} authoritative SoA footnotes")
    
    except Exception as e:
        logger.warning(f"  ⚠ SoA footnotes addition skipped: {e}")


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
