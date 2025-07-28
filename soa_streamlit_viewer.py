import streamlit as st
import json
import os
import glob
import pandas as pd  # for reading the M11 mapping workbook
import re
import html

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

st.set_page_config(page_title="SoA Extraction Review", layout="wide")
st.title('Schedule of Activities (SoA) Extraction Review')
# Placeholder for dynamic file display; will be updated after run selection.
file_placeholder = st.empty()

# --- Utility Functions ---

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
    """Categorize all relevant pipeline files for a specific run."""
    inventory = {
        'final_soa': None,
        'primary_outputs': {},
        'post_processed': {},
        'intermediate_data': {},
        'configs': {},
        'images': []
    }
    
    # New file map based on main.py output paths
    file_map = {
        '9_reconciled_soa.json': ('final_soa', 'Final Reconciled SoA'),
        '5_raw_text_soa.json': ('primary_outputs', 'Raw Text Extraction'),
        '6_raw_vision_soa.json': ('primary_outputs', 'Raw Vision Extraction'),
        '7_postprocessed_text_soa.json': ('post_processed', 'Text Post-processed'),
        '8_postprocessed_vision_soa.json': ('post_processed', 'Vision Post-processed'),
        '4_soa_header_structure.json': ('intermediate_data', 'SoA Header Structure'),
        '2_soa_pages.json': ('intermediate_data', 'Identified SoA Pages'),
        '1_llm_prompt.txt': ('configs', 'Generated LLM Prompt'),
        '1_llm_prompt_full.txt': ('configs', 'Full LLM Prompt'),
    }

    for f_name, (category, display_name) in file_map.items():
        f_path = os.path.join(base_path, f_name)
        if os.path.exists(f_path):
            content, _ = load_file(f_path)
            if content:
                if category == 'final_soa':
                    inventory[category] = {'display_name': display_name, 'content': content}
                else:
                    inventory[category][display_name] = content

    # Handle soa_entity_mapping.json from root
    mapping_path = "soa_entity_mapping.json"
    if os.path.exists(mapping_path):
        content, _ = load_file(mapping_path)
        if content:
            inventory['configs']['SoA Entity Mapping'] = content

    image_dir = os.path.join(base_path, "3_soa_images")
    if os.path.isdir(image_dir):
        inventory['images'] = sorted(glob.glob(os.path.join(image_dir, "*.png")))
    
        # --- Attach provenance if stored in separate file ---
    if inventory['final_soa']:
        final_path = inventory['final_soa']['path'] if isinstance(inventory['final_soa'], dict) and 'path' in inventory['final_soa'] else None
        if not final_path:
            # Attempt to reconstruct path based on base_path
            final_path = os.path.join(base_path, '9_reconciled_soa.json')
        prov_path = final_path.replace('.json', '_provenance.json')
        if os.path.exists(prov_path):
            prov_content, _ = load_file(prov_path)
            if isinstance(inventory['final_soa']['content'], dict) and prov_content and isinstance(prov_content, dict):
                # Only merge if p2uProvenance missing
                if 'p2uProvenance' not in inventory['final_soa']['content']:
                    inventory['final_soa']['content']['p2uProvenance'] = prov_content
    
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

def get_timeline(soa):
    """Extracts the timeline object robustly from a USDM Wrapper-Input JSON."""
    if not isinstance(soa, dict):
        return None
    try:
        study = soa.get('study', {})
        versions = study.get('versions') or study.get('studyVersions')
        return versions[0].get('timeline')
    except (KeyError, IndexError, TypeError):
        return None

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

def get_timepoints(timeline):
    pts_raw = timeline.get('plannedTimepoints', [])
    timepoints = []
    for pt in pts_raw:
        if not (isinstance(pt, dict) and pt.get('id') and pt.get('name')):
            continue
        
        name = pt['name']
        desc = pt.get('description')
        
        # Use the timepoint name as the primary label; description will be shown separately in timing band if needed.
        # Strip redundant parenthetical legacy details (e.g., "Visit 1 (Week -2)")
        base_name = re.sub(r"\s*\(.*\)$", "", name)

# --- New Python-based SoA Renderer ---

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


def render_flexible_soa(data):
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
        parent_name = "Uncategorized Activities"
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

    if not col_index_data:
        st.error("Could not build timeline columns – no planned timepoints available.")
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

    st.dataframe(df)

def get_provenance_sources(provenance, item_type, item_id):
    """
    Determines the provenance (text, vision, or both) for a given item ID.
    This logic is specific to the key format in '9_reconciled_soa.json'.
    """
    sources = {'text': False, 'vision': False}
    if not provenance or item_type not in provenance or not item_id:
        return sources

    id_num_match = re.search(r'-(\d+)$', item_id)
    if not id_num_match:
        return sources
    
    id_num = id_num_match.group(1)

    # Define the keys based on the pattern in the JSON file
    key_map = {
        'activities': (f"activity-{id_num}", f"act{id_num}"),
        'encounters': (f"encounter-{id_num}", f"enc_{id_num}")
    }

    if item_type not in key_map:
        return sources

    text_key, vision_key = key_map[item_type]
    
    provenance_data = provenance.get(item_type, {})
    if provenance_data.get(text_key) == 'text':
        sources['text'] = True
    if provenance_data.get(vision_key) == 'vision':
        sources['vision'] = True
        
    return sources

def style_provenance(df, provenance, activity_map, encounter_map):
    """
    Applies background color styling to the DataFrame based on data provenance.
    Returns a DataFrame of CSS styles.
    """
    # Create a new DataFrame of the same size to hold the styles
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Provenance colors
    colors = {
        'text': '#60a5fa',    # blue-400
        'vision': '#facc15',  # yellow-400
        'both': '#4ade80'     # green-400
    }

    for (group_name, activity_name), row in df.iterrows():
        activity_id = activity_map.get((group_name, activity_name))
        if not activity_id:
            continue

        for (epoch_name, encounter_name) in df.columns:
            if row[(epoch_name, encounter_name)] == 'X':
                encounter_id = encounter_map.get((epoch_name, encounter_name))
                if not encounter_id:
                    continue

                # Determine the provenance of the cell's row (activity) and column (encounter)
                activity_prov = get_provenance_sources(provenance, 'activities', activity_id)
                encounter_prov = get_provenance_sources(provenance, 'encounters', encounter_id)

                # The cell's provenance is a union of the row's and column's provenance
                from_text = activity_prov['text'] or encounter_prov['text']
                from_vision = activity_prov['vision'] or encounter_prov['vision']

                color = ''
                if from_text and from_vision:
                    color = colors['both']
                elif from_text:
                    color = colors['text']
                elif from_vision:
                    color = colors['vision']
                
                if color:
                    style_df.loc[(group_name, activity_name), (epoch_name, encounter_name)] = f'background-color: {color}'
                    
    return style_df


def render_soa_table(data):
    """
    Parses the USDM data and renders a styled Schedule of Activities table.
    """
    if not data:
        st.warning("No SoA data provided to renderer.")
        return

    try:
        timeline = data['study']['versions'][0]['timeline']
        provenance = data.get('p2uProvenance', {})
    except (KeyError, IndexError, TypeError) as e:
        st.error(f"Invalid USDM JSON structure. Missing expected key or invalid data: {e}")
        st.json(data) # Show the problematic data
        return

    # --- Data Extraction and Mapping ---
    epochs = timeline.get('epochs', [])
    encounters = timeline.get('encounters', [])
    activities = timeline.get('activities', [])
    activity_groups = timeline.get('activityGroups', [])
    planned_timepoints = timeline.get('plannedTimepoints', [])
    activity_timepoints = timeline.get('activityTimepoints', [])

    if not all([epochs, encounters, activities, activity_groups, planned_timepoints, activity_timepoints]):
        st.warning("SoA data is missing one or more key entities (epochs, encounters, activities, etc.). Cannot render table.")
        return

    # Create maps for efficient lookups
    planned_timepoint_map = {pt['id']: pt for pt in planned_timepoints}
    
    activity_encounter_map = set()
    for at in activity_timepoints:
        pt = planned_timepoint_map.get(at['plannedTimepointId'])
        if pt and pt.get('encounterId') and at.get('isPerformed'):
            key = (at['activityId'], pt['encounterId'])
            activity_encounter_map.add(key)

    # --- Prepare DataFrame Structure ---
    
    # Create multi-index for rows
    row_index_data = []
    # Create a map to get activity_id from its name and group for the styler
    activity_id_map = {} 
    for group in activity_groups:
        group_id = group['id']
        group_name = group['name']
        for act in activities:
            if act.get('activityGroupId') == group_id:
                activity_name = act['name']
                row_index_data.append((group_name, activity_name))
                activity_id_map[(group_name, activity_name)] = act['id']
                
    if not row_index_data:
        st.info("No activities found to display in the table.")
        return

    row_multi_index = pd.MultiIndex.from_tuples(row_index_data, names=['Activity Group', 'Activity / Procedure'])

    # Create multi-index for columns
    col_index_data = []
    # Create a map to get encounter_id from its name and epoch for the styler
    encounter_id_map = {} 
    ordered_encounters = []
    for epoch in epochs:
        epoch_id = epoch['id']
        epoch_name = epoch['name']
        for enc in encounters:
            if enc.get('epochId') == epoch_id:
                encounter_name = enc['name']
                col_index_data.append((epoch_name, encounter_name))
                encounter_id_map[(epoch_name, encounter_name)] = enc['id']
                ordered_encounters.append(enc) # Keep a simple ordered list for data filling

    if not col_index_data:
        st.info("No encounters found to display in the table.")
        return

    col_multi_index = pd.MultiIndex.from_tuples(col_index_data, names=['Epoch', 'Encounter'])

    # --- Create and Populate DataFrame ---
    df = pd.DataFrame("", index=row_multi_index, columns=col_multi_index)

    for (group_name, activity_name), activity_id in activity_id_map.items():
        for enc in ordered_encounters:
            encounter_id = enc['id']
            epoch_name = next((e['name'] for e in epochs if e['id'] == enc.get('epochId')), None)
            encounter_name = enc['name']
            
            if (activity_id, encounter_id) in activity_encounter_map:
                if (epoch_name, encounter_name) in df.columns:
                    df.loc[(group_name, activity_name), (epoch_name, encounter_name)] = 'X'

    # --- Display Legend and Table ---
    st.markdown("""
    <h3 style="font-weight: 600;">Provenance Legend</h3>
    <div style="display: flex; align-items: center; gap: 1.5rem;">
        <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #60a5fa;"></div><span>Text</span></div>
        <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #facc15;"></div><span>Vision</span></div>
        <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #4ade80;"></div><span>Both</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Convert the styled DataFrame to HTML to get the desired merged-cell effect for the index
    styler = df.style.apply(style_provenance, provenance=provenance, activity_map=activity_id_map, encounter_map=encounter_id_map, axis=None)
    html = styler.to_html(sparse_index=True)
    st.markdown(html, unsafe_allow_html=True)

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

# --- Completeness badge ---
if inventory['final_soa']:
    tl = get_timeline(inventory['final_soa']['content'])
    if tl:
        total_links = sum(len(v) for v in get_activity_timepoints(tl).values())
        num_acts = len(tl.get('activities', []))
        num_tps = len(tl.get('plannedTimepoints', []))
        denom = num_acts * num_tps if num_acts and num_tps else 0
        completeness = (total_links / denom * 100) if denom else 0
        if completeness >= 95:
            badge_color = '#4caf50'
        elif completeness >= 80:
            badge_color = '#ff9800'
        else:
            badge_color = '#f44336'
        st.sidebar.markdown(f"<div style='background:{badge_color};color:white;padding:6px;border-radius:4px;text-align:center;'>Completeness {completeness:.0f}%</div>", unsafe_allow_html=True)






# --- Main Display: Render the final SoA --- 
st.header("Final Reconciled SoA")
if not inventory['final_soa']:
    st.warning("The final reconciled SoA (`9_reconciled_soa.json`) was not found for this run.")
else:
    # The main view always shows the final, precise render
    render_soa_table(inventory['final_soa']['content'])
    with st.expander("Show Full JSON Output"):
        st.json(inventory['final_soa']['content'])

# --- Debugging / Intermediate Files Section ---
st.markdown("--- ")
st.header("Intermediate Outputs & Debugging")

# Create tabs for the different categories of intermediate files
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Raw Outputs", 
    "Post-Processed", 
    "Data Files", 
    "Config Files", 
    "SoA Images",
    "Completeness Report"
])

with tab1:
    st.subheader("Primary Extraction Outputs (Raw)")
    if not inventory['primary_outputs']:
        st.info("No raw text or vision output files found.")
    else:
        if inventory['primary_outputs']:
            output_tabs = st.tabs(list(inventory['primary_outputs'].keys()))
            for i, (key, content) in enumerate(inventory['primary_outputs'].items()):
                with output_tabs[i]:
                    render_flexible_soa(content)
                    if st.checkbox("Show Full JSON Output", key=f"json_primary_{i}"):
                        st.json(content)

with tab2:
    st.subheader("Post-Processed Outputs")
    if not inventory['post_processed']:
        st.info("No post-processed output files found.")
    else:
        if inventory['post_processed']:
            # The key is the filename, the value is the content
            output_tabs = st.tabs([inventory['file_map'].get(k, k) for k in inventory['post_processed'].keys()])
            for i, (filename, content) in enumerate(inventory['post_processed'].items()):
                with output_tabs[i]:
                    render_flexible_soa(content)
                    if st.checkbox("Show Full JSON Output", key=f"json_post_{i}"):
                        st.json(content)

with tab3:
    st.subheader("Intermediate Data Files")
    if not inventory['intermediate_data']:
        st.info("No intermediate data files found.")
    else:
        for key, content in inventory['intermediate_data'].items():
            with st.expander(key):
                st.json(content if isinstance(content, dict) else str(content))

with tab4:
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

with tab5:
    st.subheader("Extracted SoA Images")
    if not inventory['images']:
        st.info("No images found in `3_soa_images/`")
    else:
        for img_path in inventory['images']:
            if not os.path.exists(img_path):
                st.warning(f"Image not found: {img_path}")
                continue
            try:
                st.image(img_path, caption=os.path.basename(img_path), use_container_width=True)
            except Exception as e:
                st.warning(f"Could not load image {img_path}: {e}")

with tab6:
    st.subheader("USDM Completeness Report")
    if not inventory['final_soa']:
        st.info("Run a pipeline to generate a final SoA first.")
    else:
        metrics = compute_completeness_metrics(inventory['final_soa']['content'])
        if metrics:
            st.table(metrics)
        else:
            st.info("Could not compute metrics; timeline missing or malformed.")
