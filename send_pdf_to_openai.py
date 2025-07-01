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
parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o"), help="OpenAI model (e.g., gpt-4o, gpt-3.5-turbo)")
args = parser.parse_args()
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
        "Extract the Schedule of Activities (SoA) from the protocol text and return a single JSON object conforming to the CDISC USDM v4.0 OpenAPI schema.\n"
        "\n"
        "REQUIREMENTS (STRICT):\n"
        "- The root of the JSON object MUST be a Wrapper-Input object.\n"
        "- The JSON object MUST have a top-level 'study' object and a 'usdmVersion' key set to '4.0.0'.\n"
        "- For EVERY activity, explicitly assign an 'activityGroupId'. If an activity belongs to a category (e.g., 'Laboratory Tests'), define that category in 'activityGroups' and reference its ID.\n"
        "- The 'activityGroups' array MUST include definitions for all categories present in the SoA.\n"
        "- The 'timeline' must include an 'activityTimepoints' array, where each entry maps an 'activityId' to a 'plannedTimepointId', representing every tickmark in the SoA table.\n"
        "- Use table headers verbatim for timepoint labels.\n"
        "- Output ONLY valid JSON. Do not include explanations, comments, or markdown.\n"
        "\n"
        "EXAMPLE WRAPPER STRUCTURE:\n"
        "{\n"
        "  \"usdmVersion\": \"4.0.0\",\n"
        "  \"study\": {\n"
        "    \"id\": \"<study_id>\",\n"
        "    \"name\": \"<study_name>\",\n"
        "    \"versions\": [\n"
        "      {\n"
        "        \"timeline\": { ... }\n"
        "      }\n"
        "    ]\n"
        "  }\n"
        "}\n"
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
    try:
        print(f"[INFO] Using OpenAI model: {MODEL_NAME}")
        params = {
            "model": MODEL_NAME,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        # The 'o3' model family does not support temperature=0.0.
        if MODEL_NAME not in ['o3', 'o3-mini', 'o3-mini-high']:
            params["temperature"] = 0.0
        
        response = client.chat.completions.create(**params)
        result = response.choices[0].message.content
        print(f"[ACTUAL_MODEL_USED] {MODEL_NAME}")
        return result
    except Exception as e:
        print(f"[FATAL] Model '{MODEL_NAME}' failed: {e}")
        raise RuntimeError(f"Model '{MODEL_NAME}' failed: {e}")

def clean_llm_json(raw):
    # Remove markdown code block fences
    cleaned = re.sub(r"^```json\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)
    # Remove leading/trailing whitespace that might affect parsing
    cleaned = cleaned.strip()
    # Attempt to fix trailing commas in objects and arrays
    cleaned = re.sub(r",(\s*[]}])", r"\1", cleaned)
    return cleaned

def merge_soa_jsons(soa_parts):
    if not soa_parts:
        return None

    base_soa = None
    for part in soa_parts:
        if 'study' in part and 'versions' in part['study'] and part['study']['versions']:
            base_soa = part
            break
    
    if not base_soa:
        print("[ERROR] No valid SoA structure found in any of the parts to merge.")
        return None

    import copy
    merged_soa = copy.deepcopy(base_soa)

    timeline = merged_soa['study']['versions'][0]['timeline']
    timepoints = {tp['id']: tp for tp in timeline.get('plannedTimepoints', []) if tp.get('id')}
    activities = {act['id']: act for act in timeline.get('activities', []) if act.get('id')}
    groups = {grp['id']: grp for grp in timeline.get('activityGroups', []) if grp.get('id')}
    activity_timepoints = {f"{at.get('activityId')}-{at.get('plannedTimepointId')}": at for at in timeline.get('activityTimepoints', []) if at.get('activityId') and at.get('plannedTimepointId')}

    for part in soa_parts:
        part_timeline = part.get('study', {}).get('versions', [{}])[0].get('timeline', {})
        
        for tp in part_timeline.get('plannedTimepoints', []):
            if tp.get('id') and tp['id'] not in timepoints:
                timepoints[tp['id']] = tp
        
        for act in part_timeline.get('activities', []):
            if act.get('id') and act['id'] not in activities:
                activities[act['id']] = act

        for grp in part_timeline.get('activityGroups', []):
            if grp.get('id') and grp['id'] not in groups:
                groups[grp['id']] = grp

        for at in part_timeline.get('activityTimepoints', []):
            key = f"{at.get('activityId')}-{at.get('plannedTimepointId')}"
            if key not in activity_timepoints:
                activity_timepoints[key] = at

    timeline['plannedTimepoints'] = list(timepoints.values())
    timeline['activities'] = list(activities.values())
    timeline['activityGroups'] = list(groups.values())
    timeline['activityTimepoints'] = list(activity_timepoints.values())
    
    merged_soa['usdmVersion'] = base_soa.get('usdmVersion', '4.0.0')

    return merged_soa

def main():
    parser = argparse.ArgumentParser(description="Extract SoA from PDF text with OpenAI")
    parser.add_argument("pdf_path", help="Path to the protocol PDF")
    parser.add_argument("--output", default="STEP1_soa_text.json", help="Output JSON file")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o"), help="OpenAI model (e.g., gpt-4o, gpt-3.5-turbo)")
    args = parser.parse_args()
    MODEL_NAME = args.model
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = MODEL_NAME
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")
    print(f"[DEBUG] args.model={args.model}, env OPENAI_MODEL={os.environ.get('OPENAI_MODEL')}")

    pdf_path = args.pdf_path
    pdf_text = extract_pdf_text(pdf_path)
    sections = split_into_sections(pdf_text)
    chunks = chunk_sections(sections)
    print(f"[INFO] Split text into {len(chunks)} chunks to send to LLM.")

    all_soa_parts = []
    for i, chunk in enumerate(chunks):
        print(f"[INFO] Sending chunk {i+1}/{len(chunks)} to LLM...")
        raw_output = send_text_to_openai(chunk)
        if not raw_output or not raw_output.strip().startswith(('{', '[')):
            print(f"[WARNING] LLM output for chunk {i+1} is empty or not valid JSON. Skipping.")
            continue
        try:
            # First try direct parsing
            parsed_json = json.loads(raw_output)
            all_soa_parts.append(parsed_json)
        except json.JSONDecodeError:
            # If direct parsing fails, try to clean it
            cleaned_json = clean_llm_json(raw_output)
            try:
                parsed_json = json.loads(cleaned_json)
                all_soa_parts.append(parsed_json)
            except json.JSONDecodeError:
                print(f"[ERROR] Failed to parse JSON from chunk {i+1} even after cleaning. Skipping.")

    if not all_soa_parts:
        print("[FATAL] No valid SoA JSON could be extracted from any text chunk.")
        sys.exit(1)

    print(f"[INFO] Successfully extracted SoA data from {len(all_soa_parts)} chunks. Merging...")
    final_json = merge_soa_jsons(all_soa_parts)

    if not final_json:
        print("[FATAL] Merging of SoA chunks failed.")
        sys.exit(1)

    # Ensure the final study object has the required keys for validation
    if 'study' in final_json and 'attributes' not in final_json['study']:
        final_json['study']['attributes'] = {}
    if 'study' in final_json and 'relationships' not in final_json['study']:
        final_json['study']['relationships'] = {}

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
    
    print(f"[SUCCESS] Merged SoA output from all LLM chunks written to {args.output}")

if __name__ == "__main__":
    main()
