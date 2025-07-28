import os
import sys
import argparse
import json
import io
from openai import OpenAI
import google.generativeai as genai
from p2u_constants import USDM_VERSION

# Ensure all output is UTF-8 safe for Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
import fitz  # PyMuPDF
from json_utils import clean_llm_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set up API clients from environment variables for security
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Configure the Gemini client
google_api_key = os.environ.get("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)


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

def send_text_to_llm(text, usdm_prompt, model_name):
    # This function now receives the fully-formed prompt.
    print(f"[DEBUG] Length of extracted PDF text: {len(text)}")
    print(f"[DEBUG] Length of prompt: {len(usdm_prompt)}")
    print(f"[DEBUG] Total prompt+text length: {len(usdm_prompt) + len(text)}")
    messages = [
        {"role": "system", "content": "You are an expert medical writer specializing in clinical trial protocols. When extracting text, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. Do NOT output any markdown, explanation, or additional text."},
        {"role": "user", "content": f"{usdm_prompt}\n\nHere is the protocol text to analyze:\n\n---\n\n{text}"}
    ]
    try:
        if 'gemini' in model_name.lower():
            print(f"[INFO] Using Google Gemini model: {model_name}")
            if not google_api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            model = genai.GenerativeModel(model_name)
            # Gemini uses a different message format
            full_prompt = f"{messages[0]['content']}\n\n{messages[1]['content']}"
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            result = response.text
        else:
            print(f"[INFO] Using OpenAI model: {model_name}")
            params = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"}
            }
            # The 'o3' model family does not support temperature=0.0.
            if model_name not in ['o3', 'o3-mini', 'o3-mini-high']:
                params["temperature"] = 0.0
            
            response = openai_client.chat.completions.create(**params)
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
                    def _alt(id_str: str) -> str | None:
                        m = re.match(r"(encounter|enc)[-_](\d+)", id_str)
                        if m:
                            full = f"encounter-{m.group(2)}"
                            short = f"enc_{m.group(2)}"
                            return short if id_str == full else full
                        m2 = re.match(r"epoch[-_](\d+)", id_str)
                        if m2:
                            return f"epoch_{m2.group(1)}" if '-' in id_str else f"epoch-{m2.group(1)}"
                        return None
                    # Ensure both the original ID and a possible alias (e.g. enc_1 ↔ encounter-1) map to the same canonical new ID
                    existing_map = id_maps[entity_type]
                    if old_id not in existing_map:
                        # Generate canonical new ID (singular entity prefix)
                        new_prefix = entity_type.replace('ies', 'y').rstrip('s')  # epochs → epoch, activities → activit…
                        new_id = f"{new_prefix}-{id_counters[entity_type]}"
                        id_counters[entity_type] += 1
                        existing_map[old_id] = new_id

                        alt = _alt(old_id)
                        if alt:
                            existing_map[alt] = new_id

                        all_entities[entity_type].append(entity)
                    else:
                        # We already assigned a new ID for this entity elsewhere – still register alias if needed
                        alt = _alt(old_id)
                        if alt and alt not in existing_map:
                            existing_map[alt] = existing_map[old_id]

    # --- PASS 2: Rewrite IDs and foreign keys in collected entities ---
    final_timeline = {entity_type: [] for entity_type in ENTITY_TYPES}

    for entity_type, entities in all_entities.items():
        for entity in entities:
            # Update the primary ID of the entity itself
            old_id = entity.get('id')
            if old_id in id_maps[entity_type]:
                entity['id'] = id_maps[entity_type][old_id]

            # Update foreign key references within the entity based on new schema
                        # Encounter -> Epoch and PlannedTimepoint
            if entity_type == 'encounters':
                # epochId reference
                fk_epoch = 'epochId'
                if fk_epoch in entity and entity.get(fk_epoch) in id_maps.get('epochs', {}):
                    entity[fk_epoch] = id_maps['epochs'][entity[fk_epoch]]
                # scheduledAtId (legacy naming)
                fk_sched = 'scheduledAtId'
                if fk_sched in entity and entity.get(fk_sched) in id_maps.get('plannedTimepoints', {}):
                    entity[fk_sched] = id_maps['plannedTimepoints'][entity[fk_sched]]
            
                        # PlannedTimepoint -> Encounter
            if entity_type == 'plannedTimepoints':
                fk_enc = 'encounterId'
                if fk_enc in entity and entity.get(fk_enc) in id_maps.get('encounters', {}):
                    entity[fk_enc] = id_maps['encounters'][entity[fk_enc]]

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
        
        # Create machine-readable header hints
        hints = {
            "timepoints": [
                {
                    "id": tp.get("id"),
                    "labelPrimary": tp.get("primary_name"),
                    "labelSecondary": tp.get("secondary_name")
                } for tp in structure_data.get("timepoints", [])
            ],
            "activityGroups": [
                {
                    "id": ag.get("id"),
                    "name": ag.get("group_name"),
                    "activities": ag.get("activities", [])
                } for ag in structure_data.get("activity_groups", [])
            ]
        }
        header_prompt_part = (
            "\n\nThe following JSON object (headerHints) describes the detected table structure. "
            "Use the information strictly to assign correct IDs and groupings. "
            "You may copy values but do NOT invent new IDs.\n" +
            "```json\n" + json.dumps({"headerHints": hints}, indent=2) + "\n```\n"
        )
        return base_prompt + header_prompt_part

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"[FATAL] Could not read or parse header structure file {header_structure_file}: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Extract SoA from a PDF using text-based LLM.")
    parser.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
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
        raw_output = send_text_to_llm(chunk, usdm_prompt, args.model)
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

    # Provenance tagging (text source)
    def _tag(container_key, items):
        cm = final_json.setdefault('p2uProvenance', {}).setdefault(container_key, {})
        for obj in items:
            if isinstance(obj, dict) and obj.get('id'):
                cm[obj['id']] = 'text'
    tl = final_json.get('study', {}).get('versions', [{}])[0].get('timeline', {}) if isinstance(final_json, dict) else {}
    _tag('plannedTimepoints', tl.get('plannedTimepoints', []))
    _tag('activities', tl.get('activities', []))
    _tag('encounters', tl.get('encounters', []))

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
