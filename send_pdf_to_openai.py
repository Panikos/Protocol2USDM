import os
import sys
import argparse
import json
import io
from openai import OpenAI
from p2u_constants import USDM_VERSION

# Ensure all output is UTF-8 safe for Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
import fitz  # PyMuPDF
from json_utils import clean_llm_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set your OpenAI API key using environment variable for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

import re

def extract_pdf_text(pdf_path, page_numbers=None):
    doc = fitz.open(pdf_path)
    text = ""
    # If page_numbers are specified, extract text only from those pages
    if page_numbers:
        for page_num in page_numbers:
            if 0 <= page_num < len(doc):
                text += doc[page_num].get_text()
    else:
        # Otherwise, extract text from all pages
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

def send_text_to_openai(text, usdm_prompt, model_name):
    # This function now receives the fully-formed prompt.
    print(f"[DEBUG] Length of extracted PDF text: {len(text)}")
    print(f"[DEBUG] Length of prompt: {len(usdm_prompt)}")
    print(f"[DEBUG] Total prompt+text length: {len(usdm_prompt) + len(text)}")
    messages = [
        {"role": "system", "content": "You are an expert medical writer specializing in clinical trial protocols. When extracting text, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. Do NOT output any markdown, explanation, or additional text."},
        {"role": "user", "content": f"{usdm_prompt}\n\nHere is the protocol text to analyze:\n\n---\n\n{text}"}
    ]
    try:
        print(f"[INFO] Using OpenAI model: {model_name}")
        params = {
            "model": model_name,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        # The 'o3' model family does not support temperature=0.0.
        if model_name not in ['o3', 'o3-mini', 'o3-mini-high']:
            params["temperature"] = 0.0
        
        response = client.chat.completions.create(**params)
        result = response.choices[0].message.content
        print(f"[DEBUG] Raw LLM output:\n{result}")
        print(f"[ACTUAL_MODEL_USED] {model_name}")
        return result
    except Exception as e:
        print(f"[FATAL] Model '{model_name}' failed: {e}")
        raise RuntimeError(f"Model '{model_name}' failed: {e}")

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
    """
    Merges multiple SoA JSON parts from chunked LLM calls into a single,
    valid USDM JSON object based on the v4.0.0 timeline structure.
    Handles re-indexing of all entity IDs to prevent collisions.
    """
    if not soa_parts:
        return None

    # Entity types as they appear in the LLM's timeline output
    ENTITY_TYPES = [
        'epochs',
        'encounters',
        'plannedTimepoints',
        'activities',
        'activityTimepoints',
        'activityGroups'
    ]

    # --- PASS 1: Collect all unique entities and create ID mappings ---
    id_maps = {entity_type: {} for entity_type in ENTITY_TYPES}
    all_entities = {entity_type: [] for entity_type in ENTITY_TYPES}
    id_counters = {entity_type: 1 for entity_type in ENTITY_TYPES}

    for part in soa_parts:
        # Check for the expected nested structure
        if not (
            'study' in part and
            'versions' in part['study'] and
            isinstance(part['study']['versions'], list) and
            len(part['study']['versions']) > 0 and
            'timeline' in part['study']['versions'][0]
        ):
            continue
        
        timeline = part['study']['versions'][0]['timeline']
        for entity_type in ENTITY_TYPES:
            if entity_type in timeline and isinstance(timeline[entity_type], list):
                for entity in timeline[entity_type]:
                    if not isinstance(entity, dict):
                        continue
                    old_id = entity.get('id')
                    if old_id is None:
                        continue

                    # Add entity if its ID hasn't been seen before
                    if old_id not in id_maps[entity_type]:
                        # Use a more descriptive new ID format
                        new_id = f"{entity_type.replace('ies', 'y').rstrip('s')}-{id_counters[entity_type]}"
                        id_maps[entity_type][old_id] = new_id
                        id_counters[entity_type] += 1
                        all_entities[entity_type].append(entity)

    # --- PASS 2: Rewrite IDs and foreign keys in collected entities ---
    final_timeline = {entity_type: [] for entity_type in ENTITY_TYPES}

    for entity_type, entities in all_entities.items():
        for entity in entities:
            # Update the primary ID of the entity itself
            old_id = entity.get('id')
            if old_id in id_maps[entity_type]:
                entity['id'] = id_maps[entity_type][old_id]

            # Update foreign key references within the entity based on new schema
            # Encounter -> PlannedTimepoint
            if entity_type == 'encounters':
                fk = 'scheduledAtId'
                if fk in entity and entity.get(fk) in id_maps.get('plannedTimepoints', {}):
                    entity[fk] = id_maps['plannedTimepoints'][entity[fk]]
            
            # ActivityTimepoint -> Activity and PlannedTimepoint
            if entity_type == 'activityTimepoints':
                fk_activity = 'activityId'
                if fk_activity in entity and entity.get(fk_activity) in id_maps.get('activities', {}):
                    entity[fk_activity] = id_maps['activities'][entity[fk_activity]]
                
                fk_timepoint = 'plannedTimepointId'
                if fk_timepoint in entity and entity.get(fk_timepoint) in id_maps.get('plannedTimepoints', {}):
                    entity[fk_timepoint] = id_maps['plannedTimepoints'][entity[fk_timepoint]]

            # ActivityGroup -> Activity
            if entity_type == 'activityGroups':
                if 'activities' in entity and isinstance(entity.get('activities'), list):
                    entity['activities'] = [id_maps.get('activities', {}).get(aid, aid) for aid in entity['activities']]

            final_timeline[entity_type].append(entity)

    # Construct the final merged JSON in the new timeline format
    final_json = {
        "study": {
            "versions": [
                {
                    "timeline": {key: val for key, val in final_timeline.items() if val}
                }
            ]
        },
        "usdmVersion": USDM_VERSION # Carry over version
    }

    return final_json

def get_llm_prompt(prompt_file, header_structure_file):
    # Base prompt is always loaded
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    except FileNotFoundError:
        print(f"[FATAL] Prompt file not found: {prompt_file}")
        raise

    # Dynamically add header and activity group structure info
    try:
        with open(header_structure_file, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)
        
        # Add timepoint header structure to the prompt
        header_prompt_part = "\n\nTo guide your extraction, here is the hierarchical structure of the table I have identified:\n"
        header_prompt_part += "\n--- TIMEPOINT COLUMN HEADERS ---\n"
        for tp in structure_data.get('timepoints', []):
            header_prompt_part += f"- Column '{tp.get('id')}' has a primary name of '{tp.get('primary_name')}'"
            if tp.get('secondary_name'):
                header_prompt_part += f" and a secondary name/date of '{tp.get('secondary_name')}'"
            header_prompt_part += '.\n'
        
        # Add activity group structure to the prompt
        header_prompt_part += "\n--- ACTIVITY ROW GROUPINGS ---\n"
        for ag in structure_data.get('activity_groups', []):
            header_prompt_part += f"- The group '{ag.get('group_name')}' contains the following activities: {', '.join(ag.get('activities', []))}\n"

        header_prompt_part += "\nPlease use this structural information to correctly interpret the table's columns, rows, and their relationships during your extraction. Ensure that the 'activityGroupId' in your output correctly references the groups identified here."
        return base_prompt + header_prompt_part

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"[FATAL] Could not read or parse header structure file {header_structure_file}: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Extract SoA from a PDF using text-based LLM.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("--output", required=True, help="Path to write the output JSON file.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use (e.g., 'gpt-4-turbo', 'gpt-4o').")
    parser.add_argument("--prompt-file", required=True, help="Path to the LLM prompt file.")
    parser.add_argument("--header-structure-file", required=True, help="Path to the header structure JSON file.")
    parser.add_argument("--soa-pages-file", required=False, help="Optional path to a JSON file containing a list of 0-based SoA page numbers. If not provided, the entire PDF will be processed.")
    args = parser.parse_args()

    MODEL_NAME = args.model
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = MODEL_NAME
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

    # Build the dynamic prompt
    usdm_prompt = get_llm_prompt(args.prompt_file, args.header_structure_file)

    page_numbers = None
    if args.soa_pages_file:
        try:
            with open(args.soa_pages_file, 'r') as f:
                data = json.load(f)
            page_numbers = data['soa_pages'] # These are 0-indexed
            print(f"[INFO] Extracting text from {len(page_numbers)} pages specified in {args.soa_pages_file}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"[FATAL] Could not read page numbers from {args.soa_pages_file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[INFO] No SoA pages file provided. Extracting text from the entire PDF.")

    pdf_text = extract_pdf_text(args.pdf_path, page_numbers=page_numbers)
    if not pdf_text:
        print("[FATAL] No text could be extracted from the specified pages.", file=sys.stderr)
        sys.exit(1)
        
    sections = split_into_sections(pdf_text)
    chunks = chunk_sections(sections)
    print(f"[INFO] Split text into {len(chunks)} chunks to send to LLM.")

    all_soa_parts = []
    for i, chunk in enumerate(chunks):
        print(f"[INFO] Sending chunk {i+1}/{len(chunks)} to LLM...")
        raw_output = send_text_to_openai(chunk, usdm_prompt, args.model)
        if not raw_output or not raw_output.strip().startswith(('{', '[')):
            print(f"[WARNING] LLM output for chunk {i+1} is empty or not valid JSON. Skipping.")
            continue
        try:
            # First try direct parsing
            parsed_json = json.loads(raw_output)
            study = parsed_json.get('study', {})
            if not study or ('versions' not in study and 'studyVersions' not in study):
                print(f"[WARNING] LLM output for chunk {i+1} is valid JSON but lacks SoA data (e.g., study.versions). Skipping.")
                continue
            all_soa_parts.append(parsed_json)
        except json.JSONDecodeError:
            # If direct parsing fails, try to clean it
            cleaned_json = clean_llm_json(raw_output)
            try:
                parsed_json = json.loads(cleaned_json)
                study = parsed_json.get('study', {})
                if not study or ('versions' not in study and 'studyVersions' not in study):
                    print(f"[WARNING] LLM output for chunk {i+1} is valid JSON but lacks SoA data (e.g., study.versions). Skipping.")
                    continue
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

    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[FATAL] Could not write output to {args.output}: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[SUCCESS] Merged SoA output from all LLM chunks written to {args.output}")

if __name__ == "__main__":
    main()
