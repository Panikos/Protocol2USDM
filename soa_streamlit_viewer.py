import streamlit as st
import json
import os
import glob

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
            
        timepoints.append({'id': pt['id'], 'label': label})
    return timepoints

def get_activity_groups(timeline):
    # NOTE: The rendering logic in `render_soa_table` is already set up to handle
    # activity groups by looking for the `activityGroupId` on each activity.
    # The primary issue is that the pipeline is not yet populating this data.

    groups_raw = timeline.get('activityGroups', [])
    return {g['id']: g for g in groups_raw if isinstance(g, dict) and g.get('id')}

def get_activities(timeline):
    acts_raw = timeline.get('activities', [])
    acts = []
    for act in acts_raw:
        if isinstance(act, dict) and act.get('id') and act.get('name'):
            acts.append({'id': act['id'], 'name': act['name'], 'desc': act.get('description', ''), 'groupId': act.get('activityGroupId')})
    return acts

def get_activity_timepoints(timeline):
    """Robustly extracts activity-timepoint links from a timeline object."""
    links = set()
    # Check both keys, as raw output might use 'activityTimepoints' and processed uses 'scheduledActivityInstances'
    for key in ['scheduledActivityInstances', 'activityTimepoints']:
        links_raw = timeline.get(key, [])
        for link in links_raw:
            if isinstance(link, dict):
                act_id = link.get('activityId')
                # The post-processor normalizes plannedVisitId to plannedTimepointId
                tp_id = link.get('plannedTimepointId') or link.get('plannedVisitId')
                if act_id and tp_id:
                    links.add((act_id, tp_id))
    return links

def render_json_file(content, file_key):
    """Renders a simple display for a JSON file."""
    st.header(f'Content of: {file_key}')
    st.json(content)

def render_soa_table(soa_content, file_key, filters):
    """Renders a single SoA table, including metadata and the table itself."""
    st.header(f'Analysis of: {file_key}')
    
    metadata = extract_soa_metadata(soa_content)
    if metadata:
        col1, col2, col3 = st.columns(3)
        col1.metric("Timepoints", metadata.get('num_timepoints', 0))
        col2.metric("Activities", metadata.get('num_activities', 0))
        col3.metric("Activity Groups", metadata.get('num_groups', 0))
    else:
        st.warning("Could not extract valid metadata from this file.")

    timeline = get_timeline(soa_content)
    if not timeline:
        st.warning(f"Could not find a valid 'timeline' object in this file. Cannot render SoA table.")
    else:
        all_pts = get_timepoints(timeline)
        all_acts = get_activities(timeline)
        links = get_activity_timepoints(timeline)
        groups = get_activity_groups(timeline)

        # Apply filters
        pts = [p for p in all_pts if not filters.get('tp') or filters['tp'].lower() in p['label'].lower()]
        acts = [a for a in all_acts if not filters.get('act') or filters['act'].lower() in a['name'].lower()]

        if not acts or not pts:
            st.info("No activities or timepoints match the current filters.")
        else:
            for act in acts:
                act['group_name'] = groups.get(act['groupId'], {}).get('name', 'Uncategorized')
            if filters.get('grouped'):
                acts.sort(key=lambda x: (x['group_name'], x['name']))

            # HTML Table Rendering
            header_row = "<tr><th>Activity</th>" + ''.join(f"<th>{p['label']}</th>" for p in pts) + "</tr>"
            body_rows = []
            last_group = None
            for act in acts:
                if filters.get('grouped') and act['group_name'] != last_group:
                    group_header = f"<td colspan='{1 + len(pts)}'>{act['group_name']}</td>"
                    body_rows.append(f"<tr class='group-header-row'>{group_header}</tr>")
                    last_group = act['group_name']

                row = [f"<td class='activity-name' title='ID: {act['id']}'>{act['name']}</td>"]
                for pt in pts:
                    checked = '✔️' if (act['id'], pt['id']) in links else ''
                    row.append(f"<td style='text-align: center;'>{checked}</td>")
                body_rows.append("<tr>" + ''.join(row) + "</tr>")

            table_html = f"""
            <style>
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f0f2f6; position: sticky; top: 0; z-index: 1; }}
                .activity-name {{ font-weight: bold; }}
                .group-header-row {{ background-color: #e0e6ef; font-weight: bold; }}
            </style>
            <table>{header_row}{"".join(body_rows)}</table>
            """
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
    'grouped': st.sidebar.checkbox('Group by Activity Group', value=True)
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
