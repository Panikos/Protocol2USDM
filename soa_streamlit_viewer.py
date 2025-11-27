import streamlit as st
import json
import os
import glob
import pandas as pd  # for reading the M11 mapping workbook
import re
import html
from pathlib import Path
from datetime import datetime

# --- Data Access Functions --------------------------------------------------

def get_timeline(soa_content):
    """Safely retrieves the 'timeline' object from the SoA content."""
    if isinstance(soa_content, dict):
        # Standard USDM v4 location
        study = soa_content.get('study', {})
        if study and isinstance(study.get('versions'), list) and study['versions']:
            return study['versions'][0].get('timeline')
        # Fallback for flattened/reconciled format
        return soa_content.get('timeline')
    return None

def get_activity_timepoints(timeline):
    """Robustly extracts activity-timepoint links from a timeline object."""
    if not timeline:
        return {}  # Explicitly return an empty dict
    
    activity_timepoints = {}
    # Check both keys, as raw output might use 'activityTimepoints' and processed uses 'scheduledActivityInstances'
    for key in ['scheduledActivityInstances', 'activityTimepoints']:
        # Gracefully handle if the key is missing from the timeline
        for link in timeline.get(key, []):
            if isinstance(link, dict) and link.get('activityId') and link.get('plannedTimepointId'):
                activity_timepoints.setdefault(link['activityId'], []).append(link['plannedTimepointId'])

    return activity_timepoints

st.set_page_config(page_title="Protocol2USDM Viewer", layout="wide", page_icon="📊")
st.title('📊 Protocol2USDM v6.0 Viewer')
st.markdown("**Full Protocol Extraction** | USDM v4.0 Format")
# Placeholder for dynamic file display; will be updated after run selection.
file_placeholder = st.empty()

# --- Utility Functions ---

def compute_usdm_metrics(soa, gold_standard=None):
    """Compute comprehensive USDM-specific metrics including visit accuracy, linkage, and field population."""
    if not isinstance(soa, dict):
        return {}
    timeline = get_timeline(soa)
    if not timeline:
        return {}
    
    metrics = {}
    
    # Entity counts
    metrics['visits'] = len(timeline.get('plannedTimepoints', []))
    metrics['activities'] = len(timeline.get('activities', []))
    metrics['activityTimepoints'] = len(timeline.get('activityTimepoints', []))
    metrics['encounters'] = len(timeline.get('encounters', []))
    metrics['epochs'] = len(timeline.get('epochs', []))
    
    # Visit accuracy (if gold standard provided)
    if gold_standard:
        gold_timeline = get_timeline(gold_standard)
        if gold_timeline:
            gold_visits = len(gold_timeline.get('plannedTimepoints', []))
            metrics['visit_accuracy'] = (min(metrics['visits'], gold_visits) / gold_visits * 100) if gold_visits > 0 else 0
            gold_acts = len(gold_timeline.get('activities', []))
            metrics['activity_accuracy'] = (min(metrics['activities'], gold_acts) / gold_acts * 100) if gold_acts > 0 else 0
    
    # Linkage accuracy
    activities = {a['id']: a for a in timeline.get('activities', [])}
    planned_timepoints = {pt['id']: pt for pt in timeline.get('plannedTimepoints', [])}
    encounters = {e['id']: e for e in timeline.get('encounters', [])}
    
    correct_linkages = 0
    total_linkages = 0
    
    # Check PlannedTimepoint → Encounter linkages
    for pt in timeline.get('plannedTimepoints', []):
        enc_id = pt.get('encounterId')
        if enc_id:
            total_linkages += 1
            if enc_id in encounters:
                correct_linkages += 1
    
    # Check ActivityTimepoint linkages
    for at in timeline.get('activityTimepoints', []):
        act_id = at.get('activityId')
        pt_id = at.get('plannedTimepointId') or at.get('timepointId')
        if act_id:
            total_linkages += 1
            if act_id in activities:
                correct_linkages += 1
        if pt_id:
            total_linkages += 1
            if pt_id in planned_timepoints:
                correct_linkages += 1
    
    metrics['linkage_accuracy'] = (correct_linkages / total_linkages * 100) if total_linkages > 0 else 100
    
    # Field population rate
    required_fields = {
        'PlannedTimepoint': ['id', 'name', 'instanceType', 'encounterId', 'value', 'unit', 'relativeToId', 'relativeToType'],
        'Activity': ['id', 'name', 'instanceType'],
        'Encounter': ['id', 'name', 'type', 'instanceType'],
    }
    
    total_required = 0
    total_present = 0
    
    for pt in timeline.get('plannedTimepoints', []):
        for field in required_fields['PlannedTimepoint']:
            total_required += 1
            if field in pt and pt[field] is not None and pt[field] != '':
                total_present += 1
    
    for act in timeline.get('activities', []):
        for field in required_fields['Activity']:
            total_required += 1
            if field in act and act[field] is not None and act[field] != '':
                total_present += 1
    
    metrics['field_population_rate'] = (total_present / total_required * 100) if total_required > 0 else 100
    
    return metrics

def compute_completeness_metrics(soa):
    """Return a list of dicts summarising attribute coverage for key USDM entities."""
    if not isinstance(soa, dict):
        return []
    timeline = get_timeline(soa)
    if not timeline:
        return []

    metrics_config = {
        'activities': ['description', 'activityGroupId'],
        'plannedTimepoints': ['description'],
        'activityGroups': ['description'],
        'encounters': ['description', 'timing'],
        'epochs': ['description']
    }

    rows = []
    for entity_key, attrs in metrics_config.items():
        items = timeline.get(entity_key, [])
        total = len(items)
        if total == 0:
            continue
        row = {'Entity': entity_key, 'Count': total}
        for attr in attrs:
            filled = sum(1 for it in items if it.get(attr))
            row[f"{attr} filled (%)"] = f"{filled}/{total} ({filled/total*100:.0f}%)"
        rows.append(row)

    # StudyVersion level checks
    study_versions = soa.get('study', {}).get('versions', [])
    if study_versions:
        sv = study_versions[0]
        sv_checks = {
            'rationale': bool(sv.get('rationale')),
            'titles': bool(sv.get('titles')),
            'studyIdentifiers': bool(sv.get('studyIdentifiers'))
        }
        filled = sum(1 for v in sv_checks.values() if v)
        rows.append({'Entity': 'StudyVersion', 'Count': 1, 'Key fields filled (%)': f"{filled}/3 ({filled/3*100:.0f}%)"})
    return rows

def load_file(path):
    """Loads a file, trying JSON first, then falling back to text."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f), 'json'
    except (json.JSONDecodeError, UnicodeDecodeError):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read(), 'text'
    except Exception:
        return None, None

@st.cache_data
def get_file_inventory(base_path):
    """
    Builds an inventory of available output files for a given run.
    Returns a dictionary with categorized files for display.
    """
    if not os.path.isdir(base_path):
        st.error(f"The specified path is not a directory: {base_path}")
        return None

    inventory = {
        'final_soa': None,
        'full_usdm': None,  # Combined full protocol output
        'expansion': {},     # Expansion phase outputs
        'primary_outputs': {},
        'post_processed': {},
        'intermediate_data': {},
        'configs': {},
        'images': [],
    }
    
    # File map supporting both old (main.py) and new (main_v2.py) pipeline outputs
    file_map = {
        # New pipeline outputs (main_v2.py)
        '9_final_soa.json': ('final_soa', 'Final SoA'),
        '4_header_structure.json': ('intermediate_data', 'SoA Header Structure'),
        '5_text_extraction.json': ('primary_outputs', 'Text Extraction'),
        '6_validation_result.json': ('intermediate_data', 'Validation Result'),
        # Legacy pipeline outputs (main.py)
        '9_reconciled_soa.json': ('final_soa', 'Final Reconciled SoA'),
        '5_raw_text_soa.json': ('primary_outputs', 'Raw Text Extraction'),
        '6_raw_vision_soa.json': ('primary_outputs', 'Raw Vision Extraction'),
        '7_postprocessed_text_soa.json': ('post_processed', 'Text Post-processed'),
        '8_postprocessed_vision_soa.json': ('post_processed', 'Vision Post-processed'),
        '4_soa_header_structure.json': ('intermediate_data', 'SoA Header Structure'),
        '2_soa_pages.json': ('intermediate_data', 'Identified SoA Pages'),
        '1_llm_prompt.txt': ('configs', 'Generated LLM Prompt'),
        '1_llm_prompt_full.txt': ('configs', 'Full LLM Prompt'),
        # Step-by-step test outputs
        'step3_header_structure.json': ('intermediate_data', 'Header Structure (Step 3)'),
        'step4_text_extraction.json': ('primary_outputs', 'Text Extraction (Step 4)'),
        'step6_final_soa.json': ('final_soa', 'Final SoA (Step 6)'),
    }
    
    # USDM Expansion files (v6.0)
    expansion_map = {
        'full_usdm.json': ('full_usdm', 'Full Protocol USDM'),
        '2_study_metadata.json': ('metadata', 'Study Metadata'),
        '3_eligibility_criteria.json': ('eligibility', 'Eligibility Criteria'),
        '4_objectives_endpoints.json': ('objectives', 'Objectives & Endpoints'),
        '5_study_design.json': ('studydesign', 'Study Design'),
        '6_interventions.json': ('interventions', 'Interventions'),
        '7_narrative_structure.json': ('narrative', 'Narrative Structure'),
        '8_advanced_entities.json': ('advanced', 'Advanced Entities'),
    }
    
    # Load expansion files
    for f_name, (key, display_name) in expansion_map.items():
        f_path = os.path.join(base_path, f_name)
        if os.path.exists(f_path):
            content, _ = load_file(f_path)
            if content:
                if key == 'full_usdm':
                    inventory['full_usdm'] = {'display_name': display_name, 'content': content, 'path': f_path}
                else:
                    inventory['expansion'][key] = {'display_name': display_name, 'content': content, 'path': f_path}

    for f_name, (category, display_name) in file_map.items():
        f_path = os.path.join(base_path, f_name)
        if os.path.exists(f_path):
            content, _ = load_file(f_path)
            if content:
                if category == 'final_soa':
                    inventory[category] = {'display_name': display_name, 'content': content, 'path': f_path}
                else:
                    inventory[category][display_name] = content

    # Handle soa_entity_mapping.json from root
    mapping_path = "soa_entity_mapping.json"
    if os.path.exists(mapping_path):
        content, _ = load_file(mapping_path)
        if content:
            inventory['configs']['SoA Entity Mapping'] = content

    # Check multiple possible image directories
    for img_dir_name in ["3_soa_images", "step2_images"]:
        image_dir = os.path.join(base_path, img_dir_name)
        if os.path.isdir(image_dir):
            inventory['images'] = sorted(glob.glob(os.path.join(image_dir, "*.png")))
            break
    
    # --- Attach provenance if stored in separate file ---
    if inventory['final_soa']:
        # Try multiple possible provenance file patterns
        possible_prov_files = [
            '9_final_soa_provenance.json',      # New pipeline
            '9_reconciled_soa_provenance.json', # Legacy pipeline
            'step6_provenance.json',            # Step-by-step test
        ]
        
        for prov_file in possible_prov_files:
            prov_path = os.path.join(base_path, prov_file)
            if os.path.exists(prov_path):
                prov_content, _ = load_file(prov_path)
                if isinstance(inventory['final_soa']['content'], dict) and prov_content and isinstance(prov_content, dict):
                    # Convert provenance format if needed (new format has 'entities' and 'cells')
                    if 'entities' in prov_content:
                        # New format - merge entities into p2uProvenance format
                        merged_prov = dict(prov_content.get('entities', {}))
                        
                        # Convert cells from flat "actId|ptId" -> nested {actId: {ptId: source}}
                        cells = prov_content.get('cells', {})
                        nested_cells = {}
                        for key, source in cells.items():
                            if '|' in key:
                                act_id, pt_id = key.split('|', 1)
                                if act_id not in nested_cells:
                                    nested_cells[act_id] = {}
                                if pt_id:  # Only add if pt_id is not empty
                                    nested_cells[act_id][pt_id] = source
                        merged_prov['activityTimepoints'] = nested_cells
                        inventory['final_soa']['content']['p2uProvenance'] = merged_prov
                    elif 'p2uProvenance' not in inventory['final_soa']['content']:
                        # Legacy format - use directly
                        inventory['final_soa']['content']['p2uProvenance'] = prov_content
                break
    
    inventory['file_map'] = file_map
    return inventory

def extract_soa_metadata(soa):
    if not isinstance(soa, dict):
        return {}
    study = soa.get('study', {})
    usdm_version = soa.get('usdmVersion', 'N/A')
    
    # Handle both pre and post-processed formats
    versions = study.get('versions') or study.get('studyVersions')
    timeline = versions[0].get('timeline') if versions else None

    if timeline:
        num_timepoints = len(timeline.get('plannedTimepoints', []))
        num_activities = len(timeline.get('activities', []))
        num_groups = len(timeline.get('activityGroups', []))
    else:
        num_timepoints, num_activities, num_groups = 0, 0, 0
        
    return {
        'usdm_version': usdm_version,
        'num_timepoints': num_timepoints,
        'num_activities': num_activities,
        'num_groups': num_groups
    }

# Note: get_timeline() is defined earlier in this file (lines 13-22)
# Removed duplicate definition that was here

def _get_timepoint_sort_key(tp_label):
    """Creates a sort key for a timepoint label for chronological sorting."""
    label = tp_label.lower()
    # Priority 0: Screening
    if 'screen' in label:
        return (0, 0)
    
    # Priority 1: Visit, Day, Week, Period (numeric)
    match = re.search(r'(visit|day|week|period)\s*(-?\d+)', label)
    if match:
        return (1, int(match.group(2)))

    # Priority 2: Time-based (numeric)
    match = re.search(r'(-?\d+\.?\d*)\s*hour', label)
    if match:
        return (2, float(match.group(1)))

    # Priority 3: Specific keywords
    if 'end of study' in label or 'eos' in label:
        return (3, 0)
    if 'et' in label or 'early term' in label:
        return (3, 1)
    if 'unscheduled' in label or 'uns' in label:
        return (3, 2)
    if 'rt' in label: # Retreatment
        return (3, 3)

    # Default priority
    return (4, label)

# Note: Removed incomplete get_timepoints() function - functionality is in render_flexible_soa()

# --- SoA Renderer ---

from collections import defaultdict

def get_schedule_components(data):
    """
    Flexibly extracts schedule-related components from the JSON data.
    It checks for data in both the standard `studyDesigns` path and a custom `timeline` path.
    """
    schedule_data = {}
    
    # Try the standard USDM 4.0 path first
    try:
        study_design = data['study']['versions'][0]['studyDesigns'][0]
        # st.info("Found data in the standard `studyDesigns` location.")
        schedule_data = study_design
    except (KeyError, IndexError):
        # Fallback to the custom/intermediary `timeline` path
        try:
            timeline = data['study']['versions'][0]['timeline']
            # st.info("Could not find `studyDesigns`. Found data in the non-standard `timeline` location instead.")
            schedule_data = timeline
        except (KeyError, IndexError):
            # If neither path works, return empty
            return None
            
    # Use .get() for graceful extraction of each component
    return {
        'activities': schedule_data.get('activities', []),
        'activityGroups': schedule_data.get('activityGroups', []),
        'epochs': schedule_data.get('epochs', []),
        'encounters': schedule_data.get('encounters', []),
        'scheduleTimelines': schedule_data.get('scheduleTimelines', []),
        'plannedTimepoints': schedule_data.get('plannedTimepoints', []),
        'activityTimepoints': schedule_data.get('activityTimepoints', [])
    }


def render_flexible_soa(data, table_id: str = "main"):
    """
    Parses a potentially incomplete or non-standard USDM file and renders the best possible SoA table.
    """
    components = get_schedule_components(data)
    if not components:
        st.error(
            "Could not find schedule data. The file must contain either a `studyDesigns` array "
            "or a `timeline` object within the first study version."
        )
        return

    if not components['activities']:
        st.warning("No activities found in the data. Cannot render a schedule.")
        return

    # --- Create maps for easy lookups ---
    activity_map = {act.get('id'): act for act in components['activities'] if act.get('id')}
    epoch_map = {e.get('id'): e.get('name', 'Unnamed Epoch') for e in components['epochs'] if e.get('id')}
    encounter_map = {e.get('id'): e.get('name', 'Unnamed Encounter') for e in components['encounters'] if e.get('id')}

    # --- Flexibly determine Activity -> Encounter links ---
    activity_encounter_links = set()
    epoch_encounter_pairs = defaultdict(set)

    # Strategy 1: Standard `scheduleTimelines`
    if components['scheduleTimelines'] and components['scheduleTimelines'][0].get('instances'):
        # st.success("Using standard `scheduleTimelines` to link activities to the timeline.")
        for instance in components['scheduleTimelines'][0].get('instances', []):
            if instance.get('instanceType') == 'ScheduledActivityInstance':
                encounter_id = instance.get('encounterId')
                epoch_id = instance.get('epochId')
                if encounter_id and epoch_id:
                    epoch_encounter_pairs[epoch_id].add(encounter_id)
                    for act_id in instance.get('activityIds', []):
                        activity_encounter_links.add((act_id, encounter_id))
    
    # Strategy 2: Fallback to `activityTimepoints` (common in intermediary files)
    elif components['activityTimepoints'] and components['plannedTimepoints']:
        # st.success("Using non-standard `activityTimepoints` to link activities to the timeline.")
        pt_map = {pt.get('id'): pt for pt in components['plannedTimepoints'] if pt.get('id')}
        for at in components['activityTimepoints']:
            pt = pt_map.get(at.get('plannedTimepointId'))
            if pt and pt.get('encounterId') and at.get('activityId'):
                encounter_id = pt['encounterId']
                # Find the epoch for this encounter
                epoch_id = next((enc.get('epochId') for enc in components['encounters'] if enc.get('id') == encounter_id), None)
                if epoch_id:
                    epoch_encounter_pairs[epoch_id].add(encounter_id)
                    activity_encounter_links.add((at['activityId'], encounter_id))
    else:
        st.error("Could not determine activity schedule. The file is missing `scheduleTimelines` and `activityTimepoints` data.")
        return

    # --- Prepare DataFrame Structure ---

    # 1. Build Row Index (Activities) with Hierarchy
    row_index_data = []
    ordered_activities = []

    # Strategy 1: Standard `childIds` hierarchy
    all_child_ids = {cid for act in components['activities'] if 'childIds' in act for cid in act['childIds']}
    parent_activities = [act for act in components['activities'] if act.get('id') not in all_child_ids and act.get('childIds')]

    if parent_activities:
        # st.success("Determined activity hierarchy using standard parent/child links (`childIds`).")
        for parent_act in parent_activities:
            parent_name = parent_act.get('label', parent_act.get('name', 'Unnamed Category'))
            for child_id in parent_act.get('childIds', []):
                if child_id in activity_map:
                    child_activity = activity_map[child_id]
                    child_name = child_activity.get('label', child_activity.get('name', 'Unnamed Activity'))
                    row_index_data.append((parent_name, child_name))
                    ordered_activities.append(child_activity)
    
    # Strategy 2: Fallback `activityGroupId` hierarchy
    elif components['activityGroups']:
        # st.success("Determined activity hierarchy using non-standard `activityGroupId` links.")
        group_map = {g.get('id'): g.get('name', 'Unnamed Group') for g in components['activityGroups']}
        activities_by_group = defaultdict(list)
        for act in components['activities']:
            group_id = act.get('activityGroupId')
            if group_id:
                activities_by_group[group_id].append(act)
        
        for group_id, group_name in group_map.items():
            for activity in activities_by_group.get(group_id, []):
                activity_name = activity.get('label', activity.get('name', 'Unnamed Activity'))
                row_index_data.append((group_name, activity_name))
                ordered_activities.append(activity)

    # Strategy 3: No hierarchy found
    else:
        st.warning("No activity hierarchy found. Displaying a flat list of activities.")
        parent_name = "Activities"
        for activity in components['activities']:
            activity_name = activity.get('label', activity.get('name', 'Unnamed Activity'))
            row_index_data.append((parent_name, activity_name))
            ordered_activities.append(activity)

    if not row_index_data:
        st.error("Could not build activity rows for the table.")
        st.info("The 'activities' list in the JSON is likely empty or malformed. Here is the raw data found:")
        st.json(components.get('activities', []))
        return
        
    row_multi_index = pd.MultiIndex.from_tuples(row_index_data, names=['Category / System', 'Activity / Procedure'])

    # 2. Build Column Index (Epoch ▸ Visit Window ▸ Planned Timepoint)
    col_index_data = []
    ordered_pt_for_cols = []  # Keep the original objects to speed look-ups

    # Helper maps
    epoch_map = {e.get('id'): e.get('name', 'Unnamed Epoch') for e in components['epochs'] if e.get('id')}
    enc_map_full = {e.get('id'): e for e in components['encounters'] if e.get('id')}

    # Maintain original file order by iterating through plannedTimepoints as they appear
    for pt in components['plannedTimepoints']:
        pt_id = pt.get('id')
        enc_id = pt.get('encounterId')
        if not (pt_id and enc_id):
            continue

        # epoch → encounter → pt
        enc = enc_map_full.get(enc_id, {})
        epoch_id = enc.get('epochId')
        epoch_name = epoch_map.get(epoch_id, 'Unnamed Epoch')
        # Prefer visit-window label from timing; fallback to encounter name
        encounter_name = enc.get('timing', {}).get('windowLabel') or enc.get('name', 'Unnamed Window')
        pt_name = pt.get('name', 'Unnamed TP')

        col_index_data.append((epoch_name, encounter_name, pt_name))
        ordered_pt_for_cols.append({'id': pt_id, 'encounterId': enc_id})

    # Fallback: if we have plannedTimepoints but none with encounterId, still build columns
    if not col_index_data:
        if components['plannedTimepoints']:
            st.warning("No encounterId found on plannedTimepoints; building columns from timepoints only.")
            for pt in components['plannedTimepoints']:
                pt_id = pt.get('id')
                if not pt_id:
                    continue
                pt_name = pt.get('name', 'Unnamed TP')
                # Use generic epoch/visit labels when encounter linkage is missing
                col_index_data.append(("Timeline", "", pt_name))
                ordered_pt_for_cols.append({'id': pt_id, 'encounterId': None})
        else:
            st.error("Could not build timeline columns  no planned timepoints available.")
            return

    col_multi_index = pd.MultiIndex.from_tuples(col_index_data, names=['Epoch', 'Visit Window', 'Planned TP'])

    # --- Create and Populate DataFrame ---
    df = pd.DataFrame("", index=row_multi_index, columns=col_multi_index)

    # Pre-compute activity ⇢ plannedTimepoint links
    activity_pt_links = set()

    if components['scheduleTimelines'] and components['scheduleTimelines'][0].get('instances'):
        # Derive from ScheduledActivityInstance → mark all pts within that encounter
        enc_to_pt_ids = defaultdict(list)
        for pt in components['plannedTimepoints']:
            if pt.get('encounterId'):
                enc_to_pt_ids[pt['encounterId']].append(pt['id'])
        for inst in components['scheduleTimelines'][0].get('instances', []):
            if inst.get('instanceType') != 'ScheduledActivityInstance':
                continue
            enc_id = inst.get('encounterId')
            for act_id in inst.get('activityIds', []):
                for pid in enc_to_pt_ids.get(enc_id, []):
                    activity_pt_links.add((act_id, pid))
    elif components['activityTimepoints']:
        for at in components['activityTimepoints']:
            if at.get('activityId') and at.get('plannedTimepointId'):
                activity_pt_links.add((at['activityId'], at['plannedTimepointId']))

    # populate DataFrame
    for i, activity in enumerate(ordered_activities):
        row_label = row_index_data[i]
        act_id = activity.get('id')
        for col_tuple, pt_info in zip(col_index_data, ordered_pt_for_cols):
            pt_id = pt_info['id']
            if (act_id, pt_id) in activity_pt_links:
                df.loc[row_label, col_tuple] = 'X'

    # Display the full dataframe (no filtering of all-X rows)
    df_display = df
    row_index_data_display = row_index_data
    ordered_activities_display = ordered_activities

    # Add provenance styling if available
    provenance = data.get('p2uProvenance', {})
    if provenance:
        at_prov_map = provenance.get('activityTimepoints', {}) if isinstance(provenance, dict) else {}
        tick_counts = {'text': 0, 'confirmed': 0, 'needs_review': 0}
        rows_with_review = set()
        if isinstance(at_prov_map, dict):
            for idx, activity in zip(row_index_data_display, ordered_activities_display):
                aid = activity.get('id')
                if not aid:
                    continue
                cell_map = at_prov_map.get(aid, {})
                if not isinstance(cell_map, dict):
                    continue
                has_row_review = False
                for src in cell_map.values():
                    if src == 'text':
                        tick_counts['text'] += 1
                    elif src == 'both':
                        tick_counts['confirmed'] += 1
                    elif src in ('vision', 'needs_review'):
                        # Vision-only and needs_review both count as needing review
                        tick_counts['needs_review'] += 1
                        has_row_review = True
                if has_row_review:
                    rows_with_review.add(idx)

        total_ticks = tick_counts['text'] + tick_counts['confirmed'] + tick_counts['needs_review']
        has_validation = tick_counts['confirmed'] > 0 or tick_counts['needs_review'] > 0

        if total_ticks:
            summary_text = (
                f"**Tick provenance:** {total_ticks} total - "
                f"{tick_counts['confirmed']} ✓ confirmed, "
                f"{tick_counts['text']} unvalidated, "
                f"{tick_counts['needs_review']} ⚠️ need review."
            )
            st.markdown(summary_text)

        if rows_with_review:
            st.warning(f"⚠️ **{tick_counts['needs_review']} ticks need human review** (possible hallucinations or vision-only detections)")
            only_review_rows = st.checkbox(
                "Show only rows needing review",
                value=False,
                key=f"only_review_{table_id}",
            )
            if only_review_rows:
                keep_index = [idx for idx in df_display.index if idx in rows_with_review]
                df_display = df_display.loc[keep_index]
                keep_index_set = set(df_display.index)
                filtered = [
                    (idx, act)
                    for idx, act in zip(row_index_data_display, ordered_activities_display)
                    if idx in keep_index_set
                ]
                row_index_data_display = [idx for idx, _ in filtered]
                ordered_activities_display = [act for _, act in filtered]

        if not has_validation:
            st.info("Vision validation has not been run. All ticks shown are from text extraction only.")

        # Display provenance legend
        st.markdown("""
        <h3 style="font-weight: 600;">Provenance Legend</h3>
        <div style="display: flex; align-items: center; gap: 1.5rem; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #60a5fa;"></div><span>Text (unvalidated)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #4ade80;"></div><span>✓ Confirmed</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #fb923c;"></div><span>⚠️ Needs Review</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Apply provenance styling
        def apply_provenance_style(row, col):
            """Apply provenance color to cells with 'X', preferring cell-level provenance when available."""
            try:
                # Safely get cell value - handle multi-index
                cell_value = df_display.loc[row, col]
                # If it's a Series (multi-index edge case), get the first value
                if hasattr(cell_value, 'item'):
                    cell_value = cell_value.item()
                elif hasattr(cell_value, 'iloc'):
                    cell_value = cell_value.iloc[0]
                
                if cell_value != 'X':
                    return ''
            except (KeyError, IndexError, ValueError):
                return ''
            
            # Get activity ID from row
            act_id = None
            for i, row_tuple in enumerate(row_index_data_display):
                if row_tuple == row:
                    act_id = ordered_activities_display[i].get('id')
                    break
            
            # Get timepoint ID from column  
            pt_id = None
            for col_tuple, pt_info in zip(col_index_data, ordered_pt_for_cols):
                if col_tuple == col:
                    pt_id = pt_info['id']
                    break
            
            if not act_id or not pt_id:
                return ''

            # 1) Prefer cell-level provenance if available
            at_prov_map = provenance.get('activityTimepoints', {}) if isinstance(provenance, dict) else {}
            if at_prov_map and isinstance(at_prov_map, dict):
                cell_src = at_prov_map.get(act_id, {}).get(pt_id)
                if cell_src in ('needs_review', 'vision'):
                    return 'background-color: #fb923c'  # orange - needs review (includes vision-only)
                elif cell_src == 'both':
                    return 'background-color: #4ade80'  # green - confirmed
                elif cell_src == 'text':
                    return 'background-color: #60a5fa'  # blue - text (unvalidated)
            
            # 2) Fallback to entity-level provenance
            act_prov = get_provenance_sources(provenance, 'activities', act_id)
            pt_prov = get_provenance_sources(provenance, 'plannedTimepoints', pt_id)
            
            from_text = act_prov['text'] or pt_prov['text']
            from_vision = act_prov['vision'] or pt_prov['vision']
            
            if from_text and from_vision:
                return 'background-color: #4ade80'  # green - both
            elif from_text:
                return 'background-color: #60a5fa'  # blue - text
            elif from_vision:
                return 'background-color: #facc15'  # yellow - vision
            return ''
        
        # Apply styling directly - bypass Styler to avoid multi-index issues
        # Build a style map with integer positions instead of labels
        style_map = {}
        for i, row_idx in enumerate(df_display.index):
            for j, col_idx in enumerate(df_display.columns):
                style = apply_provenance_style(row_idx, col_idx)
                if style:
                    style_map[(i, j)] = style
        
        # Convert DataFrame to HTML manually with styles
        html_parts = ['<style>']
        html_parts.append('.soa-table { border-collapse: collapse; width: 100%; }')
        html_parts.append('.soa-table th, .soa-table td { border: 1px solid #ddd; padding: 8px; text-align: center; }')
        html_parts.append('.soa-table th { background-color: #f2f2f2; font-weight: bold; }')
        html_parts.append('</style>')
        html_parts.append('<table class="soa-table">')
        
        # Header - with proper column structure for activity groups
        has_groups = isinstance(df_display.index, pd.MultiIndex) and df_display.index.nlevels >= 2
        html_parts.append('<thead>')
        if isinstance(df.columns, pd.MultiIndex):
            # Check if Visit Window (level 1) and Planned TP (level 2) are duplicates
            # If so, skip one level to avoid redundant rows
            level_values = [df.columns.get_level_values(i).tolist() for i in range(df.columns.nlevels)]
            skip_levels = set()
            if df.columns.nlevels >= 3:
                # Check if level 1 and level 2 are mostly identical
                if level_values[1] == level_values[2]:
                    skip_levels.add(2)  # Skip the duplicate level
            
            active_levels = [i for i in range(df.columns.nlevels) if i not in skip_levels]
            num_header_rows = len(active_levels)
            
            # Multi-level column headers with colspan merging
            for level_idx, level in enumerate(active_levels):
                html_parts.append('<tr>')
                if level_idx == 0:
                    # Two header columns: Activity Group + Activity Name
                    if has_groups:
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #d1d5db; min-width: 120px;">Category</th>')
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #d1d5db; min-width: 200px;">Activity</th>')
                    else:
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #d1d5db;">Activity</th>')
                
                # Build merged cells with colspan for this level
                values = level_values[level]
                i = 0
                while i < len(values):
                    val = values[i]
                    colspan = 1
                    # Count consecutive identical values
                    while i + colspan < len(values) and values[i + colspan] == val:
                        colspan += 1
                    
                    # Different styling for epoch row (level 0)
                    if level == 0:
                        style = 'background-color: #e5e7eb; font-weight: bold;'
                    else:
                        style = ''
                    
                    if colspan > 1:
                        html_parts.append(f'<th colspan="{colspan}" style="{style}">{html.escape(str(val))}</th>')
                    else:
                        html_parts.append(f'<th style="{style}">{html.escape(str(val))}</th>')
                    i += colspan
                html_parts.append('</tr>')
        else:
            html_parts.append('<tr>')
            if has_groups:
                html_parts.append('<th style="background-color: #d1d5db;">Category</th>')
                html_parts.append('<th style="background-color: #d1d5db;">Activity</th>')
            else:
                html_parts.append('<th style="background-color: #d1d5db;">Activity</th>')
            for col in df.columns:
                html_parts.append(f'<th>{col}</th>')
            html_parts.append('</tr>')
        html_parts.append('</thead>')
        
        # Body - with proper activity group visual structure
        html_parts.append('<tbody>')
        
        # Pre-calculate group spans for proper rowspan rendering
        group_spans = {}  # group_name -> (start_row, count)
        prev_group = None
        for i, row_idx in enumerate(df_display.index):
            if isinstance(row_idx, tuple) and len(row_idx) >= 2:
                group_name = row_idx[0]
                if group_name != prev_group:
                    group_spans[group_name] = {'start': i, 'count': 1}
                    prev_group = group_name
                else:
                    group_spans[group_name]['count'] += 1
        
        rendered_groups = set()
        for i, (row_idx, row) in enumerate(df_display.iterrows()):
            html_parts.append('<tr>')
            
            if isinstance(row_idx, tuple) and len(row_idx) >= 2:
                group_name, activity_name = row_idx[0], row_idx[1]
                
                # Render group header cell with rowspan (only for first row of group)
                if group_name not in rendered_groups:
                    rendered_groups.add(group_name)
                    span = group_spans.get(group_name, {}).get('count', 1)
                    html_parts.append(
                        f'<th rowspan="{span}" style="background-color: #e5e7eb; '
                        f'font-weight: 600; text-align: left; vertical-align: top; '
                        f'border-right: 2px solid #9ca3af; padding: 8px 12px;">{group_name}</th>'
                    )
                
                # Activity name cell
                html_parts.append(f'<th style="text-align: left; font-weight: normal; padding-left: 8px;">{activity_name}</th>')
            else:
                # Flat structure - no grouping
                html_parts.append(f'<th style="text-align: left;">{row_idx}</th>')
            
            # Data cells with provenance styling
            for j, (col_idx, value) in enumerate(row.items()):
                style_attr = f' style="{style_map.get((i, j), "")}"' if (i, j) in style_map else ''
                html_parts.append(f'<td{style_attr}>{value}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody></table>')
        
        table_html = ''.join(html_parts)
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        # No provenance available, just show the dataframe (with any applied row filtering)
        st.dataframe(df_display)

def get_provenance_sources(provenance, item_type, item_id):
    """
    Determines the provenance (text, vision, or both) for a given item ID.
    Updated to work with actual provenance data structure.
    """
    sources = {'text': False, 'vision': False}
    if not provenance or item_type not in provenance or not item_id:
        return sources

    # Get provenance data for this entity type
    provenance_data = provenance.get(item_type, {})
    if not provenance_data:
        return sources

    # Look up the entity ID directly in provenance, but be tolerant of
    # hyphen vs underscore differences between extraction/post-processing
    entity_source = provenance_data.get(item_id)
    if entity_source is None and isinstance(item_id, str):
        # Try hyphen-normalized variants
        alt_ids = set()
        if '-' in item_id:
            alt_ids.add(item_id.replace('-', '_'))
        if '_' in item_id:
            alt_ids.add(item_id.replace('_', '-'))
        for alt in alt_ids:
            if alt in provenance_data:
                entity_source = provenance_data[alt]
                break
    
    if entity_source == 'text':
        sources['text'] = True
    elif entity_source == 'vision':
        sources['vision'] = True
    elif entity_source == 'both':
        sources['text'] = True
        sources['vision'] = True
        
    return sources

# Note: Removed unused style_provenance() and render_soa_table() functions
# The viewer now uses render_flexible_soa() which handles all rendering with provenance styling

# --- Main App Layout ---

OUTPUT_DIR = "output"

# --- Sidebar ---
st.sidebar.title("Protocol Run Selection")

try:
    # Get a list of all subdirectories in the output folder
    runs = sorted(
        [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))],
        reverse=True # Show most recent first
    )
except FileNotFoundError:
    runs = []

if not runs:
    st.error(f"No run directories found in the '{OUTPUT_DIR}' folder. Please run the pipeline first.")
    st.stop()

# Add a placeholder to the list of runs, and default to it.
runs.insert(0, "-- Select a Run --")
selected_run = st.sidebar.selectbox(
    "Select a pipeline run:",
    runs,
    index=0,
    help="Each folder in the 'output' directory represents a single execution of the pipeline."
)

if selected_run == "-- Select a Run --":
    st.info("Please select a pipeline run from the sidebar to begin.")
    st.stop()


run_path = os.path.join(OUTPUT_DIR, selected_run)
# Update header subtitle displaying the source PDF/protocol directory
file_placeholder.markdown(f"**SoA from:** `{selected_run}`")
inventory = get_file_inventory(run_path)

# --- USDM Metrics Dashboard in Sidebar ---
if inventory['final_soa']:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 USDM Quality Metrics")

    # Compute metrics solely from the reconciled SoA (no external gold standard).
    metrics = compute_usdm_metrics(inventory['final_soa']['content'])

    if metrics:
        # Entity counts
        st.sidebar.markdown("**Entity Counts:**")
        st.sidebar.metric("Visits (PlannedTimepoints)", metrics['visits'])
        st.sidebar.metric("Activities", metrics['activities'])
        st.sidebar.metric("Activity-Visit Mappings", metrics['activityTimepoints'])

        # Quality metrics
        st.sidebar.markdown("**Quality Scores:**")

        # Linkage accuracy
        linkage_color = '#4caf50' if metrics['linkage_accuracy'] >= 95 else '#ff9800' if metrics['linkage_accuracy'] >= 85 else '#f44336'
        st.sidebar.markdown(f"<div style='background:{linkage_color};color:white;padding:6px;border-radius:4px;text-align:center;margin-bottom:8px;'>Linkage Accuracy: {metrics['linkage_accuracy']:.1f}%</div>", unsafe_allow_html=True)

        # Field population
        field_color = '#4caf50' if metrics['field_population_rate'] >= 70 else '#ff9800' if metrics['field_population_rate'] >= 50 else '#f44336'
        st.sidebar.markdown(f"<div style='background:{field_color};color:white;padding:6px;border-radius:4px;text-align:center;margin-bottom:8px;'>Field Population: {metrics['field_population_rate']:.1f}%</div>", unsafe_allow_html=True)






# --- Main Display: Render the final SoA --- 
st.header("Schedule of Activities (SoA)")
if not inventory['final_soa']:
    st.warning("The final SoA (`9_final_soa.json`) was not found for this run.")
else:
    # Use the flexible renderer which handles missing entities gracefully
    render_flexible_soa(inventory['final_soa']['content'], table_id="final_soa")
    with st.expander("Show Full JSON Output"):
        st.json(inventory['final_soa']['content'])

# --- USDM Expansion Data (v6.0) ---
if inventory.get('expansion') or inventory.get('full_usdm'):
    st.markdown("---")
    st.header("📋 Protocol Expansion Data (v6.0)")
    
    if inventory.get('full_usdm'):
        st.success("✅ Full USDM protocol available (`full_usdm.json`)")
    
    # Create tabs for each expansion section
    expansion_tabs = []
    expansion_keys = []
    
    tab_config = [
        ('metadata', '📄 Metadata'),
        ('eligibility', '✅ Eligibility'),
        ('objectives', '🎯 Objectives'),
        ('studydesign', '🔬 Design'),
        ('interventions', '💊 Interventions'),
        ('narrative', '📖 Narrative'),
        ('advanced', '🌍 Advanced'),
    ]
    
    available_tabs = [(key, label) for key, label in tab_config if key in inventory.get('expansion', {})]
    
    if available_tabs:
        tab_labels = [label for _, label in available_tabs]
        tabs = st.tabs(tab_labels)
        
        for i, (key, label) in enumerate(available_tabs):
            with tabs[i]:
                exp_data = inventory['expansion'][key]
                content = exp_data['content']
                
                if key == 'metadata':
                    st.subheader("Study Metadata")
                    if content.get('success') and content.get('metadata'):
                        md = content['metadata']
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Study Titles:**")
                            for t in md.get('studyTitles', []):
                                st.write(f"- {t.get('text', 'N/A')}")
                            st.markdown("**Study Phase:**")
                            phase = md.get('studyPhase', {})
                            st.write(phase.get('phase', 'N/A'))
                        with col2:
                            st.markdown("**Identifiers:**")
                            for ident in md.get('studyIdentifiers', []):
                                st.write(f"- {ident.get('studyIdentifier', 'N/A')}")
                            st.markdown("**Indication:**")
                            for ind in md.get('studyIndications', []):
                                st.write(f"- {ind.get('name', 'N/A')}")
                
                elif key == 'eligibility':
                    st.subheader("Eligibility Criteria")
                    if content.get('success') and content.get('eligibility'):
                        elig = content['eligibility']
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Inclusion Criteria ({elig.get('summary', {}).get('inclusionCount', 0)}):**")
                            for c in elig.get('eligibilityCriteria', []):
                                if c.get('category') == 'Inclusion':
                                    st.write(f"- {c.get('text', 'N/A')[:100]}...")
                        with col2:
                            st.markdown(f"**Exclusion Criteria ({elig.get('summary', {}).get('exclusionCount', 0)}):**")
                            for c in elig.get('eligibilityCriteria', []):
                                if c.get('category') == 'Exclusion':
                                    st.write(f"- {c.get('text', 'N/A')[:100]}...")
                
                elif key == 'objectives':
                    st.subheader("Objectives & Endpoints")
                    if content.get('success') and content.get('objectivesEndpoints'):
                        obj = content['objectivesEndpoints']
                        summary = obj.get('summary', {})
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Primary", summary.get('primaryObjectivesCount', 0))
                        col2.metric("Secondary", summary.get('secondaryObjectivesCount', 0))
                        col3.metric("Endpoints", len(obj.get('endpoints', [])))
                        
                        st.markdown("**Objectives:**")
                        for o in obj.get('objectives', []):
                            level = o.get('level', 'Unknown')
                            st.write(f"- [{level}] {o.get('text', 'N/A')[:100]}...")
                
                elif key == 'studydesign':
                    st.subheader("Study Design Structure")
                    if content.get('success') and content.get('studyDesign'):
                        sd = content['studyDesign']
                        design = sd.get('studyDesign', {})
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Arms", len(sd.get('studyArms', [])))
                        col2.metric("Cohorts", len(sd.get('studyCohorts', [])))
                        col3.metric("Blinding", design.get('blindingSchema', {}).get('code', 'N/A'))
                        
                        st.markdown("**Study Arms:**")
                        for arm in sd.get('studyArms', []):
                            st.write(f"- {arm.get('name', 'N/A')}: {arm.get('description', 'N/A')[:80]}...")
                
                elif key == 'interventions':
                    st.subheader("Interventions & Products")
                    if content.get('success') and content.get('interventions'):
                        iv = content['interventions']
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Interventions", len(iv.get('interventions', [])))
                        col2.metric("Products", len(iv.get('products', [])))
                        col3.metric("Administrations", len(iv.get('administrations', [])))
                        
                        st.markdown("**Interventions:**")
                        for inter in iv.get('interventions', []):
                            st.write(f"- {inter.get('name', 'N/A')}")
                
                elif key == 'narrative':
                    st.subheader("Narrative Structure")
                    if content.get('success') and content.get('narrative'):
                        narr = content['narrative']
                        col1, col2 = st.columns(2)
                        col1.metric("Sections", len(narr.get('narrativeContents', [])))
                        col2.metric("Abbreviations", len(narr.get('abbreviations', [])))
                        
                        st.markdown("**Sections:**")
                        for sec in narr.get('narrativeContents', [])[:10]:
                            st.write(f"- {sec.get('sectionNumber', '')} {sec.get('sectionTitle', sec.get('name', 'N/A'))}")
                        
                        st.markdown("**Abbreviations:**")
                        abbr_text = ", ".join([f"{a.get('abbreviatedText', '')}={a.get('expandedText', '')}" 
                                              for a in narr.get('abbreviations', [])[:10]])
                        st.write(abbr_text)
                
                elif key == 'advanced':
                    st.subheader("Advanced Entities")
                    if content.get('success') and content.get('advanced'):
                        adv = content['advanced']
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Amendments", len(adv.get('studyAmendments', [])))
                        col2.metric("Countries", len(adv.get('countries', [])))
                        col3.metric("Sites", len(adv.get('studySites', [])))
                        
                        st.markdown("**Amendments:**")
                        for amend in adv.get('studyAmendments', []):
                            st.write(f"- Amendment {amend.get('number', 'N/A')}: {amend.get('summary', 'N/A')[:60]}...")
                
                with st.expander("Show Raw JSON"):
                    st.json(content)
    else:
        st.info("No expansion data found. Run `main_v2.py --full-protocol` to extract.")

# --- Debugging / Intermediate Files Section ---
st.markdown("--- ")
st.header("Intermediate Outputs & Debugging")

# Create tabs for intermediate files (simplified - removed legacy Post-Processed tab)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Text Extraction", 
    "Data Files", 
    "Config Files", 
    "SoA Images",
    "Quality Metrics",
    "Validation & Conformance",
])

with tab1:
    st.subheader("Text Extraction Output")
    if not inventory['primary_outputs']:
        st.info("No text extraction output found. Run the pipeline to generate.")
    else:
        for i, (key, content) in enumerate(inventory['primary_outputs'].items()):
            st.markdown(f"**{key}**")
            render_flexible_soa(content, table_id=f"primary_{i}")
            with st.expander("Show Raw JSON"):
                st.json(content)

with tab2:
    st.subheader("Intermediate Data Files")
    if not inventory['intermediate_data']:
        st.info("No intermediate data files found.")
    else:
        for key, content in inventory['intermediate_data'].items():
            with st.expander(key):
                st.json(content if isinstance(content, dict) else str(content))

with tab3:
    st.subheader("Configuration Files")
    if not inventory['configs']:
        st.info("No configuration files found.")
    else:
        for key, content in inventory['configs'].items():
            with st.expander(key):
                if isinstance(content, dict):
                    st.json(content)
                else:
                    st.text(content)

with tab4:
    st.subheader("Extracted SoA Images")
    if not inventory['images']:
        st.info("No images found.")
    else:
        cols = st.columns(2)
        for i, img_path in enumerate(inventory['images']):
            if not os.path.exists(img_path):
                continue
            try:
                with cols[i % 2]:
                    st.image(img_path, caption=os.path.basename(img_path), use_container_width=True)
            except Exception as e:
                st.warning(f"Could not load image {img_path}: {e}")

with tab5:
    st.subheader("Quality Metrics")
    if not inventory['final_soa']:
        st.info("Run a pipeline to generate a final SoA first.")
    else:
        # Entity counts and quality metrics
        metrics = compute_usdm_metrics(inventory['final_soa']['content'])
        
        if metrics:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Visits", metrics['visits'])
                st.metric("Activities", metrics['activities'])
                st.metric("Encounters", metrics['encounters'])
            
            with col2:
                st.metric("Epochs", metrics['epochs'])
                st.metric("Tick Marks", metrics['activityTimepoints'])
            
            with col3:
                st.metric("Linkage Accuracy", f"{metrics['linkage_accuracy']:.1f}%")
                st.metric("Field Population", f"{metrics['field_population_rate']:.1f}%")
            
            # Quality interpretation
            st.markdown("---")
            if metrics['linkage_accuracy'] >= 95:
                st.success(f"✅ Excellent linkage ({metrics['linkage_accuracy']:.1f}%)")
            elif metrics['linkage_accuracy'] >= 85:
                st.warning(f"⚠️ Good linkage ({metrics['linkage_accuracy']:.1f}%)")
            else:
                st.error(f"❌ Poor linkage ({metrics['linkage_accuracy']:.1f}%)")
            
            # Completeness table
            st.markdown("---")
            st.subheader("Field Completeness")
            completeness = compute_completeness_metrics(inventory['final_soa']['content'])
            if completeness:
                st.table(completeness)
        else:
            st.error("Could not compute metrics")

with tab6:
    st.subheader("Validation & Conformance Results")
    
    # Get the output directory from the current file path
    if inventory['final_soa'] and inventory['final_soa'].get('path'):
        output_dir = Path(inventory['final_soa']['path']).parent
    else:
        output_dir = None
    
    if not output_dir or not output_dir.exists():
        st.info("Select an output directory to view validation results.")
    else:
        # --- Terminology Enrichment ---
        st.markdown("### 🏷️ Terminology Enrichment (Step 7)")
        
        # Check both test pipeline and main pipeline output for enrichment
        enriched_data = None
        for fname in ["step7_enriched_soa.json", "9_final_soa.json"]:
            f = output_dir / fname
            if f.exists():
                with open(f) as fp:
                    enriched_data = json.load(fp)
                break
        
        if enriched_data:
            timeline = get_timeline(enriched_data)
            if timeline:
                activities = timeline.get('activities', [])
                enriched_activities = [a for a in activities if a.get('definedProcedures')]
                
                if enriched_activities:
                    st.success(f"✅ Enriched {len(enriched_activities)}/{len(activities)} activities with NCI terminology codes")
                    
                    with st.expander("View Enriched Activities"):
                        for act in enriched_activities:
                            procs = act.get('definedProcedures', [])
                            if procs and procs[0].get('code'):
                                code_info = procs[0]['code']
                                st.markdown(f"- **{act.get('name', 'Unknown')}** → `{code_info.get('code')}` ({code_info.get('decode', '')})")
                else:
                    st.info("No activities enriched with terminology codes yet.")
        else:
            st.info("Terminology enrichment not run. Use `--enrich` or `--full` flag.")
        
        st.markdown("---")
        
        # --- Schema Validation ---
        st.markdown("### 📋 Schema Validation (Step 8)")
        schema_file = output_dir / "step8_schema_validation.json"
        if schema_file.exists():
            with open(schema_file) as f:
                schema_result = json.load(f)
            
            if schema_result.get('valid'):
                st.success("✅ Schema validation PASSED")
            else:
                st.error("❌ Schema validation FAILED")
                
            issues = schema_result.get('issues', [])
            warnings = schema_result.get('warnings', [])
            
            if issues:
                st.markdown("**Issues:**")
                for issue in issues:
                    st.markdown(f"- ❌ {issue}")
            
            if warnings:
                with st.expander(f"Warnings ({len(warnings)})"):
                    for warn in warnings:
                        st.markdown(f"- ⚠️ {warn}")
        else:
            st.info("Schema validation not run. Use `--validate-schema` or `--full` flag.")
        
        st.markdown("---")
        
        # --- CDISC CORE Conformance ---
        st.markdown("### 🔬 CDISC CORE Conformance (Step 9)")
        
        # Check for conformance report (could be step9_conformance.json or conformance_report.json)
        conformance_file = None
        for fname in ["step9_conformance.json", "conformance_report.json"]:
            f = output_dir / fname
            if f.exists():
                conformance_file = f
                break
        
        if conformance_file:
            with open(conformance_file) as f:
                conformance_data = json.load(f)
            
            # Parse CORE report structure (handle both naming conventions)
            details = conformance_data.get('Conformance_Details', {})
            rules_report = conformance_data.get('Rules_Report', conformance_data.get('rules_report', []))
            issues = conformance_data.get('Issue_Details', conformance_data.get('issues', []))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("CORE Version", details.get('CORE_Engine_Version', 'N/A'))
            with col2:
                st.metric("Standard", f"{details.get('Standard', 'USDM')} {details.get('Version', '')}")
            with col3:
                st.metric("Rules Executed", len(rules_report))
            
            if not issues:
                st.success("✅ No conformance issues found!")
            else:
                # Group issues by severity
                by_severity = {}
                for issue in issues:
                    sev = issue.get('severity', 'Unknown')
                    by_severity[sev] = by_severity.get(sev, 0) + 1
                
                st.warning(f"⚠️ Found {len(issues)} conformance issues")
                
                for sev, count in sorted(by_severity.items()):
                    if sev.lower() == 'error':
                        st.markdown(f"- ❌ **{sev}**: {count}")
                    elif sev.lower() == 'warning':
                        st.markdown(f"- ⚠️ **{sev}**: {count}")
                    else:
                        st.markdown(f"- ℹ️ **{sev}**: {count}")
                
                with st.expander("View Issue Details"):
                    for issue in issues[:20]:  # Limit to first 20
                        st.markdown(f"**{issue.get('rule_id', 'Unknown')}**: {issue.get('message', '')}")
                    if len(issues) > 20:
                        st.info(f"... and {len(issues) - 20} more issues")
            
            # Show runtime info
            with st.expander("Report Details"):
                st.json(details)
        else:
            st.info("CDISC conformance check not run. Use `--conformance` or `--full` flag.")
