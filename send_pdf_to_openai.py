import os
import sys
import argparse
import json
from openai import OpenAI
from dotenv import load_dotenv
import fitz  # PyMuPDF
from json_utils import clean_llm_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set your OpenAI API key using environment variable for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

import argparse
parser = argparse.ArgumentParser(description="Extract SoA from PDF text with OpenAI")
parser.add_argument("pdf_path", help="Path to the protocol PDF")
parser.add_argument("--output", default="STEP1_soa_text.json", help="Output JSON file")
parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o"), help="OpenAI model")
args = parser.parse_args()
ALLOWED_MODELS = ['o3', 'o3-mini', 'gpt-4o']
if args.model not in ALLOWED_MODELS:
    print(f"[FATAL] Model '{args.model}' is not allowed. Choose from: {ALLOWED_MODELS}")
    sys.exit(1)
MODEL_NAME = args.model
if 'OPENAI_MODEL' not in os.environ:
    os.environ['OPENAI_MODEL'] = MODEL_NAME
print(f"[INFO] Using OpenAI model: {MODEL_NAME}")
print(f"[DEBUG] args.model={args.model}, env OPENAI_MODEL={os.environ.get('OPENAI_MODEL')}")

import re

def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def split_into_sections(text):
    # Try to split by section headers (e.g., numbered, all-caps, or 'Schedule of Activities')
    # Fallback: split by double newlines
    section_pattern = re.compile(r"(^\s*\d+\.\s+.+$|^[A-Z][A-Z\s\-]{6,}$|^Schedule of Activities.*$)", re.MULTILINE)
    matches = list(section_pattern.finditer(text))
    if not matches:
        # fallback: split by paragraphs
        return [s.strip() for s in text.split('\n\n') if s.strip()]
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return sections

def chunk_sections(sections, max_chars=75000):
    chunks = []
    current = []
    current_len = 0
    for sec in sections:
        if current_len + len(sec) > max_chars and current:
            chunks.append('\n\n'.join(current))
            current = [sec]
            current_len = len(sec)
        else:
            current.append(sec)
            current_len += len(sec)
    if current:
        chunks.append('\n\n'.join(current))
    return chunks

def send_text_to_openai(text):
    usdm_prompt = (
        "You are an expert in clinical trial protocol data modeling.\n"
        "Extract the Schedule of Activities (SoA) from the following protocol text and return it as a single JSON object conforming to the CDISC USDM v4.0 OpenAPI schema, specifically the Wrapper-Input object.\n"
        "\n"
        "REQUIREMENTS (STRICT):\n"
        "- For EVERY activity, explicitly assign an activityGroupId. If the activity belongs to Laboratory Tests, Health Outcome Instruments, or any other group, ensure the group is defined in activityGroups and referenced from the activity.\n"
        "- The activityGroups array MUST include definitions for all groups present in the SoA, including but not limited to Laboratory Tests, Health Outcome Instruments, Safety Assessments, Efficacy Assessments, etc.\n"
        "- Each activity must have a plannedTimepoints array listing all plannedTimepointIds where it occurs.\n"
        "- The timeline must include an explicit activityTimepoints array, where each entry maps an activityId to a plannedTimepointId. Create one entry for every tickmark/cell in the SoA table.\n"
        "- If a matrix or tickmark table is present, ensure all activity-timepoint mappings are captured in activityTimepoints.\n"
        "- Use table headers verbatim for timepoint labels.\n"
        "- Output ONLY valid JSON, with no explanations, comments, or markdown.\n"
        "- Include a 'table_headers' array for traceability.\n"
        "- If a group is not present, set the group id to null.\n"
        "- If the output is invalid, output as much as possible.\n"
        "\n"
        "The study object must include:\n"
        "- id: string (use protocol’s unique identifier).\n"
        "- name: string (full study name).\n"
        "- description: string or null.\n"
        "- label: string or null.\n"
        "- versions: array of StudyVersion-Input objects (at least one).\n"
        "- documentedBy: array (can be empty).\n"
        "- instanceType: string, must be 'Study'.\n"
        "\n"
        "Within each StudyVersion-Input object, include:\n"
        "- id: string (unique version ID).\n"
        "- versionIdentifier: string (e.g., protocol version).\n"
        "- rationale: string or null.\n"
        "- timeline: object, must include:\n"
        "    - plannedTimepoints: array of PlannedTimepoint-Input (each with unique id, name, instanceType, etc.).\n"
        "    - activities: array of Activity-Input (each with unique id, name, activityGroupId, plannedTimepoints, instanceType, etc.).\n"
        "    - activityGroups: array of ActivityGroup-Input (each with unique id, name, instanceType, etc.).\n"
        "    - activityTimepoints: array of ActivityTimepoint-Input (each mapping an activity to a timepoint: activityId + plannedTimepointId).\n"
        "- amendments: array (can be empty).\n"
        "- instanceType: string, must be 'StudyVersion'.\n"
        "\n"
        "For the Schedule of Activities:\n"
        "- plannedTimepoints: List all planned visits/timepoints (e.g., Screening, Baseline, Week 1, End of Study). Each must have id, name, and instanceType ('PlannedTimepoint').\n"
        "- activities: List all activities/procedures (e.g., Informed Consent, Blood Draw, ECG). Each must have id, name, activityGroupId, plannedTimepoints, and instanceType ('Activity').\n"
        "- activityGroups: If the protocol groups activities (e.g., Labs, Safety Assessments, Laboratory Tests, Health Outcome Instruments), define these here.\n"
        "- activityTimepoints: For each cell in the SoA table (i.e., each activity at each timepoint), create an object mapping the activity to the timepoint. Each must have activityId, plannedTimepointId, and instanceType ('ActivityTimepoint').\n"
        "- Use unique IDs for all entities.\n"
        "\n"
        "General Instructions:\n"
        "- Output ONLY valid JSON (no markdown, explanations, or comments).\n"
        "- If a required field is missing in the protocol, use null or an empty array as appropriate.\n"
        "- All objects must include their required instanceType property with the correct value.\n"
        "- Output must be fully USDM v4.0 compliant with grouping and tickmark mappings.\n"
        "- Follow the OpenAPI schema exactly for field names, types, and nesting.\n"
        "\n"
        "If you need the full field list for each object, refer to the OpenAPI schema.\n"
    )
    print(f"[DEBUG] Length of extracted PDF text: {len(text)}")
    print(f"[DEBUG] Length of prompt: {len(usdm_prompt)}")
    print(f"[DEBUG] Total prompt+text length: {len(usdm_prompt) + len(text)}")
    messages = [
        {"role": "system", "content": usdm_prompt},
        {"role": "user", "content": text}
    ]
    # Model fallback logic
    model_order = [MODEL_NAME]
    # Only add fallbacks if not overridden by CLI/env
    if MODEL_NAME == 'o3':
        model_order += ['o3-mini-high', 'gpt-4o']
    elif MODEL_NAME == 'o3-mini-high':
        model_order += ['gpt-4o']
    tried = []
    for model_try in model_order:
        print(f"[INFO] Using OpenAI model: {model_try}")
        params = dict(model=model_try, messages=messages)
        # Use 'max_completion_tokens' = 100000 for o3/o3-mini/o3-mini-high, and 'max_tokens' for gpt-4o/others
        if model_try in ['o3', 'o3-mini', 'o3-mini-high']:
            params['max_completion_tokens'] = 100000
        else:
            params['max_tokens'] = 16384
        try:
            response = client.chat.completions.create(**params)
            result = response.choices[0].message.content
            # Clean up: remove code block markers, trailing text
            if len(result) > 3800:
                print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
            print(f"[ACTUAL_MODEL_USED] {model_try}")
            return result
        except Exception as e:
            err_msg = str(e)
            print(f"[WARNING] Model '{model_try}' failed: {err_msg}")
            tried.append((model_try, err_msg))
            continue
    print(f"[FATAL] All model attempts failed: {', '.join([f'{model}: {err}' for model, err in tried])}")
    raise RuntimeError(f"No available model succeeded: {', '.join([f'{model}: {err}' for model, err in tried])}")

def clean_llm_json(raw):
    raw = raw.strip()
    if raw.startswith('```json'):
        raw = raw[7:]
    if raw.startswith('```'):
        raw = raw[3:]
    if raw.endswith('```'):
        raw = raw[:-3]
    last_brace = raw.rfind('}')
    if last_brace != -1:
        raw = raw[:last_brace + 1]
    return raw

def main():
    parser = argparse.ArgumentParser(description="Extract SoA from PDF text with OpenAI")
    parser.add_argument("pdf_path", help="Path to the protocol PDF")
    parser.add_argument("--output", default="STEP1_soa_text.json", help="Output JSON file")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o"), help="OpenAI model")
    args = parser.parse_args()
    ALLOWED_MODELS = ['o3', 'o3-mini', 'gpt-4o']
    if args.model not in ALLOWED_MODELS:
        print(f"[FATAL] Model '{args.model}' is not allowed. Choose from: {ALLOWED_MODELS}")
        sys.exit(1)
    MODEL_NAME = args.model
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = MODEL_NAME
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")
    print(f"[DEBUG] args.model={args.model}, env OPENAI_MODEL={os.environ.get('OPENAI_MODEL')}")

    pdf_path = args.pdf_path
    pdf_text = extract_pdf_text(pdf_path)
    sections = split_into_sections(pdf_text)
    chunks = chunk_sections(sections, max_chars=75000)
    print(f"[INFO] PDF split into {len(chunks)} chunks for LLM extraction.")

    all_versions = []
    all_timepoints = []
    all_activities = []
    all_groups = []
    all_atps = []
    wrapper_info = None
    study_id = None
    study_name = None

    for i, chunk in enumerate(chunks):
        print(f"[INFO] Sending chunk {i+1}/{len(chunks)} to LLM (length: {len(chunk)})...")
        parsed_content = send_text_to_openai(chunk)
        if not parsed_content or not parsed_content.strip().startswith(('{', '[')):
            print(f"[FATAL] LLM output for chunk {i+1} is empty or not valid JSON. Saving raw output to llm_raw_output_{i+1}.txt.")
            with open(f"llm_raw_output_{i+1}.txt", "w", encoding="utf-8") as f:
                f.write(parsed_content or "[EMPTY]")
            continue
        try:
            parsed_json = json.loads(parsed_content)
        except json.JSONDecodeError:
            cleaned = clean_llm_json(parsed_content)
            try:
                parsed_json = json.loads(cleaned)
            except json.JSONDecodeError:
                print(f"[FATAL] LLM output for chunk {i+1} could not be parsed as JSON. Saving raw and cleaned output.")
                with open(f"llm_raw_output_{i+1}.txt", "w", encoding="utf-8") as f:
                    f.write(parsed_content)
                with open(f"llm_cleaned_output_{i+1}.txt", "w", encoding="utf-8") as f:
                    f.write(cleaned)
                continue
        # Drill into the USDM structure
        if isinstance(parsed_json, dict):
            if not wrapper_info:
                # Save wrapper info from the first chunk
                wrapper_info = {k: parsed_json[k] for k in parsed_json if k not in ('study', 'Study')}
            study = parsed_json.get('study') or parsed_json.get('Study')
            if study:
                if not study_id:
                    study_id = study.get('id')
                if not study_name:
                    study_name = study.get('name')
                versions = study.get('versions') or study.get('studyVersions') or []
                if isinstance(versions, dict):
                    versions = [versions]
                for v in versions:
                    timeline = v.get('timeline') or v.get('studyDesign', {}).get('timeline') or {}
                    # Collect all entities
                    all_versions.append(v)
                    all_timepoints.extend(timeline.get('plannedTimepoints', []))
                    all_activities.extend(timeline.get('activities', []))
                    all_groups.extend(timeline.get('activityGroups', []))
                    all_atps.extend(timeline.get('activityTimepoints', []))

    # Deduplicate by id
    unique = lambda items, key: list({item.get(key): item for item in items if item.get(key)}.values())
    all_timepoints = unique(all_timepoints, 'id')
    all_activities = unique(all_activities, 'id')
    all_groups = unique(all_groups, 'id')
    all_atps = [dict(t) for t in {json.dumps(atp, sort_keys=True): atp for atp in all_atps}.values()]

    # Compose merged timeline
    merged_timeline = {
        'plannedTimepoints': all_timepoints,
        'activities': all_activities,
        'activityGroups': all_groups,
        'activityTimepoints': all_atps
    }
    # Compose merged version
    merged_version = {
        'id': study_id or 'merged_version',
        'versionIdentifier': 'Merged from LLM chunks',
        'instanceType': 'StudyVersion',
        'timeline': merged_timeline,
        'amendments': [],
    }
    # Compose merged study
    merged_study = {
        'id': study_id or 'merged_study',
        'name': study_name or 'Merged Study',
        'instanceType': 'Study',
        'versions': [merged_version],
        'documentedBy': [],
    }
    # Compose wrapper
    final_json = {
        'systemVersion': wrapper_info.get('systemVersion', '1.0') if wrapper_info else '1.0',
        'systemName': wrapper_info.get('systemName', 'Protocol2USDMv3') if wrapper_info else 'Protocol2USDMv3',
        'usdmVersion': wrapper_info.get('usdmVersion', '4.0') if wrapper_info else '4.0',
        'study': merged_study
    }

    with open('STEP1_soa_text.json', 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
    print('[SUCCESS] Merged SoA output from all LLM chunks written to STEP1_soa_text.json')

if __name__ == "__main__":
    main()
