import streamlit as st
import json
import os
import glob
import pandas as pd  # for reading the M11 mapping workbook
import re
import html


st.set_page_config(page_title="SoA Extraction Review", layout="wide")
st.title('Schedule of Activities (SoA) Extraction Review')

# --- Utility Functions ---

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
        
        # If description provides additional, non-redundant info, combine it.
        if desc and desc.strip() and desc.lower() not in name.lower():
            label = f"{name} ({desc})"
        else:
            label = name
            
        timepoints.append({'id': pt['id'], 'name': name, 'label': label})
        
    # Sort the timepoints using the custom key
    timepoints.sort(key=lambda tp: _get_timepoint_sort_key(tp['label']))
    return timepoints

def get_activity_groups(timeline):
    if not timeline:
        return []
    return timeline.get('activityGroups', [])

def get_activities(timeline):
    acts = []
    if timeline and 'activities' in timeline:
        for act in timeline['activities']:
            acts.append({'id': act['id'], 'name': act['name'], 'desc': act.get('description', ''), 'groupId': act.get('activityGroupId')})
    return acts

def get_epochs(timeline):
    """Robustly extracts epoch definitions from a timeline object."""
    if not timeline or 'epochs' not in timeline:
        return []
    return [e for e in timeline['epochs'] if isinstance(e, dict) and e.get('id')]

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

def _generate_band_html(display_timepoints, tp_to_entity_map, band_class):
    """
    Generates a single HTML <tr> for a header band (Epoch or Encounter).
    """
    if not display_timepoints or not any(tp_to_entity_map.values()):
        return ""

    html_parts = ['<th class="first-col"></th>'] # Spacer for the activity column
    current_entity_id = None
    colspan = 0
    
    # Get the entity for the first timepoint
    first_tp_id = display_timepoints[0]['id']
    current_entity = tp_to_entity_map.get(first_tp_id)
    current_entity_id = current_entity['id'] if current_entity else None
    current_entity_name = current_entity['name'] if current_entity else 'Unassigned'
    
    for tp in display_timepoints:
        entity = tp_to_entity_map.get(tp['id'])
        entity_id = entity['id'] if entity else None

        if entity_id != current_entity_id:
            safe_name = html.escape(current_entity_name)
            html_parts.append(f'<th class="{band_class}" colspan="{colspan}">{safe_name}</th>')
            current_entity_id = entity_id
            current_entity_name = entity['name'] if entity else 'Unassigned'
            colspan = 0

        colspan += 1

    # Add the last cell
    if colspan > 0:
        safe_name = html.escape(current_entity_name)
        html_parts.append(f'<th class="{band_class}" colspan="{colspan}">{safe_name}</th>')

    return f"<tr>{''.join(html_parts)}</tr>"

def render_soa_table(soa_content, file_key, filters):
    """Renders a single SoA table, including metadata and the table itself."""
    st.subheader(f"SoA from: `{file_key}`")
    timeline = get_timeline(soa_content)
    if not timeline:
        st.warning(f"Could not extract a valid USDM timeline from '{file_key}'. This file may not be a valid SoA JSON, or it may be empty.")
        return

    # --- Data Extraction and Filtering ---
    timepoints = get_timepoints(timeline)
    epochs = get_epochs(timeline)
    all_encounters = timeline.get('encounters', []) # Keep for M11 legacy
    activity_groups = get_activity_groups(timeline)
    activities = get_activities(timeline)
    activity_timepoints = get_activity_timepoints(timeline)

    if not timepoints or not activities:
        st.info("No timepoints or activities found in the timeline.")
        return

    # Filter activities and timepoints based on sidebar inputs
    if filters['act']:
        activities = [a for a in activities if filters['act'].lower() in a.get('name', '').lower()]
    if filters['tp']:
        timepoints = [t for t in timepoints if filters['tp'].lower() in t.get('label', '').lower()]

    if not timepoints or not activities:
        st.info("No activities or timepoints match the current filter.")
        return

    tp_ids = {t['id'] for t in timepoints}

    # --- Build Mappings for Header Bands ---
    enc_to_epoch_map = {enc['id']: epoch for epoch in epochs for enc in epoch.get('encounters', [])}
    all_encs_map = {enc['id']: enc for epoch in epochs for enc in epoch.get('encounters', [])}
    # Add encounters from root if they exist (for older formats)
    for enc in all_encounters:
        if enc['id'] not in all_encs_map:
            all_encs_map[enc['id']] = enc

    tp_to_enc_map = {tp['id']: all_encs_map.get(tp.get('relativeFromScheduledInstanceId')) for tp in timepoints}
    tp_to_epoch_map = {tp['id']: enc_to_epoch_map.get(tp.get('relativeFromScheduledInstanceId')) for tp in timepoints}
    
    # --- HTML Generation ---
    # Header Rows
    epoch_band_html = ""
    if filters.get('epoch_band'):
        epoch_band_html = _generate_band_html(timepoints, tp_to_epoch_map, 'epoch-band')

    encounter_band_html = ""
    if filters.get('enc_band'):
        encounter_band_html = _generate_band_html(timepoints, tp_to_enc_map, 'encounter-band')

    # Standard Header
    header_html = "".join([f"<th>{html.escape(tp['label'])}</th>" for tp in timepoints])

    # Body Rows
    body_html = ""
    if filters.get('grouped') and activity_groups:
        group_map = {g['id']: g for g in activity_groups}
        activity_to_group_map = {act_id: g_id for g in activity_groups for act_id in g.get('activityIds', [])}
        
        grouped_activities = {}
        for act in activities:
            g_id = activity_to_group_map.get(act['id'])
            grouped_activities.setdefault(g_id, []).append(act)

        for g_id, acts_in_group in sorted(grouped_activities.items(), key=lambda item: group_map.get(item[0], {}).get('name', 'zzzz')):
            group_name = html.escape(group_map.get(g_id, {}).get('name', 'Ungrouped Activities'))
            body_html += f'<tr><td colspan="{len(timepoints) + 1}" class="group-header">{group_name}</td></tr>'
            for act in sorted(acts_in_group, key=lambda x: x.get('name', '')):
                row_cells = "".join([f"<td>{'X' if t['id'] in activity_timepoints.get(act['id'], []) else ''}</td>" for t in timepoints])
                safe_act_name = html.escape(act['name'])
                body_html += f"<tr><td class='activity-name'>{safe_act_name}</td>{row_cells}</tr>"

    else: # Not grouped
        for act in sorted(activities, key=lambda x: x.get('name', '')):
            row_cells = "".join([f"<td>{'X' if t['id'] in activity_timepoints.get(act['id'], []) else ''}</td>" for t in timepoints])
            safe_act_name = html.escape(act['name'])
            body_html += f"<tr><td class='activity-name'>{safe_act_name}</td>{row_cells}</tr>"

    # --- Final Assembly ---
    # Define CSS separately to avoid f-string issues with curly braces
    CSS = """
    <style>
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #cccccc; text-align: center; padding: 8px; }
        .first-col, .activity-name { text-align: left; background-color: #f2f2f2; font-weight: bold; position: sticky; left: 0; z-index: 1; }
        .group-header { text-align: left; font-weight: bold; background-color: #e0e0e0; }
        thead th { background-color: #f2f2f2; position: sticky; top: 0; z-index: 2; }
        .epoch-band { background-color: #ADD8E6; }
        .encounter-band { background-color: #90EE90; }
    </style>
    """
    st.markdown(CSS, unsafe_allow_html=True)

    # Build the HTML table structure robustly to prevent string corruption
    html_parts = [
        "<table>",
        "<thead>",
        epoch_band_html,
        encounter_band_html,
        '<tr><th class="first-col">Activity</th>',
        header_html,
        "</tr>",
        "</thead>",
        "<tbody>",
        body_html,
        "</tbody>",
        "</table>"
    ]
    table_html = "".join(html_parts)
    
    st.markdown(table_html, unsafe_allow_html=True)

# --- Main App Layout ---

OUTPUT_DIR = "output"

# --- Sidebar ---
st.sidebar.title("Run Selection")

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
inventory = get_file_inventory(run_path)

st.sidebar.title('Display Options')
filters = {
    'act': st.sidebar.text_input('Filter activities by name:'),
    'tp': st.sidebar.text_input('Filter timepoints by label:'),
    'grouped': st.sidebar.checkbox('Group by Activity Group', value=True),
    'epoch_band': st.sidebar.checkbox('Show Epoch band', value=True),
    'enc_band': st.sidebar.checkbox('Show Encounter band', value=True)
}




# --- Main Content Area ---
if not inventory['final_soa']:
    st.warning('Final reconciled SoA (`9_reconciled_soa.json`) not found. Please run the full pipeline.')
else:
    render_soa_table(inventory['final_soa']['content'], inventory['final_soa']['display_name'], filters)
    with st.expander("Show Full JSON Output"):
        st.json(inventory['final_soa']['content'])

# --- Debugging / Intermediate Files Section ---
st.markdown("--- ")
st.header("Intermediate Outputs & Debugging")

# Create tabs for the different categories of intermediate files
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Raw Outputs", 
    "Post-Processed", 
    "Data Files", 
    "Config Files", 
    "SoA Images"
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
                    render_soa_table(content, key, filters)
                    if st.checkbox("Show Full JSON Output", key=f"json_primary_{i}"):
                        st.json(content)

with tab2:
    st.subheader("Post-Processed Outputs")
    if not inventory['post_processed']:
        st.info("No post-processed output files found.")
    else:
        if inventory['post_processed']:
            output_tabs = st.tabs(list(inventory['post_processed'].keys()))
            for i, (key, content) in enumerate(inventory['post_processed'].items()):
                with output_tabs[i]:
                    render_soa_table(content, key, filters)
                    if st.checkbox("Show Full JSON Output", key=f"json_postprocessed_{i}"):
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
            st.image(img_path, caption=os.path.basename(img_path), use_container_width=True)
