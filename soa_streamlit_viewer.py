import streamlit as st
import json
import os
import glob
import pandas as pd  # for reading the M11 mapping workbook
import re
import html
from pathlib import Path
from datetime import datetime

# ============================================================================
# CUSTOM CSS FOR UX IMPROVEMENTS
# ============================================================================
CUSTOM_CSS = """
<style>
/* No data message styling */
.no-data-message {
    background-color: #f0f4f8;
    border: 2px dashed #94a3b8;
    border-radius: 12px;
    padding: 40px;
    text-align: center;
    color: #64748b;
    margin: 20px 0;
}
.no-data-message .icon {
    font-size: 48px;
    margin-bottom: 16px;
}
.no-data-message .title {
    font-size: 18px;
    font-weight: 600;
    color: #475569;
    margin-bottom: 8px;
}
.no-data-message .subtitle {
    font-size: 14px;
    color: #94a3b8;
}
</style>
"""

def render_no_data_message(section_name: str, hint: str = None):
    """Render a clear 'No Data' system message that cannot be confused with real data."""
    hint_html = f'<div class="subtitle">{hint}</div>' if hint else ''
    st.markdown(f'''
    <div class="no-data-message">
        <div class="icon">📭</div>
        <div class="title">No {section_name} Data Available</div>
        {hint_html}
    </div>
    ''', unsafe_allow_html=True)


# --- Data Access Functions --------------------------------------------------

def get_timeline(soa_content):
    """
    Safely retrieves schedule data from USDM content.
    Handles both legacy 'timeline' format and USDM v4.0 'studyDesigns' format.
    """
    if not isinstance(soa_content, dict):
        return None
    
    study = soa_content.get('study', {})
    if study and isinstance(study.get('versions'), list) and study['versions']:
        version = study['versions'][0]
        
        # USDM v4.0: Check studyDesigns first (preferred)
        study_designs = version.get('studyDesigns', [])
        if study_designs and isinstance(study_designs, list) and len(study_designs) > 0:
            sd = study_designs[0]
            # Return studyDesign as timeline-like object if it has SoA data
            if sd.get('activities') or sd.get('scheduleTimelines') or sd.get('encounters'):
                return sd
        
        # Legacy: Check timeline
        if version.get('timeline'):
            return version['timeline']
    
    # Top-level studyDesigns (some formats)
    if soa_content.get('studyDesigns'):
        sd = soa_content['studyDesigns'][0] if soa_content['studyDesigns'] else None
        if sd and (sd.get('activities') or sd.get('scheduleTimelines')):
            return sd
    
    # Fallback for flattened/reconciled format
    return soa_content.get('timeline')

def get_activity_timepoints(timeline):
    """
    Robustly extracts activity-timepoint links from a timeline or studyDesign object.
    Handles both legacy 'activityTimepoints' and USDM v4.0 'scheduleTimelines.instances'.
    """
    if not timeline:
        return {}
    
    activity_timepoints = {}
    
    # USDM v4.0: Check scheduleTimelines first
    schedule_timelines = timeline.get('scheduleTimelines', [])
    if schedule_timelines:
        for st in schedule_timelines:
            for instance in st.get('instances', []):
                if instance.get('instanceType') == 'ScheduledActivityInstance':
                    act_id = instance.get('activityId')
                    enc_id = instance.get('encounterId')
                    if act_id and enc_id:
                        activity_timepoints.setdefault(act_id, []).append(enc_id)
    
    # Legacy: Check activityTimepoints and scheduledActivityInstances
    for key in ['scheduledActivityInstances', 'activityTimepoints']:
        for link in timeline.get(key, []):
            if isinstance(link, dict):
                act_id = link.get('activityId')
                pt_id = link.get('plannedTimepointId') or link.get('encounterId')
                if act_id and pt_id:
                    activity_timepoints.setdefault(act_id, []).append(pt_id)

    return activity_timepoints

st.set_page_config(page_title="Protocol2USDM Viewer", layout="wide", page_icon="📊")

# Inject custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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
    
    # Entity counts - handle both legacy and USDM v4.0 structures
    metrics['visits'] = len(timeline.get('plannedTimepoints', timeline.get('encounters', [])))
    metrics['activities'] = len(timeline.get('activities', []))
    
    # Count activityTimepoints from multiple sources
    at_count = len(timeline.get('activityTimepoints', []))
    # Also count from scheduleTimelines if present
    for st in timeline.get('scheduleTimelines', []):
        at_count += len([i for i in st.get('instances', []) if i.get('instanceType') == 'ScheduledActivityInstance'])
    metrics['activityTimepoints'] = at_count
    
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

    # Handle both legacy and USDM v4.0 field names
    metrics_config = {
        'activities': ['description', 'childIds'],  # USDM v4.0 uses childIds instead of activityGroupId
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
    
    # USDM Expansion files (v6.1)
    expansion_map = {
        'protocol_usdm.json': ('full_usdm', 'Protocol USDM'),
        'full_usdm.json': ('full_usdm', 'Full Protocol USDM'),
        '2_study_metadata.json': ('metadata', 'Study Metadata'),
        '3_eligibility_criteria.json': ('eligibility', 'Eligibility Criteria'),
        '4_objectives_endpoints.json': ('objectives', 'Objectives & Endpoints'),
        '5_study_design.json': ('studydesign', 'Study Design'),
        '6_interventions.json': ('interventions', 'Interventions'),
        '7_narrative_structure.json': ('narrative', 'Narrative Structure'),
        '8_advanced_entities.json': ('advanced', 'Advanced Entities'),
        '9_procedures_devices.json': ('procedures', 'Procedures & Devices'),
        '10_scheduling_logic.json': ('scheduling', 'Scheduling Logic'),
        '11_sap_populations.json': ('sap', 'Analysis Populations (SAP)'),
        '12_study_sites.json': ('sites', 'Study Sites'),
        '13_document_structure.json': ('docstructure', 'Document Structure'),
        '14_amendment_details.json': ('amendmentdetails', 'Amendment Details'),
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
    
    # Store provenance path for later attachment (outside cache)
    possible_prov_files = [
        '9_final_soa_provenance.json',      # New pipeline
        '9_reconciled_soa_provenance.json', # Legacy pipeline
        'step6_provenance.json',            # Step-by-step test
    ]
    
    for prov_file in possible_prov_files:
        prov_path = os.path.join(base_path, prov_file)
        if os.path.exists(prov_path):
            inventory['provenance_path'] = prov_path
            break
    
    inventory['file_map'] = file_map
    return inventory


def attach_provenance_to_inventory(inventory):
    """Attach provenance data to inventory items (must be called outside cache)."""
    if not inventory or 'provenance_path' not in inventory:
        return
    
    prov_path = inventory['provenance_path']
    if not os.path.exists(prov_path):
        return
    
    prov_content, _ = load_file(prov_path)
    if not prov_content:
        return
    
    def attach_provenance(target_content, prov_data):
        """Convert and attach provenance data to target content."""
        if not isinstance(target_content, dict) or not prov_data or not isinstance(prov_data, dict):
            return
        # Convert provenance format if needed (new format has 'entities' and 'cells')
        if 'entities' in prov_data:
            # New format - merge entities into p2uProvenance format
            merged_prov = dict(prov_data.get('entities', {}))
            
            # Convert cells from flat "actId|ptId" -> nested {actId: {ptId: source}}
            cells = prov_data.get('cells', {})
            nested_cells = {}
            for key, source in cells.items():
                if '|' in key:
                    act_id, pt_id = key.split('|', 1)
                    if act_id not in nested_cells:
                        nested_cells[act_id] = {}
                    if pt_id:  # Only add if pt_id is not empty
                        nested_cells[act_id][pt_id] = source
            merged_prov['activityTimepoints'] = nested_cells
            target_content['p2uProvenance'] = merged_prov
        elif 'p2uProvenance' not in target_content:
            # Legacy format - use directly
            target_content['p2uProvenance'] = prov_data
    
    # Attach provenance to final_soa
    if inventory.get('final_soa'):
        attach_provenance(inventory['final_soa']['content'], prov_content)
    
    # Attach provenance to full_usdm (protocol_usdm.json)
    if inventory.get('full_usdm'):
        attach_provenance(inventory['full_usdm']['content'], prov_content)


def attach_footnotes_to_inventory(inventory):
    """Attach SoA footnotes from header structure to inventory items."""
    if not inventory:
        return
    
    # Get footnotes from header structure in intermediate_data
    header_structure = inventory.get('intermediate_data', {}).get('SoA Header Structure')
    if not header_structure or not isinstance(header_structure, dict):
        return
    
    footnotes = header_structure.get('footnotes', [])
    if not footnotes:
        return
    
    def attach_footnotes(target_content, fn_list):
        """Attach footnotes to target content if not already present."""
        if not isinstance(target_content, dict):
            return
        # Add footnotes at top level for fallback lookup
        if 'footnotes' not in target_content:
            target_content['footnotes'] = fn_list
    
    # Attach footnotes to final_soa
    if inventory.get('final_soa'):
        attach_footnotes(inventory['final_soa']['content'], footnotes)
    
    # Attach footnotes to full_usdm (protocol_usdm.json)
    if inventory.get('full_usdm'):
        attach_footnotes(inventory['full_usdm']['content'], footnotes)


def extract_soa_metadata(soa):
    if not isinstance(soa, dict):
        return {}
    usdm_version = soa.get('usdmVersion', 'N/A')
    
    # Use get_timeline() to handle both legacy and USDM v4.0 formats
    timeline = get_timeline(soa)

    if timeline:
        # Handle both plannedTimepoints (legacy) and encounters (USDM v4.0)
        num_timepoints = len(timeline.get('plannedTimepoints', timeline.get('encounters', [])))
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
    It checks for data in multiple possible locations for maximum compatibility.
    Handles both legacy 'timeline' format and USDM v4.0 'studyDesigns' format.
    """
    schedule_data = {}
    
    # Try 1: Standard USDM 4.0 path (study.versions[0].studyDesigns[0]) - PREFERRED
    if 'study' in data:
        try:
            study_design = data['study']['versions'][0]['studyDesigns'][0]
            if study_design.get('activities') or study_design.get('scheduleTimelines') or study_design.get('encounters'):
                schedule_data = study_design
        except (KeyError, IndexError, TypeError):
            pass
        
        # Try legacy timeline path if studyDesigns didn't have data
        if not schedule_data:
            try:
                timeline = data['study']['versions'][0]['timeline']
                if timeline and (timeline.get('activities') or timeline.get('activityTimepoints')):
                    schedule_data = timeline
            except (KeyError, IndexError, TypeError):
                pass
    
    # Try 2: Top-level studyDesigns (some formats)
    if not schedule_data and 'studyDesigns' in data and data['studyDesigns']:
        schedule_data = data['studyDesigns'][0]
    
    # If no schedule data found in any path
    if not schedule_data:
        return None
    
    # Extract plannedTimepoints - use encounters as fallback for USDM v4.0
    planned_timepoints = schedule_data.get('plannedTimepoints', [])
    
    # USDM v4.0: If no plannedTimepoints, create pseudo-timepoints from encounters
    # This allows the SoA grid to render using encounters as columns
    if not planned_timepoints and schedule_data.get('encounters'):
        planned_timepoints = [
            {
                'id': enc.get('id'),
                'name': enc.get('name', 'Unnamed'),
                'encounterId': enc.get('id'),  # Self-reference for compatibility
                'instanceType': 'PlannedTimepoint'
            }
            for enc in schedule_data.get('encounters', [])
        ]
            
    # Extract SoA footnotes from notes (CommentAnnotation objects)
    soa_footnotes = []
    for note in schedule_data.get('notes', []):
        if isinstance(note, dict) and note.get('text'):
            soa_footnotes.append(note['text'])
    
    # Use .get() for graceful extraction of each component
    return {
        'activities': schedule_data.get('activities', []),
        'activityGroups': schedule_data.get('activityGroups', []),
        'epochs': schedule_data.get('epochs', []),
        'encounters': schedule_data.get('encounters', []),
        'scheduleTimelines': schedule_data.get('scheduleTimelines', []),
        'plannedTimepoints': planned_timepoints,
        'activityTimepoints': schedule_data.get('activityTimepoints', []),
        'footnotes': soa_footnotes,
        '_raw_study_design': schedule_data,  # Keep raw for additional lookups
    }


def render_flexible_soa(data, table_id: str = "main", source_name: str = "SoA data"):
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

    # Pre-compute activity ⇢ plannedTimepoint/encounter links
    activity_pt_links = set()
    
    # Build a mapping from pt_* IDs to enc_* IDs (for ID mismatch handling)
    # The ScheduledActivityInstance may use pt_* IDs for encounterId
    pt_to_enc_map = {}
    for i, enc in enumerate(components['encounters']):
        pt_to_enc_map[f"pt_{i+1}"] = enc.get('id')  # Map pt_1 -> enc_1, etc.

    if components['scheduleTimelines'] and components['scheduleTimelines'][0].get('instances'):
        # USDM v4.0: Derive from ScheduledActivityInstance
        for inst in components['scheduleTimelines'][0].get('instances', []):
            if inst.get('instanceType') != 'ScheduledActivityInstance':
                continue
            
            # Get activity ID (handles both singular and plural)
            act_ids = inst.get('activityIds', [])
            if not act_ids and inst.get('activityId'):
                act_ids = [inst.get('activityId')]
            
            # Get encounter/timepoint ID and normalize to enc_* format
            enc_id = inst.get('encounterId')
            # Map pt_* to enc_* if needed
            if enc_id and enc_id.startswith('pt_'):
                enc_id = pt_to_enc_map.get(enc_id, enc_id)
            
            for act_id in act_ids:
                if act_id and enc_id:
                    activity_pt_links.add((act_id, enc_id))
    
    elif components['activityTimepoints']:
        # Legacy format
        for at in components['activityTimepoints']:
            if at.get('activityId') and at.get('plannedTimepointId'):
                activity_pt_links.add((at['activityId'], at['plannedTimepointId']))

    # populate DataFrame from USDM activity-timepoint links
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
        # Get cell-level provenance map (already converted to nested format during load)
        at_prov_map = provenance.get('activityTimepoints', {})
        
        tick_counts = {'text': 0, 'confirmed': 0, 'needs_review': 0, 'orphaned': 0}
        rows_with_review = set()
        
        # Build enc_* to pt_* mapping for provenance lookup
        # Provenance uses pt_* IDs but columns may use enc_* IDs
        enc_to_pt_map = {}
        for i, enc in enumerate(components['encounters']):
            enc_id = enc.get('id')
            if enc_id:
                enc_to_pt_map[enc_id] = f"pt_{i+1}"
        
        # Build set of timepoint IDs for lookup
        pt_id_map = {pt['id']: True for pt in ordered_pt_for_cols if pt.get('id')}
        
        if isinstance(at_prov_map, dict):
            for idx, activity in zip(row_index_data_display, ordered_activities_display):
                aid = activity.get('id')
                if not aid:
                    continue
                cell_map = at_prov_map.get(aid, {})
                if not isinstance(cell_map, dict):
                    cell_map = {}
                has_row_review = False
                
                # Count ticks that have provenance
                for pt_id, src in cell_map.items():
                    if src == 'text':
                        tick_counts['text'] += 1
                        has_row_review = True
                    elif src == 'both':
                        tick_counts['confirmed'] += 1
                    elif src in ('vision', 'needs_review'):
                        tick_counts['needs_review'] += 1
                        has_row_review = True
                
                # Check for orphaned ticks (X in matrix but no provenance)
                # Get row data from dataframe using iloc for positional access (handles duplicate column names)
                if idx in df.index:
                    row_idx_pos = df.index.get_loc(idx)
                    # Handle potential slice (from duplicate index labels)
                    if isinstance(row_idx_pos, slice):
                        row_idx_pos = row_idx_pos.start
                    row_data = df.iloc[row_idx_pos]
                    
                    for col_pos in range(len(df.columns)):
                        cell_value = row_data.iloc[col_pos]
                        if cell_value == 'X':
                            # Get timepoint ID by position (handles duplicate column names)
                            pt_id = ordered_pt_for_cols[col_pos].get('id') if col_pos < len(ordered_pt_for_cols) else None
                            # Map enc_* ID to pt_* ID for provenance lookup
                            prov_pt_id = enc_to_pt_map.get(pt_id, pt_id) if pt_id else None
                            if prov_pt_id and prov_pt_id not in cell_map:
                                tick_counts['orphaned'] += 1
                                has_row_review = True
                
                if has_row_review:
                    rows_with_review.add(idx)

        total_ticks = tick_counts['text'] + tick_counts['confirmed'] + tick_counts['needs_review'] + tick_counts['orphaned']
        has_validation = tick_counts['confirmed'] > 0 or tick_counts['needs_review'] > 0 or tick_counts['text'] > 0 or tick_counts['orphaned'] > 0

        if total_ticks:
            review_count = tick_counts['text'] + tick_counts['needs_review'] + tick_counts['orphaned']
            summary_text = (
                f"**Tick provenance:** {total_ticks} total - "
                f"{tick_counts['confirmed']} ✓ confirmed, "
                f"{review_count} ⚠️ need review "
                f"({tick_counts['text']} text-only, {tick_counts['needs_review']} vision-only, {tick_counts['orphaned']} orphaned)."
            )
            st.markdown(summary_text)

        if tick_counts['text'] > 0 or tick_counts['needs_review'] > 0 or tick_counts['orphaned'] > 0:
            review_msg = []
            if tick_counts['text'] > 0:
                review_msg.append(f"{tick_counts['text']} text-only (not confirmed by vision)")
            if tick_counts['needs_review'] > 0:
                review_msg.append(f"{tick_counts['needs_review']} vision-only (possible hallucinations)")
            if tick_counts['orphaned'] > 0:
                review_msg.append(f"{tick_counts['orphaned']} orphaned (no provenance data)")
            st.warning(f"⚠️ **Review needed:** " + "; ".join(review_msg))
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
        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #4ade80;"></div><span><strong>Green:</strong> Confirmed (text + vision agree)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #60a5fa;"></div><span><strong>Blue:</strong> Text-only (NOT confirmed by vision)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #fb923c;"></div><span><strong>Orange:</strong> Vision-only (possible hallucination, needs review)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 1rem; height: 1rem; margin-right: 0.5rem; border-radius: 0.25rem; background-color: #f87171;"></div><span><strong>Red:</strong> Orphaned (no provenance data)</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Build lookup dicts for faster ID resolution (row uses tuple->id, col uses position)
        row_to_act_id = {row_tuple: ordered_activities_display[i].get('id') 
                         for i, row_tuple in enumerate(row_index_data_display)}
        # Column lookup by position (handles duplicate column names)
        col_pos_to_pt_id = {i: pt_info.get('id') for i, pt_info in enumerate(ordered_pt_for_cols)}
        
        # Apply provenance styling
        def apply_provenance_style(row_pos, col_pos):
            """Apply provenance color to cells with 'X', preferring cell-level provenance when available."""
            try:
                # Use positional access to handle duplicate column names
                cell_value = df_display.iloc[row_pos, col_pos]
                
                if cell_value != 'X':
                    return ''
            except (KeyError, IndexError, ValueError):
                return ''
            
            # Get activity ID by row tuple, timepoint ID by column position
            row_tuple = df_display.index[row_pos]
            act_id = row_to_act_id.get(row_tuple)
            pt_id = col_pos_to_pt_id.get(col_pos)
            
            if not act_id or not pt_id:
                return ''
            
            # Map enc_* ID to pt_* ID for provenance lookup
            prov_pt_id = enc_to_pt_map.get(pt_id, pt_id)

            # 1) Prefer cell-level provenance if available (using the at_prov_map built earlier)
            if at_prov_map and isinstance(at_prov_map, dict):
                cell_src = at_prov_map.get(act_id, {}).get(prov_pt_id)
                if cell_src in ('needs_review', 'vision'):
                    return 'background-color: #fb923c'  # orange - needs review (includes vision-only)
                elif cell_src == 'both':
                    return 'background-color: #4ade80'  # green - confirmed
                elif cell_src == 'text':
                    return 'background-color: #60a5fa'  # blue - text (unvalidated)
            
            # 2) Fallback to entity-level provenance
            act_prov = get_provenance_sources(provenance, 'activities', act_id)
            pt_prov = get_provenance_sources(provenance, 'plannedTimepoints', prov_pt_id)
            
            from_text = act_prov['text'] or pt_prov['text']
            from_vision = act_prov['vision'] or pt_prov['vision']
            
            if from_text and from_vision:
                return 'background-color: #4ade80'  # green - both
            elif from_text:
                return 'background-color: #60a5fa'  # blue - text
            elif from_vision:
                return 'background-color: #fb923c'  # orange - vision-only
            
            # No provenance found - orphaned item, needs review
            return 'background-color: #f87171'  # red - orphaned (no provenance)
        
        # Build a style map with integer positions
        style_map = {}
        for i in range(len(df_display.index)):
            for j in range(len(df_display.columns)):
                style = apply_provenance_style(i, j)
                if style:
                    style_map[(i, j)] = style
        
        # Render HTML table with hierarchical headers and provenance colors
        html_parts = ['<style>']
        html_parts.append('.soa-table { border-collapse: collapse; width: 100%; font-size: 13px; }')
        html_parts.append('.soa-table th, .soa-table td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: center; white-space: normal; word-wrap: break-word; max-width: 120px; }')
        html_parts.append('.soa-table th { background-color: #f3f4f6; font-weight: 600; }')
        html_parts.append('.soa-table tbody tr:hover { background-color: #f9fafb; }')
        html_parts.append('</style>')
        html_parts.append('<div style="overflow-x: auto; max-height: 700px; overflow-y: auto;">')
        html_parts.append('<table class="soa-table">')
        
        # Build header rows
        has_groups = isinstance(df_display.index, pd.MultiIndex) and df_display.index.nlevels >= 2
        html_parts.append('<thead>')
        
        if isinstance(df.columns, pd.MultiIndex):
            level_values = [df.columns.get_level_values(i).tolist() for i in range(df.columns.nlevels)]
            # Check for duplicate levels
            skip_levels = set()
            if df.columns.nlevels >= 3 and level_values[1] == level_values[2]:
                skip_levels.add(2)
            
            active_levels = [i for i in range(df.columns.nlevels) if i not in skip_levels]
            num_header_rows = len(active_levels)
            level_names = ['Epoch', 'Visit', 'Day']
            
            for level_idx, level in enumerate(active_levels):
                html_parts.append('<tr>')
                if level_idx == 0:
                    if has_groups:
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #e5e7eb; min-width: 100px; position: sticky; left: 0; z-index: 2;">Category</th>')
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #e5e7eb; min-width: 150px; position: sticky; left: 100px; z-index: 2;">Activity</th>')
                    else:
                        html_parts.append(f'<th rowspan="{num_header_rows}" style="background-color: #e5e7eb;">Activity</th>')
                
                # Merged cells with colspan
                values = level_values[level]
                i = 0
                while i < len(values):
                    val = values[i]
                    colspan = 1
                    while i + colspan < len(values) and values[i + colspan] == val:
                        colspan += 1
                    
                    level_name = level_names[level] if level < len(level_names) else ''
                    style = 'background-color: #dbeafe; font-weight: bold;' if level == 0 else 'background-color: #f3f4f6;'
                    
                    # Show level name as prefix for first row only
                    display_val = html.escape(str(val)) if val else ''
                    
                    if colspan > 1:
                        html_parts.append(f'<th colspan="{colspan}" style="{style}">{display_val}</th>')
                    else:
                        html_parts.append(f'<th style="{style}">{display_val}</th>')
                    i += colspan
                html_parts.append('</tr>')
        else:
            html_parts.append('<tr>')
            if has_groups:
                html_parts.append('<th style="background-color: #e5e7eb;">Category</th>')
                html_parts.append('<th style="background-color: #e5e7eb;">Activity</th>')
            else:
                html_parts.append('<th style="background-color: #e5e7eb;">Activity</th>')
            for col in df.columns:
                html_parts.append(f'<th>{html.escape(str(col))}</th>')
            html_parts.append('</tr>')
        html_parts.append('</thead>')
        
        # Build body with rowspan grouping
        html_parts.append('<tbody>')
        group_spans = {}
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
                
                if group_name not in rendered_groups:
                    rendered_groups.add(group_name)
                    span = group_spans.get(group_name, {}).get('count', 1)
                    html_parts.append(
                        f'<th rowspan="{span}" style="background-color: #f3f4f6; font-weight: 600; '
                        f'text-align: left; vertical-align: top; border-right: 2px solid #9ca3af; '
                        f'position: sticky; left: 0; z-index: 1;">{html.escape(str(group_name))}</th>'
                    )
                
                html_parts.append(f'<th style="text-align: left; font-weight: normal; background-color: #fafafa; position: sticky; left: 100px; z-index: 1;">{html.escape(str(activity_name))}</th>')
            else:
                html_parts.append(f'<th style="text-align: left; background-color: #fafafa;">{html.escape(str(row_idx))}</th>')
            
            for j, (col_idx, value) in enumerate(row.items()):
                cell_style = style_map.get((i, j), '')
                style_attr = f' style="{cell_style}"' if cell_style else ''
                html_parts.append(f'<td{style_attr}>{html.escape(str(value))}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</tbody></table></div>')
        
        st.markdown(''.join(html_parts), unsafe_allow_html=True)
        
        # Display SoA footnotes if available
        footnotes = components.get('footnotes', [])
        # Fallback: check for footnotes in header structure data or provenance
        if not footnotes and 'footnotes' in data:
            footnotes = data.get('footnotes', [])
        if not footnotes and 'p2uProvenance' in data:
            prov_footnotes = data.get('p2uProvenance', {}).get('footnotes', [])
            if prov_footnotes:
                footnotes = prov_footnotes
        
        if footnotes:
            with st.expander(f"📝 Schedule of Activities Footnotes ({len(footnotes)})"):
                footnote_html = ['<div style="font-size: 0.9em; color: #374151; background-color: #f9fafb; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #3b82f6;">']
                for fn in footnotes:
                    footnote_html.append(f'<p style="margin: 0.5rem 0;">{html.escape(str(fn))}</p>')
                footnote_html.append('</div>')
                st.markdown(''.join(footnote_html), unsafe_allow_html=True)
        
        # Add interactive export option
        with st.expander("📥 Export & Search Data"):
            # Create flat export dataframe
            export_data = []
            for row_idx, row in df_display.iterrows():
                if isinstance(row_idx, tuple):
                    row_dict = {'Category': row_idx[0], 'Activity': row_idx[1]}
                else:
                    row_dict = {'Activity': row_idx}
                for col_idx, val in row.items():
                    col_name = ' | '.join(str(c) for c in col_idx) if isinstance(col_idx, tuple) else str(col_idx)
                    row_dict[col_name] = val
                export_data.append(row_dict)
            export_df = pd.DataFrame(export_data)
            
            # Search filter
            search = st.text_input("🔍 Search activities:", key=f"search_{table_id}")
            if search:
                mask = export_df.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)
                export_df = export_df[mask]
            
            st.dataframe(export_df, use_container_width=True, height=300)
            
            # CSV download
            csv = export_df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, f"soa_export_{table_id}.csv", "text/csv")
        
        # JSON viewer (collapsible)
        with st.expander(f"📄 Show JSON ({source_name})"):
            st.json(data, expanded=False)
    else:
        # No provenance - simple dataframe display
        st.dataframe(df_display, use_container_width=True, height=600)

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

# Add cache clear button
if st.sidebar.button("🔄 Refresh Data", help="Clear cached data and reload"):
    st.cache_data.clear()
    st.rerun()

if selected_run == "-- Select a Run --":
    st.info("Please select a pipeline run from the sidebar to begin.")
    st.stop()


run_path = os.path.join(OUTPUT_DIR, selected_run)
# Update header subtitle displaying the source PDF/protocol directory
file_placeholder.markdown(f"**SoA from:** `{selected_run}`")
inventory = get_file_inventory(run_path)

# Attach provenance data (must be done outside cached function)
attach_provenance_to_inventory(inventory)

# Attach footnotes from header structure (fallback if not in final output)
attach_footnotes_to_inventory(inventory)

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

# Use 9_final_soa.json for SoA display (has matching provenance)
# protocol_usdm.json has different activities from expansion phases
soa_source = None
soa_source_name = None

if inventory.get('final_soa') and inventory['final_soa'].get('content'):
    soa_source = inventory['final_soa']['content']
    soa_source_name = "9_final_soa.json"
elif inventory.get('full_usdm') and inventory['full_usdm'].get('content'):
    # Fallback to protocol_usdm.json if no SoA file
    soa_source = inventory['full_usdm']['content']
    soa_source_name = "protocol_usdm.json"

if not soa_source:
    render_no_data_message(
        "Schedule of Activities", 
        "Run the pipeline with a protocol PDF to extract the SoA table."
    )
else:
    st.info(f"📄 Source: **{soa_source_name}**")
    
    # Use the flexible renderer which handles missing entities gracefully
    render_flexible_soa(soa_source, table_id="final_soa", source_name=soa_source_name)

# --- USDM Expansion Data (v6.0) ---
if inventory.get('expansion') or inventory.get('full_usdm'):
    st.markdown("---")
    st.header("📋 Protocol Expansion Data (v6.0)")
    
    # Helper: Get data from protocol_usdm.json (preferred) or fallback to expansion files
    def get_expansion_data(key: str, full_usdm: dict, expansion_inv: dict):
        """Get expansion data, preferring protocol_usdm.json as source."""
        # Map of expansion keys to their location in protocol_usdm.json
        usdm_paths = {
            'eligibility': lambda u: {'eligibilityCriteria': u.get('studyDesigns', [{}])[0].get('eligibilityCriteria', []),
                                      'population': u.get('studyDesigns', [{}])[0].get('population') or u.get('studyDesigns', [{}])[0].get('studyDesignPopulation')},
            'objectives': lambda u: {'objectives': u.get('studyDesigns', [{}])[0].get('objectives', []),
                                     'endpoints': u.get('studyDesigns', [{}])[0].get('endpoints', [])},
            'studydesign': lambda u: {'arms': u.get('studyDesigns', [{}])[0].get('arms') or u.get('studyDesigns', [{}])[0].get('studyArms', []),
                                      'epochs': u.get('studyDesigns', [{}])[0].get('epochs', [])},
            'interventions': lambda u: {'studyInterventions': u.get('studyDesigns', [{}])[0].get('studyInterventions', []),
                                        'products': u.get('administrableProducts', [])},
            'narrative': lambda u: {'abbreviations': u.get('abbreviations', []),
                                    'narrativeContents': u.get('narrativeContents', [])},
            'advanced': lambda u: {'studyAmendments': u.get('studyAmendments', []),
                                   'countries': u.get('countries', [])},
            'procedures': lambda u: {'procedures': u.get('procedures', [])},
            'sap': lambda u: {'analysisPopulations': u.get('analysisPopulations', [])},
        }
        
        # Try to get from protocol_usdm.json first
        if full_usdm and key in usdm_paths:
            data = usdm_paths[key](full_usdm)
            # Check if data is non-empty
            has_data = any(v for v in data.values() if v)
            if has_data:
                return {'source': 'protocol_usdm.json', 'data': data, 'from_usdm': True}
        
        # Fallback to expansion files
        if expansion_inv and key in expansion_inv:
            return {'source': expansion_inv[key].get('display_name', key), 
                    'data': expansion_inv[key].get('content', {}), 
                    'from_usdm': False}
        
        return None
    
    full_usdm_content = inventory.get('full_usdm', {}).get('content', {})
    
    if inventory.get('full_usdm'):
        st.success("✅ Full USDM protocol available (`protocol_usdm.json`) - Data sourced from combined output")
    
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
        ('procedures', '🔬 Procedures'),
        ('scheduling', '⏱️ Scheduling'),
        ('sap', '📊 SAP'),
        ('sites', '🏥 Sites'),
        ('docstructure', '📑 Doc Structure'),
        ('amendmentdetails', '📝 Amendments'),
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
                            for t in md.get('titles', []):
                                title_text = t.get('text', 'N/A')
                                title_type = t.get('type', {})
                                type_label = title_type.get('decode', '') if isinstance(title_type, dict) else title_type
                                st.write(f"- [{type_label}] {title_text}")
                            st.markdown("**Study Phase:**")
                            phase = md.get('studyPhase', {})
                            phase_text = phase.get('code', phase.get('decode', 'N/A')) if isinstance(phase, dict) else phase
                            st.write(phase_text or 'N/A')
                        with col2:
                            st.markdown("**Identifiers:**")
                            for ident in md.get('identifiers', []):
                                st.write(f"- {ident.get('text', 'N/A')}")
                            st.markdown("**Indication:**")
                            for ind in md.get('indications', []):
                                st.write(f"- {ind.get('name', 'N/A')}")
                    else:
                        render_no_data_message("Study Metadata", "Run --metadata or --full-protocol to extract")
                
                elif key == 'eligibility':
                    st.subheader("Eligibility Criteria")
                    if content.get('success') and content.get('eligibility'):
                        elig = content['eligibility']
                        # Build lookup from criterionItemId -> text
                        items_map = {item.get('id'): item.get('text', item.get('name', 'N/A')) 
                                     for item in elig.get('eligibilityCriterionItems', [])}
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Inclusion Criteria ({elig.get('summary', {}).get('inclusionCount', 0)}):**")
                            for c in elig.get('eligibilityCriteria', []):
                                cat = c.get('category', {})
                                cat_code = cat.get('code', cat) if isinstance(cat, dict) else cat
                                if cat_code == 'Inclusion':
                                    text = items_map.get(c.get('criterionItemId'), c.get('name', 'N/A'))
                                    st.write(f"- [{c.get('identifier', '')}] {text[:100]}...")
                        with col2:
                            st.markdown(f"**Exclusion Criteria ({elig.get('summary', {}).get('exclusionCount', 0)}):**")
                            for c in elig.get('eligibilityCriteria', []):
                                cat = c.get('category', {})
                                cat_code = cat.get('code', cat) if isinstance(cat, dict) else cat
                                if cat_code == 'Exclusion':
                                    text = items_map.get(c.get('criterionItemId'), c.get('name', 'N/A'))
                                    st.write(f"- [{c.get('identifier', '')}] {text[:100]}...")
                    else:
                        render_no_data_message("Eligibility Criteria", "Run --eligibility or --full-protocol to extract")
                
                elif key == 'objectives':
                    st.subheader("Objectives & Endpoints")
                    if content.get('success') and content.get('objectivesEndpoints'):
                        obj = content['objectivesEndpoints']
                        summary = obj.get('summary', {})
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Primary", summary.get('primaryObjectives', 0))
                        col2.metric("Secondary", summary.get('secondaryObjectives', 0))
                        col3.metric("Exploratory", summary.get('exploratoryObjectives', 0))
                        col4.metric("Endpoints", summary.get('totalEndpoints', len(obj.get('endpoints', []))))
                        
                        st.markdown("**Objectives:**")
                        for o in obj.get('objectives', []):
                            level = o.get('level', {})
                            level_text = level.get('code', level) if isinstance(level, dict) else level
                            st.write(f"- [{level_text}] {o.get('text', 'N/A')[:100]}...")
                    else:
                        render_no_data_message("Objectives & Endpoints", "Run --objectives or --full-protocol to extract")
                
                elif key == 'studydesign':
                    st.subheader("Study Design Structure")
                    # Handle both 'studyDesign' and 'studyDesignStructure' keys
                    sd = content.get('studyDesignStructure') or content.get('studyDesign')
                    if content.get('success') and sd:
                        summary = sd.get('summary', {})
                        col1, col2, col3 = st.columns(3)
                        arms = sd.get('arms') or sd.get('studyArms', [])
                        col1.metric("Arms", summary.get('armCount', len(arms)))
                        col2.metric("Cohorts", summary.get('cohortCount', len(sd.get('studyCohorts', []))))
                        blinding = sd.get('blindingSchema', {})
                        blinding_text = blinding.get('code', 'N/A') if isinstance(blinding, dict) else blinding
                        col3.metric("Blinding", blinding_text or 'N/A')
                        
                        if arms:
                            st.markdown("**Study Arms:**")
                            for arm in arms:
                                desc = arm.get('description', 'N/A')
                                desc_text = desc[:80] + '...' if len(str(desc)) > 80 else desc
                                st.write(f"- {arm.get('name', 'N/A')}: {desc_text}")
                        
                        if sd.get('studyCohorts'):
                            st.markdown("**Study Cohorts:**")
                            for cohort in sd.get('studyCohorts', []):
                                desc = cohort.get('description', 'N/A')
                                desc_text = desc[:80] + '...' if len(str(desc)) > 80 else desc
                                st.write(f"- {cohort.get('name', 'N/A')}: {desc_text}")
                    else:
                        render_no_data_message("Study Design", "Run --studydesign or --full-protocol to extract")
                
                elif key == 'interventions':
                    st.subheader("Interventions & Products")
                    if content.get('success') and content.get('interventions'):
                        iv = content['interventions']
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Interventions", len(iv.get('studyInterventions', iv.get('interventions', []))))
                        col2.metric("Products", len(iv.get('investigationalProducts', iv.get('products', []))))
                        col3.metric("Regimens", len(iv.get('administrationRegimens', iv.get('administrations', []))))
                        
                        interventions_list = iv.get('studyInterventions', iv.get('interventions', []))
                        if interventions_list:
                            st.markdown("**Interventions:**")
                            for inter in interventions_list:
                                role = inter.get('role', {})
                                role_text = role.get('decode', role) if isinstance(role, dict) else role
                                st.write(f"- {inter.get('name', 'N/A')} ({role_text})")
                        
                        products_list = iv.get('investigationalProducts', iv.get('products', []))
                        if products_list:
                            st.markdown("**Products:**")
                            for prod in products_list:
                                st.write(f"- {prod.get('name', 'N/A')}: {prod.get('description', 'N/A')[:60]}...")
                        
                        regimens_list = iv.get('administrationRegimens', iv.get('administrations', []))
                        if regimens_list:
                            st.markdown("**Administration Regimens:**")
                            for reg in regimens_list:
                                dose = reg.get('dose', {})
                                dose_text = f"{dose.get('value', '')} {dose.get('unit', '')}" if isinstance(dose, dict) else str(dose)
                                route = reg.get('route', {})
                                route_text = route.get('decode', route) if isinstance(route, dict) else route
                                st.write(f"- {reg.get('name', 'N/A')}: {dose_text} ({route_text})")
                    else:
                        render_no_data_message("Interventions", "Run --interventions or --full-protocol to extract")
                
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
                    else:
                        render_no_data_message("Narrative Structure", "Run --narrative or --full-protocol to extract")
                
                elif key == 'advanced':
                    st.subheader("Advanced Entities")
                    if content.get('success') and content.get('advanced'):
                        adv = content['advanced']
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Amendments", len(adv.get('studyAmendments', [])))
                        col2.metric("Countries", len(adv.get('countries', [])))
                        col3.metric("Sites", len(adv.get('studySites', [])))
                        
                        amendments_list = adv.get('studyAmendments', [])
                        if amendments_list:
                            st.markdown("**Amendments:**")
                            for amend in amendments_list:
                                st.write(f"- Amendment {amend.get('number', 'N/A')}: {amend.get('summary', 'N/A')[:60]}...")
                        
                        countries_list = adv.get('countries', [])
                        if countries_list:
                            st.markdown("**Countries:**")
                            country_names = [c.get('name', c) if isinstance(c, dict) else str(c) for c in countries_list]
                            st.write(", ".join(country_names))
                        
                        sites_list = adv.get('studySites', [])
                        if sites_list:
                            st.markdown("**Study Sites:**")
                            for site in sites_list[:10]:  # Limit to first 10
                                st.write(f"- {site.get('name', 'N/A')}: {site.get('location', 'N/A')}")
                            if len(sites_list) > 10:
                                st.write(f"... and {len(sites_list) - 10} more sites")
                    else:
                        render_no_data_message("Advanced Entities", "Run --advanced or --full-protocol to extract")
                
                elif key == 'procedures':
                    st.subheader("🔬 Procedures & Devices")
                    proc_data = content.get('proceduresDevices', content)
                    if proc_data:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Procedures", len(proc_data.get('procedures', [])))
                        col2.metric("Medical Devices", len(proc_data.get('medicalDevices', [])))
                        col3.metric("Ingredients", len(proc_data.get('ingredients', [])))
                        
                        st.markdown("**Procedures:**")
                        for proc in proc_data.get('procedures', [])[:10]:
                            proc_type = proc.get('procedureType', {})
                            type_text = proc_type.get('decode', proc_type) if isinstance(proc_type, dict) else (proc_type or '')
                            st.write(f"- {proc.get('name', 'N/A')} ({type_text})")
                        
                        if proc_data.get('medicalDevices'):
                            st.markdown("**Medical Devices:**")
                            for dev in proc_data.get('medicalDevices', [])[:5]:
                                st.write(f"- {dev.get('name', 'N/A')} ({dev.get('manufacturer', 'N/A')})")
                        
                        if proc_data.get('ingredients'):
                            st.markdown("**Ingredients:**")
                            for ing in proc_data.get('ingredients', [])[:10]:
                                role = ing.get('role', {})
                                role_text = role.get('decode', role) if isinstance(role, dict) else (role or 'N/A')
                                st.write(f"- {ing.get('name', 'N/A')} ({role_text})")
                            if len(proc_data.get('ingredients', [])) > 10:
                                st.write(f"... and {len(proc_data.get('ingredients', [])) - 10} more ingredients")
                    else:
                        render_no_data_message("Procedures & Devices", "Run --procedures or --full-protocol to extract")
                
                elif key == 'scheduling':
                    st.subheader("⏱️ Scheduling Logic")
                    sched_data = content.get('scheduling', content)
                    if sched_data:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Timings", len(sched_data.get('timings', [])))
                        col2.metric("Conditions", len(sched_data.get('conditions', [])))
                        col3.metric("Transition Rules", len(sched_data.get('transitionRules', [])))
                        
                        if sched_data.get('timings'):
                            st.markdown("**Visit Timings:**")
                            for timing in sched_data.get('timings', [])[:8]:
                                window = ""
                                if timing.get('windowLower') is not None or timing.get('windowUpper') is not None:
                                    window = f" (window: {timing.get('windowLower', 0):+d}/{timing.get('windowUpper', 0):+d} {timing.get('unit', 'days')})"
                                st.write(f"- {timing.get('name', 'N/A')}: {timing.get('value', 'N/A')} {timing.get('unit', 'days')}{window}")
                        
                        if sched_data.get('conditions'):
                            st.markdown("**Conditions:**")
                            for cond in sched_data.get('conditions', [])[:8]:
                                cond_text = cond.get('text', cond.get('description', 'N/A'))
                                cond_text = cond_text[:80] + '...' if len(str(cond_text)) > 80 else cond_text
                                st.write(f"- {cond.get('name', 'N/A')}: {cond_text}")
                        
                        if sched_data.get('transitionRules'):
                            st.markdown("**Transition Rules:**")
                            for rule in sched_data.get('transitionRules', [])[:5]:
                                st.write(f"- {rule.get('name', 'N/A')}: {rule.get('text', rule.get('description', 'N/A'))[:80]}...")
                    else:
                        render_no_data_message("Scheduling Logic", "Run --scheduling or --full-protocol to extract")
                
                elif key == 'sap':
                    st.subheader("📊 Analysis Populations (SAP)")
                    sap_data = content.get('sapData', content)
                    if sap_data:
                        col1, col2 = st.columns(2)
                        col1.metric("Analysis Populations", len(sap_data.get('analysisPopulations', [])))
                        col2.metric("Baseline Characteristics", len(sap_data.get('characteristics', [])))
                        
                        st.markdown("**Analysis Populations:**")
                        for pop in sap_data.get('analysisPopulations', []):
                            st.write(f"- **{pop.get('label', pop.get('name', 'N/A'))}** ({pop.get('populationType', 'N/A')}): {pop.get('description', 'N/A')[:100]}...")
                        
                        st.markdown("**Baseline Characteristics:**")
                        char_names = [c.get('name', 'N/A') for c in sap_data.get('characteristics', [])[:15]]
                        st.write(", ".join(char_names))
                    else:
                        render_no_data_message("Analysis Populations", "Provide --sap <path> with a SAP document to extract")
                
                elif key == 'sites':
                    st.subheader("🏥 Study Sites")
                    sites_data = content.get('sitesData', content)
                    if sites_data:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Sites", len(sites_data.get('studySites', [])))
                        col2.metric("Roles", len(sites_data.get('studyRoles', [])))
                        col3.metric("Personnel", len(sites_data.get('assignedPersons', [])))
                        
                        st.markdown("**Study Sites:**")
                        for site in sites_data.get('studySites', [])[:10]:
                            st.write(f"- {site.get('siteNumber', 'N/A')}: {site.get('name', 'N/A')} ({site.get('country', 'N/A')}) - {site.get('status', 'Active')}")
                    else:
                        render_no_data_message("Study Sites", "Provide --sites <path> with a sites file to extract")
                
                elif key == 'docstructure':
                    st.subheader("📑 Document Structure")
                    doc_data = content.get('documentStructure', content)
                    if doc_data:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("References", len(doc_data.get('documentContentReferences', [])))
                        col2.metric("Annotations", len(doc_data.get('commentAnnotations', [])))
                        col3.metric("Versions", len(doc_data.get('studyDefinitionDocumentVersions', [])))
                        
                        if doc_data.get('documentContentReferences'):
                            st.markdown("**Document References:**")
                            for ref in doc_data.get('documentContentReferences', [])[:8]:
                                ref_type = ref.get('referenceType', {})
                                ref_type_text = ref_type.get('decode', ref_type) if isinstance(ref_type, dict) else (ref_type or 'N/A')
                                st.write(f"- {ref.get('name', 'N/A')} ({ref_type_text})")
                        
                        if doc_data.get('studyDefinitionDocumentVersions'):
                            st.markdown("**Document Versions:**")
                            for ver in doc_data.get('studyDefinitionDocumentVersions', []):
                                amend = f" ({ver.get('amendmentNumber', '')})" if ver.get('amendmentNumber') else ""
                                st.write(f"- Version {ver.get('versionNumber', 'N/A')}{amend} - {ver.get('status', 'N/A')} ({ver.get('versionDate', 'N/A')})")
                        
                        if doc_data.get('commentAnnotations'):
                            st.markdown("**Annotations/Footnotes:**")
                            for annot in doc_data.get('commentAnnotations', [])[:5]:
                                st.write(f"- [{annot.get('annotationType', 'Note')}] {annot.get('text', 'N/A')[:80]}...")
                    else:
                        render_no_data_message("Document Structure", "Run --docstructure or --full-protocol to extract")
                
                elif key == 'amendmentdetails':
                    st.subheader("📝 Amendment Details")
                    amend_data = content.get('amendmentDetails', content)
                    if amend_data:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Impacts", len(amend_data.get('studyAmendmentImpacts', [])))
                        col2.metric("Reasons", len(amend_data.get('studyAmendmentReasons', [])))
                        col3.metric("Changes", len(amend_data.get('studyChanges', [])))
                        
                        if amend_data.get('studyAmendmentImpacts'):
                            st.markdown("**Amendment Impacts:**")
                            for impact in amend_data.get('studyAmendmentImpacts', [])[:8]:
                                impact_type = impact.get('impactType', {})
                                impact_type_text = impact_type.get('decode', impact_type) if isinstance(impact_type, dict) else (impact_type or 'N/A')
                                desc = impact.get('description', 'N/A')
                                desc_text = desc[:60] + '...' if len(str(desc)) > 60 else desc
                                st.write(f"- [{impact_type_text}] {desc_text}")
                        
                        if amend_data.get('studyAmendmentReasons'):
                            st.markdown("**Amendment Reasons:**")
                            for reason in amend_data.get('studyAmendmentReasons', []):
                                primary = " ⭐" if reason.get('isPrimary') else ""
                                st.write(f"- [{reason.get('category', 'N/A')}]{primary} {reason.get('reasonText', 'N/A')[:80]}...")
                        
                        if amend_data.get('studyChanges'):
                            st.markdown("**Key Changes:**")
                            for change in amend_data.get('studyChanges', [])[:5]:
                                st.write(f"- [{change.get('changeType', 'Modification')}] {change.get('summary', change.get('sectionNumber', 'N/A'))[:60]}...")
                    else:
                        render_no_data_message("Amendment Details", "Run --amendmentdetails or --full-protocol to extract")
                
                with st.expander("Show Raw JSON"):
                    st.json(content)
    else:
        st.info("No expansion data found. Run `main_v2.py --full-protocol` to extract.")

# --- Debugging / Intermediate Files Section ---
st.markdown("--- ")
st.header("Intermediate Outputs & Debugging")

# Create tabs for intermediate files
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Text Extraction", 
    "Data Files", 
    "SoA Images",
    "Quality Metrics",
    "Validation & Conformance",
])

with tab1:
    st.subheader("Text Extraction Output")
    if not inventory['primary_outputs']:
        render_no_data_message("Text Extraction Output", "Run the pipeline to generate SoA extraction")
    else:
        for i, (key, content) in enumerate(inventory['primary_outputs'].items()):
            st.markdown(f"**{key}**")
            render_flexible_soa(content, table_id=f"primary_{i}")
            with st.expander("Show Raw JSON"):
                st.json(content)

with tab2:
    st.subheader("Intermediate Data Files")
    if not inventory['intermediate_data']:
        render_no_data_message("Intermediate Data Files", "Run the pipeline to generate intermediate outputs")
    else:
        for key, content in inventory['intermediate_data'].items():
            with st.expander(key):
                st.json(content if isinstance(content, dict) else str(content))

with tab3:
    st.subheader("Extracted SoA Images")
    if not inventory['images']:
        render_no_data_message("SoA Images", "SoA page images are extracted during pipeline execution")
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

with tab4:
    st.subheader("Quality Metrics")
    if not inventory['final_soa']:
        render_no_data_message("Quality Metrics", "Run the pipeline to generate a final SoA for quality analysis")
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

with tab5:
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
        
        # Check for enrichment report
        enrichment_file = output_dir / "terminology_enrichment.json"
        if enrichment_file.exists():
            with open(enrichment_file) as f:
                enrichment_result = json.load(f)
            
            enriched = enrichment_result.get('enriched', 0)
            total = enrichment_result.get('total_entities', 0)
            
            if enriched > 0:
                st.success(f"✅ Enriched {enriched}/{total} entities with NCI terminology codes")
                
                # Show summary by type
                by_type = enrichment_result.get('by_type', {})
                cols = st.columns(len(by_type) if by_type else 1)
                for i, (entity_type, count) in enumerate(sorted(by_type.items(), key=lambda x: -x[1])):
                    with cols[i % len(cols)]:
                        st.metric(entity_type, count)
                
                # Show enriched items in expander
                enriched_items = enrichment_result.get('enriched_items', [])
                if enriched_items:
                    with st.expander(f"View All {len(enriched_items)} Enriched Items"):
                        # Group by type
                        for entity_type in sorted(by_type.keys()):
                            items_of_type = [item for item in enriched_items if item.get('type') == entity_type]
                            if items_of_type:
                                st.markdown(f"**{entity_type}** ({len(items_of_type)})")
                                for item in items_of_type:
                                    name = item.get('name', 'Unknown')
                                    nci = item.get('nci_code', '')
                                    # Show additional context based on type
                                    extra = ''
                                    if item.get('level'):
                                        extra = f" [{item['level']}]"
                                    elif item.get('category'):
                                        extra = f" [{item['category']}]"
                                    elif item.get('arm_type'):
                                        extra = f" [{item['arm_type']}]"
                                    st.markdown(f"- {name}{extra} → `{nci}`")
                                st.markdown("")
                
                if enrichment_result.get('cache_stats'):
                    with st.expander("Cache Stats"):
                        stats = enrichment_result['cache_stats']
                        st.markdown(f"- Cached codes: {stats.get('total_entries', 0)}")
                        st.markdown(f"- Fresh entries: {stats.get('fresh_entries', 0)}")
            else:
                st.info("No entities required terminology enrichment.")
        else:
            st.info("Terminology enrichment not run. Use `--enrich` flag to enable.")
        
        st.markdown("---")
        
        # --- CDISC CORE Conformance ---
        st.markdown("### 🔬 CDISC CORE Conformance")
        # Check multiple possible filenames
        schema_file = None
        for fname in ["schema_validation.json", "usdm_validation.json", "step8_schema_validation.json"]:
            f = output_dir / fname
            if f.exists():
                schema_file = f
                break
        
        if schema_file and schema_file.exists():
            with open(schema_file) as f:
                schema_result = json.load(f)
            
            # Display validator type
            validator_type = schema_result.get('validator', 'unknown')
            validator_badge = "🔷 Official USDM Package" if "usdm" in validator_type else "🔶 OpenAPI Custom"
            
            if schema_result.get('valid'):
                st.success(f"✅ Schema validation PASSED ({validator_badge})")
            else:
                st.error(f"❌ Schema validation FAILED ({validator_badge})")
            
            # Show summary metrics
            summary = schema_result.get('summary', {})
            col1, col2 = st.columns(2)
            col1.metric("Errors", summary.get('errorsCount', summary.get('error_count', 0)))
            col2.metric("Warnings", summary.get('warningsCount', summary.get('warning_count', 0)))
            
            # Show issues
            issues = schema_result.get('issues', [])
            if issues:
                with st.expander(f"Validation Issues ({len(issues)})", expanded=not schema_result.get('valid')):
                    # Group by error type
                    by_type = {}
                    for issue in issues:
                        etype = issue.get('type', 'unknown') if isinstance(issue, dict) else 'unknown'
                        if etype not in by_type:
                            by_type[etype] = []
                        by_type[etype].append(issue)
                    
                    for etype, type_issues in sorted(by_type.items(), key=lambda x: -len(x[1])):
                        st.markdown(f"**{etype}** ({len(type_issues)}x)")
                        for issue in type_issues[:5]:  # Show first 5
                            if isinstance(issue, dict):
                                loc = issue.get('location', issue.get('path', ''))
                                msg = issue.get('message', '')
                                st.markdown(f"- `{loc}`: {msg[:80]}")
                            else:
                                st.markdown(f"- ❌ {issue}")
                        if len(type_issues) > 5:
                            st.caption(f"... and {len(type_issues) - 5} more")
            
            # Show fixer summary if available
            fixer = schema_result.get('fixerSummary')
            if fixer:
                with st.expander("Auto-Fixer Summary"):
                    st.markdown(f"- Original issues: {fixer.get('originalIssues', 0)}")
                    st.markdown(f"- Fixed issues: {fixer.get('fixedIssues', 0)}")
                    st.markdown(f"- Remaining issues: {fixer.get('remainingIssues', 0)}")
        else:
            st.info("Schema validation not run. Use `--validate-schema` or `--full` flag.")
