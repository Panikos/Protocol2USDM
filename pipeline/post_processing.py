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
                
                # Populate epochId on schedule instances
                enc_to_epoch = {enc.get('id'): enc.get('epochId') for enc in reconciled_encounters}
                epochs = study_design.get('epochs', [])
                fallback_epoch_id = epochs[0].get('id') if epochs else None
                
                for timeline in study_design.get('scheduleTimelines', []):
                    for inst in timeline.get('instances', []):
                        if not inst.get('epochId'):
                            enc_id = inst.get('encounterId')
                            if enc_id and enc_id in enc_to_epoch:
                                inst['epochId'] = enc_to_epoch[enc_id]
                            elif fallback_epoch_id:
                                inst['epochId'] = fallback_epoch_id
        
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
        
        # Sanitize procedure codes
        for proc in procedures:
            code = proc.get('code')
            if code and isinstance(code, dict) and not code.get('code'):
                proc_type = proc.get('procedureType', 'Clinical Procedure')
                type_codes = {
                    'Diagnostic Procedure': ('C25391', 'Diagnostic Procedure'),
                    'Therapeutic Procedure': ('C49236', 'Therapeutic Procedure'),
                    'Surgical Procedure': ('C17173', 'Surgical Procedure'),
                    'Biospecimen Collection': ('C70793', 'Biospecimen Collection'),
                    'Imaging Technique': ('C17369', 'Imaging Technique'),
                    'Monitoring': ('C25548', 'Monitoring'),
                    'Assessment': ('C25218', 'Assessment'),
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
