import streamlit as st
import json
import os

st.set_page_config(page_title="SoA Clinical Review", layout="wide")
st.title('Schedule of Activities (SoA) Clinical Review')

# --- Utility functions ---
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_file_candidates():
    files = os.listdir('.')
    outputs = {}
    configs = {}
    
    output_prefixes = ['STEP', 'soa_']
    config_files = ['soa_entity_mapping.json', 'llm_soa_prompt.txt']

    for f in sorted(files):
        if f.endswith('.json'):
            if any(f.startswith(p) for p in output_prefixes) and f not in config_files:
                try:
                    outputs[f] = load_json(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    outputs[f] = {'error': 'Could not decode JSON.'}
            elif f in config_files:
                try:
                    configs[f] = load_json(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    configs[f] = {'error': 'Could not decode JSON.'}
        elif f.endswith('.txt') and f in config_files:
            with open(f, 'r', encoding='utf-8') as file:
                configs[f] = file.read()
                
    return outputs, configs

def extract_soa_metadata(soa):
    study = soa.get('study', {})
    study_id = study.get('id', 'N/A')
    study_name = study.get('name', 'N/A')
    usdm_version = soa.get('usdmVersion', 'N/A')
    
    timeline = get_timeline(soa)
    if timeline:
        num_timepoints = len(timeline.get('plannedTimepoints', []))
        num_activities = len(timeline.get('activities', []))
        num_groups = len(timeline.get('activityGroups', []))
    else:
        num_timepoints, num_activities, num_groups = 0, 0, 0
        
    return {
        'study_id': study_id,
        'study_name': study_name,
        'usdm_version': usdm_version,
        'num_timepoints': num_timepoints,
        'num_activities': num_activities,
        'num_groups': num_groups
    }

def get_timeline(soa):
    # USDM Wrapper-Input
    if isinstance(soa, dict):
        # Try: Wrapper-Input
        if 'study' in soa:
            study = soa['study']
            if 'versions' in study and study['versions']:
                v = study['versions'][0]
                if 'timeline' in v:
                    return v['timeline']
                if 'studyDesign' in v and 'timeline' in v['studyDesign']:
                    return v['studyDesign']['timeline']
            if 'studyVersions' in study and study['studyVersions']:
                v = study['studyVersions'][0]
                if 'studyDesign' in v and 'timeline' in v['studyDesign']:
                    return v['studyDesign']['timeline']
                if 'timeline' in v:
                    return v['timeline']
        # Try: Study-Input
        if 'versions' in soa and soa['versions']:
            v = soa['versions'][0]
            if 'timeline' in v:
                return v['timeline']
            if 'studyDesign' in v and 'timeline' in v['studyDesign']:
                return v['studyDesign']['timeline']
        if 'studyVersions' in soa and soa['studyVersions']:
            v = soa['studyVersions'][0]
            if 'studyDesign' in v and 'timeline' in v['studyDesign']:
                return v['studyDesign']['timeline']
            if 'timeline' in v:
                return v['timeline']
        # Try: direct timeline
        if 'timeline' in soa:
            return soa['timeline']
    return None


def get_timepoints(timeline):
    pts_raw = timeline.get('plannedTimepoints', [])
    pts = []
    for i, pt in enumerate(pts_raw):
        if isinstance(pt, dict):
            ptid = pt.get('plannedTimepointId') or pt.get('id') or pt.get('label') or f"TP{i+1}"
            label = pt.get('visit') or pt.get('label') or pt.get('name') or pt.get('timepoint') or ptid
            week = pt.get('week') or pt.get('relativeTime') or pt.get('timepointDate')
            desc = pt.get('description', '')
            pts.append({'id': ptid, 'label': label, 'week': week, 'desc': desc, 'raw': pt})
        elif isinstance(pt, str):
            ptid = f"TP{i+1}"
            pts.append({'id': ptid, 'label': pt, 'week': None, 'desc': '', 'raw': pt})
    return pts

def get_activity_groups(timeline):
    ags = timeline.get('activityGroups', [])
    groups = []
    for ag in ags:
        gid = ag.get('activityGroupId') or ag.get('id')
        name = ag.get('name') or gid
        aids = ag.get('activityIds') if 'activityIds' in ag else ag.get('activities', [])
        groups.append({'id': gid, 'name': name, 'activityIds': aids})
    return groups

def get_activities(timeline):
    acts = timeline.get('activities', [])
    result = []
    for i, act in enumerate(acts):
        if isinstance(act, dict):
            aid = act.get('activityId') or act.get('id') or f"A{i+1}"
            name = act.get('name') or act.get('description') or aid
            desc = act.get('description', '')
            result.append({'id': aid, 'name': name, 'desc': desc, 'raw': act})
        elif isinstance(act, str):
            aid = f"A{i+1}"
            result.append({'id': aid, 'name': act, 'desc': '', 'raw': act})
    return result

def get_activity_timepoints(timeline):
    # Try to extract links from a 'matrix' field if present
    links = set()
    acts = timeline.get('activities', [])
    pts = timeline.get('plannedTimepoints', [])
    matrix = timeline.get('matrix')
    if matrix and isinstance(matrix, list):
        # Assume matrix is a 2D array [activity][timepoint] with 1/0 or X/''
        for i, row in enumerate(matrix):
            for j, val in enumerate(row):
                if val and i < len(acts) and j < len(pts):
                    aid = acts[i].get('activityId') or acts[i].get('id')
                    ptid = pts[j].get('plannedTimepointId') or pts[j].get('id')
                    if aid and ptid:
                        links.add((aid, ptid))
        if links:
            return links
    # Fallback: activityTimepoints
    atps = timeline.get('activityTimepoints', [])
    for atp in atps:
        aid = atp.get('activityId') or atp.get('id') or atp.get('activityGroupId')
        ptid = atp.get('plannedTimepointId') or atp.get('timepointId') or atp.get('id')
        if aid and ptid:
            links.add((aid, ptid))
    # Fallback: activities with plannedTimepoints
    for act in acts:
        aid = act.get('activityId') or act.get('id')
        for k in ['plannedTimepoints', 'plannedTimepointIds']:
            if k in act:
                for ptid in act[k]:
                    links.add((aid, ptid))
    return links

import pandas as pd

def _render_soa_table_core(acts, pts, links, pt_groups, file_name):
    # --- Render table with group headers for both axes ---
    table_html = ["<table style='border-collapse:collapse;width:100%'>"]
    # Column group headers (visit groups)
    if any(g != 'No Group' for g in pt_groups):
        table_html.append("<tr><th></th><th></th>" + ''.join(f"<th style='border:1px solid #ccc;background:#e9ecef'><b>{g}</b></th>" for g in pt_groups) + "</tr>")
    # Header row
    table_html.append("<tr><th>Activity</th><th>Description</th>" + ''.join(f"<th style='border:1px solid #ccc'>{p['label']}</th>" for p in pts) + "</tr>")
    for idx, act in enumerate(acts):
        row_color = '#f8fafc' if idx % 2 == 0 else '#fff'
        tooltip = f" title='{act['desc'].replace("'", "&#39;")}'" if act['desc'] else ''
        row = [f"<td class='activity' style='border:1px solid #ccc;padding:4px;text-align:left;background:{row_color}'{tooltip}><b>{act['name']}</b></td>",
               f"<td style='border:1px solid #ccc;padding:4px;text-align:left;background:{row_color}'>{act['desc']}</td>"]
        for i, pt in enumerate(pts):
            checked = '✔️' if (act['id'], pt['id']) in links else ''
            row.append(f"<td style='border:1px solid #ccc;padding:4px;background:{row_color}'>{checked}</td>")
        table_html.append("<tr>" + ''.join(row) + "</tr>")
    table_html.append("</table>")
    import streamlit as st
    st.markdown(''.join(table_html), unsafe_allow_html=True)
    st.success('No missing cells!')

def render_soa_table(soa, filter_activity=None, filter_timepoint=None, grouped=True, file_name='soa', m11_mode=False):
    # If m11_mode, soa is already M11-table-aligned dict
    if m11_mode:
        acts = soa['activities']
        pts = soa['timepoints']
        matrix = soa['matrix']
        footnotes = soa.get('footnotes', [])
        legend = soa.get('legend', [])
        # Milestone detection
        milestone_cols = set(i for i, pt in enumerate(pts) if pt.get('milestone'))
        # Footnote markers map
        pt_footnotes = {pt['plannedTimepointId']: [] for pt in pts}
        act_footnotes = {act['activityId']: [] for act in acts}
        for f in footnotes:
            # Try to parse id pattern
            if f['id'].startswith('pt_'):
                pid = f['id'][3:].replace('_n','')
                pt_footnotes.setdefault(pid, []).append(str(len(pt_footnotes[pid])+1))
            elif f['id'].startswith('act_'):
                aid = f['id'][4:].replace('_n','')
                act_footnotes.setdefault(aid, []).append(str(len(act_footnotes[aid])+1))
        table_html = ["<table style='border-collapse:collapse;width:100%'>"]
        # Header
        table_html.append("<tr>" + ''.join([
            f"<th style='border:1px solid #ccc;padding:4px'>{c}</th>" for c in ['Activity', 'Description'] + [
                f"<span style='background:#ffeeba'>{p['label']}</span>" if i in milestone_cols else p['label'] for i, p in enumerate(pts)
            ]
        ]) + "</tr>")
        # Rows
        for idx, act in enumerate(acts):
            row_color = '#f8fafc' if idx % 2 == 0 else '#fff'
            act_marker = ''.join(f"<sup>{m}</sup>" for m in act_footnotes.get(act['activityId'], []))
            row = [f"<td class='activity' style='border:1px solid #ccc;padding:4px;text-align:left;background:{row_color}'><b>{act['name']}{act_marker}</b></td>",
                   f"<td style='border:1px solid #ccc;padding:4px;text-align:left;background:{row_color}'>{act.get('desc','')}</td>"]
            for j, pt in enumerate(pts):
                pt_marker = ''.join(f"<sup>{m}</sup>" for m in pt_footnotes.get(pt['plannedTimepointId'], []))
                checked = '✔️' if matrix[idx][j] else ''
                cell_bg = '#ffeeba' if j in milestone_cols else row_color
                row.append(f"<td style='border:1px solid #ccc;padding:4px;background:{cell_bg}'>{checked}{pt_marker}</td>")
            table_html.append("<tr>" + ''.join(row) + "</tr>")
        table_html.append("</table>")
        st.markdown(''.join(table_html), unsafe_allow_html=True)
        # Legend
        if legend:
            st.markdown("**Legend:**")
            for l in legend:
                st.markdown(f"- {l.get('symbol','')}: {l.get('meaning','')}")
        # Footnotes
        if footnotes:
            st.markdown("**Footnotes:**")
            for i, f in enumerate(footnotes, 1):
                st.markdown(f"<sup>{i}</sup> {f['text']}", unsafe_allow_html=True)
        return

    timeline = get_timeline(soa)
    if not timeline:
        st.error('No timeline found in SoA JSON.')
        return
    pts = get_timepoints(timeline)
    acts = get_activities(timeline)
    ags = get_activity_groups(timeline)
    atps = get_activity_timepoints(timeline)
    # --- Visit group support ---
    vgs = timeline.get('visitGroups', [])
    visit_group_map = {v['id']: v['name'] for v in vgs}
    # Map visits to groups
    pt_group_ids = [pt['raw'].get('groupId') if isinstance(pt['raw'], dict) else None for pt in pts]
    pt_groups = [visit_group_map.get(gid, 'No Group') if gid else 'No Group' for gid in pt_group_ids]

    # Filtering
    if filter_activity:
        acts = [a for a in acts if filter_activity.lower() in a['name'].lower()]
    if filter_timepoint:
        pts = [p for p in pts if filter_timepoint.lower() in p['label'].lower()]
        pt_groups = [pt_groups[i] for i, p in enumerate(pts) if filter_timepoint.lower() in p['label'].lower()]

    # Activity group map
    group_map = {}
    for ag in ags:
        for aid in ag['activityIds']:
            group_map[aid] = ag['name']
    # Always use get_activity_timepoints for links
    links = get_activity_timepoints(timeline)
    # Use get_activities/get_timepoints for correct ID mapping
    if grouped:
        # Prepare groups
        groups = {}
        grouped_ids = set()
        for ag in ags:
            group_acts = [a for a in acts if a['id'] in ag['activityIds']]
            if group_acts:
                groups[ag['name']] = group_acts
                grouped_ids.update(a['id'] for a in group_acts)
        # Find ungrouped activities
        ungrouped = [a for a in acts if a['id'] not in grouped_ids]
        if ungrouped:
            groups['Ungrouped'] = ungrouped
        # Render each group as a collapsible section
        for group_name, group_acts in groups.items():
            with st.expander(f"{group_name}", expanded=True):
                _render_soa_table_core(group_acts, pts, links, pt_groups, file_name)
        return
    # --- Render table with group headers for both axes ---
    table_html = ["<style>",
                  "table {border-collapse: collapse; width: 100%;}",
                  "th, td {border: 1px solid #ddd; padding: 8px; text-align: left;}",
                  "th {background-color: #f2f2f2;}",
                  ".activity-name {font-weight: bold;}",
                  ".even-row {background-color: #f9f9f9;}",
                  ".odd-row {background-color: #ffffff;}",
                  "</style>",
                  "<table>"]
    # Column group headers (visit groups)
    if any(g != 'No Group' for g in pt_groups):
        table_html.append("<tr><th></th><th></th>" + ''.join(f"<th><b>{g}</b></th>" for g in pt_groups) + "</tr>")
    # Header row
    table_html.append("<tr><th>Activity</th><th>Description</th>" + ''.join(f"<th>{p['label']}</th>" for p in pts) + "</tr>")
    for idx, act in enumerate(acts):
        row_class = 'even-row' if idx % 2 == 0 else 'odd-row'
        tooltip = f" title='{act['desc'].replace("'", "&#39;")}'" if act['desc'] else ''
        row = [f"<td class='activity-name {row_class}'{tooltip}><b>{act['name']}</b></td>",
               f"<td class='{row_class}'>{act['desc']}</td>"]
        for i, pt in enumerate(pts):
            checked = '✔️' if (act['id'], pt['id']) in links else ''
            row.append(f"<td class='{row_class}'>{checked}</td>")
        table_html.append("<tr>" + ''.join(row) + "</tr>")
    table_html.append("</table>")
    st.markdown(''.join(table_html), unsafe_allow_html=True)
    st.caption('Rows are grouped by Activity Group and columns by Visit Group (if present). Hover over activity names for descriptions.')
    # Clinical review stats
    st.markdown('---')
    st.subheader('Clinical Review Summary')
    n_acts = len(acts)
    n_pts = len(pts)
    coverage = sum(1 for act in acts for pt in pts if (act['id'], pt['id']) in links)
    st.markdown(f"**# Activities:** {n_acts}  |  **# Visits:** {n_pts}  |  **Coverage:** {coverage} cells with data")
    missing = [(act['name'], pt['label']) for act in acts for pt in pts if (act['id'], pt['id']) not in links]
    if missing:
        st.markdown(f"**Missing cells:** {len(missing)} (first 10 shown)")
        st.write(missing[:10])
    else:
        st.success('No missing cells!')

def render_metadata(soa):
    metadata = extract_soa_metadata(soa)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="USDM Version", value=metadata['usdm_version'])
    with col2:
        st.metric(label="Study ID", value=metadata['study_id'])
    with col3:
        st.metric(label="Study Name", value=metadata['study_name'])

    st.markdown(f"**Timeline Contains:** {metadata['num_timepoints']} Timepoints | {metadata['num_activities']} Activities | {metadata['num_groups']} Activity Groups")

# --- Main App Layout ---
output_files, config_files = get_file_candidates()

# --- Sidebar ---
st.sidebar.title('File Explorer')

# Sidebar Filtering & Toggles
st.sidebar.subheader('Table Display Options')
filter_activity = st.sidebar.text_input('Filter activities (by name):', '')
filter_timepoint = st.sidebar.text_input('Filter timepoints (by label):', '')
grouped = st.sidebar.checkbox('Group by Activity Group', value=True)
st.sidebar.caption('Use filters to focus on specific activities or visits.')

st.sidebar.markdown('---')

# --- Main Content Area ---
if not output_files:
    st.warning('No SoA output files found. Please run the pipeline first.')
else:
    tab_titles = list(output_files.keys())
    tabs = st.tabs(tab_titles)
    
    for i, (fname, soa) in enumerate(output_files.items()):
        with tabs[i]:
            if 'error' in soa:
                st.error(f"Could not load or parse {fname}: {soa['error']}")
                continue

            st.header(f'Analysis of: {fname}')
            render_metadata(soa)
            st.markdown('---')
            st.subheader('Schedule of Activities Table')
            render_soa_table(soa, filter_activity=filter_activity, filter_timepoint=filter_timepoint, grouped=grouped, file_name=fname)
            with st.expander('Show Full JSON Output', expanded=False):
                st.json(soa, expanded=False)

# --- Configuration Files Section ---
st.sidebar.subheader('Configuration Files')
for fname, content in config_files.items():
    with st.sidebar.expander(f'{fname}', expanded=False):
        if isinstance(content, dict):
            st.json(content)
        else:
            st.text(content)
