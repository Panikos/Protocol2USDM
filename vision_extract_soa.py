import os
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import argparse
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
from json_utils import clean_llm_json
import io
from PIL import Image

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# API clients are initialized on-demand in the extraction function
openai_client = None
gemini_client = None

# Ensure console can print UTF-8 (Windows default codepage causes logging errors)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def setup_logger():
    """Return a logger that writes to console and timestamped log file."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"soa_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logger = logging.getLogger("SOA_Extractor")
    logger.setLevel(logging.DEBUG)

    # File handler (full debug)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    # Console handler (info+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Initialise logger early so all functions can use it
logger = setup_logger()

def encode_image_to_data_url(image_path: str) -> str:
    """Return base64 data URL string for image (PNG assumed)."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"

def extract_soa_from_image_batch(image_paths, model_name, usdm_prompt):
    """Send all images to the vision-capable chat model in a single request and
    return the parsed USDM JSON, or None on failure."""
    logger.info(f"Processing {len(image_paths)} images with model '{model_name}'.")

    if 'gemini' in model_name.lower():
        global gemini_client
        if not gemini_client:
            try:
                google_api_key = os.environ.get("GOOGLE_API_KEY")
                if not google_api_key:
                    raise ValueError("GOOGLE_API_KEY environment variable not set.")
                genai.configure(api_key=google_api_key)
                gemini_client = genai.GenerativeModel(model_name)
            except Exception as e:
                logger.error(f"Failed to configure Gemini client: {e}")
                return None

        try:
            # For Gemini, construct a list of content parts (system instruction, text prompt, then images)
            system_instruction = (
                "You are an expert medical writer specializing in authoring clinical trial protocols. "
                "Your task is to analyze the provided image(s) of a Schedule of Activities (SoA) table and extract its contents into a structured JSON format that strictly adheres to the provided USDM schema. "
                "CRITICAL: You MUST return ONLY a single, valid JSON object. Do not include any markdown formatting (like ```json), explanations, or any other text outside of the JSON object itself. "
                "Pay close attention to the provided header structure and schema definitions to ensure all entities and relationships are mapped correctly."
            )
            prompt_parts = [system_instruction, usdm_prompt]
            for img_path in image_paths:
                try:
                    img = Image.open(img_path)
                    # Convert to a format Gemini can use, like PNG bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    prompt_parts.append({'inline_data': {'mime_type': 'image/png', 'data': base64.b64encode(img_byte_arr).decode('utf-8')}})
                except Exception as e:
                    logger.error(f"Failed to process image {img_path}: {e}")
                    return None

            logger.info("Sending request to Gemini API...")
            response = gemini_client.generate_content(prompt_parts, generation_config=genai.types.GenerationConfig(
                temperature=0.15,
                response_mime_type="application/json"
            ))
            response_text = response.text
            return clean_llm_json(response_text)

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    else: # Assume OpenAI model
        global openai_client
        if not openai_client:
            try:
                openai_api_key = os.environ.get("OPENAI_API_KEY")
                if not openai_api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set.")
                openai_client = OpenAI(api_key=openai_api_key)
            except Exception as e:
                logger.error(f"Failed to configure OpenAI client: {e}")
                return None

        system_msg = {
            "role": "system",
            "content": (
                "You are an expert medical writer specializing in authoring clinical trial protocols. "
                "When extracting text from the image, you MUST ignore any single-letter footnote markers (e.g., a, b, c) that are appended to words. "
                "Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. "
                "To conserve space, use short but unique identifiers for all `id` fields (e.g., `act-1`, `tp-2`). "
                "Do NOT output any markdown, explanation, or additional text."
            ),
        }
        user_content = [{"type": "text", "text": usdm_prompt}]
        for img_path in image_paths:
            user_content.append({"type": "image_url", "image_url": {"url": encode_image_to_data_url(img_path)}})

        messages = [system_msg, {"role": "user", "content": user_content}]

        try:
            response = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.15,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning(f"Retrying without response_format due to API error: {e}")
            try:
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.15,
                    max_tokens=8192,
                )
            except Exception as e2:
                logger.error(f"OpenAI API error on second attempt: {e2}")
                return None
        
        try:
            response_text = response.choices[0].message.content
            return clean_llm_json(response_text)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            logger.debug(f"Raw response content:\n{response.choices[0].message.content if response.choices else 'No response content'}")
            return None

        logger.warning("Model returned empty content. Attempting fallback with minimal prompt.")
        logger.debug(f"Full response object: {response}")

        # Build a much shorter prompt that often bypasses safety filters
        minimal_prompt = (
            "Return ONLY a valid JSON object that conforms to the Wrapper-Input schema "
            "for the Schedule of Activities (SoA) found in the supplied image."
        )
        minimal_user_content = [
            {"type": "text", "text": minimal_prompt}
        ]
        for img_path in image_paths:
            minimal_user_content.append({
                "type": "image_url",
                "image_url": {"url": encode_image_to_data_url(img_path)},
            })

        minimal_messages = [system_msg, {"role": "user", "content": minimal_user_content}]

        try:
            response_retry = client.chat.completions.create(
                model=model_name,
                messages=minimal_messages,
                temperature=0.15,
                max_tokens=8192,
            )
            finish_reason_retry = response_retry.choices[0].finish_reason if response_retry and response_retry.choices else 'n/a'
            logger.info(f"[FALLBACK] finish_reason={finish_reason_retry}, usage={getattr(response_retry, 'usage', {})}")
            content_retry = response_retry.choices[0].message.content if response_retry and response_retry.choices else None
            if not content_retry:
                logger.warning("Fallback also returned empty content.")
                logger.debug(f"[FALLBACK] Full response object: {response_retry}")
                return None
            content = content_retry
        except Exception as e:
            logger.error(f"Fallback API call failed: {e}")
            return None

    logger.debug(f"Raw LLM output: {content}")
    cleaned = clean_llm_json(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
        return None

def repair_json_with_llm(broken_json_str):
    """Uses a lightweight LLM to repair a broken JSON string."""
    logger.info("Attempting to repair JSON with a second LLM call...")
    try:
        # Use a fast and cheap model for the repair task
        repair_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        repair_prompt = (
            "The following string is a malformed JSON object that was extracted from a document. "
            "Your task is to correct any syntax errors (e.g., missing commas, quotes, brackets) and return ONLY the valid, corrected JSON object. "
            "Do not include any explanation, markdown, or other text outside of the JSON object itself. Ensure the corrected output is a single, complete JSON object."
            f"\n\nMalformed JSON:```json\n{broken_json_str}\n```"
        )

        response = repair_model.generate_content(
            repair_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        repaired_json = json.loads(response.text)
        logger.info("[SUCCESS] JSON repaired and parsed successfully.")
        return repaired_json
    except Exception as e:
        logger.error(f"JSON repair failed: {e}")
        logger.debug(f"Original broken string that failed repair:\n{broken_json_str}")
        return None

def clean_llm_json(text_response):
    """Extract a JSON object from a text response that might include markdown."""
    # Find the start and end of the JSON object
    start_index = text_response.find('{')
    end_index = text_response.rfind('}')

    if start_index == -1 or end_index == -1:
        logger.warning("Could not find a JSON object in the response.")
        return None

    json_str = text_response[start_index : end_index + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # If initial parsing fails, try to repair it
        repaired_json = repair_json_with_llm(json_str)
        if repaired_json:
            return repaired_json
        else:
            # If repair fails, return the original broken string for robust handling
            return json_str

def merge_soa_jsons(soa_parts):
    if not soa_parts:
        return None

    import copy

    # Dictionaries to hold unique items by a meaningful key (name).
    unique_timepoints = {}
    unique_activities = {}
    # This will hold tuples of (activity_name, timepoint_name) to represent checkmarks
    unique_activity_timepoint_pairs = set()

    import re
    split_pattern = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
    # --- PASS 1: Collect all unique entities and relationships by NAME --- 
    for part in soa_parts:
        # Robustness check: ensure the part has the expected nested structure.
        if not isinstance(part, dict) or 'study' not in part or not isinstance(part.get('study'), dict) or 'versions' not in part['study'] or not part['study']['versions']:
            logger.warning(f"Skipping malformed SoA part: {str(part)[:200]}")
            continue

        timeline = part['study']['versions'][0].get('timeline', {})
        
        # Create local maps for this part's LLM-generated IDs to names
        part_activity_id_to_name = {a['id']: a['name'] for a in timeline.get('activities', []) if a.get('id') and a.get('name')}
        part_timepoint_id_to_name = {t['id']: t['name'] for t in timeline.get('plannedTimepoints', []) if t.get('id') and t.get('name')}

        # Collect unique activities and timepoints, keyed by name
        for act in timeline.get('activities', []):
            if act.get('name'):
                unique_activities[act['name']] = act
        
        for enc in timeline.get('encounters', []):
            # Split concatenated timing in name
            if isinstance(enc.get('name'), str):
                m = split_pattern.match(enc['name'])
                if m:
                    enc['name'] = m.group(1).strip()
                    timing_label = m.group(2).strip()
                    enc['timing'] = enc.get('timing') or {}
                    if 'windowLabel' not in enc['timing']:
                        enc['timing']['windowLabel'] = timing_label
            enc_name = enc.get('name') or enc.get('label')
            unique_activities[enc_name] = enc

        for tp in timeline.get('plannedTimepoints', []):
            # Split concatenated label if needed ("Visit 1 (Week -2)")
            if isinstance(tp.get('name'), str):
                m = split_pattern.match(tp['name'])
                if m:
                    tp['name'] = m.group(1).strip()
                    if not tp.get('description'):
                        tp['description'] = m.group(2).strip()
            tp_name = tp.get('name') or tp.get('label')
            unique_timepoints[tp['name']] = tp

        # Collect unique (activity, timepoint) checkmark pairs using names
        for at in timeline.get('activityTimepoints', []):
            act_id = at.get('activityId')
            tp_id = at.get('plannedTimepointId')
            if act_id in part_activity_id_to_name and tp_id in part_timepoint_id_to_name:
                act_name = part_activity_id_to_name[act_id]
                tp_name = part_timepoint_id_to_name[tp_id]
                unique_activity_timepoint_pairs.add((act_name, tp_name))

    # --- PASS 2: Build the final, merged_soa JSON with new, consistent IDs --- #

    # Find a base structure to copy metadata from (e.g., usdmVersion)
    # Find a base structure, ensuring it has the correct nested dictionary structure.
    base_soa = next((p for p in soa_parts if isinstance(p, dict) and 'study' in p and isinstance(p.get('study'), dict) and p['study'].get('versions')), None)
    if not base_soa:
        logger.error("No valid SoA structure found in any of the parts to merge.")
        return None
        
    final_soa = copy.deepcopy(base_soa)
    final_timeline = final_soa['study']['versions'][0]['timeline']
    
    # Re-index activities and create a name -> new_id map
    final_activities = []
    activity_name_to_new_id = {}
    for i, (name, act_data) in enumerate(unique_activities.items()):
        new_id = f"act{i+1}"
        act_data['id'] = new_id
        final_activities.append(act_data)
        activity_name_to_new_id[name] = new_id
        
    # Re-index timepoints and create a name -> new_id map
    final_timepoints = []
    timepoint_name_to_new_id = {}
    for i, (name, tp_data) in enumerate(unique_timepoints.items()):
        new_id = f"tp{i+1}"
        tp_data['id'] = new_id
        final_timepoints.append(tp_data)
        timepoint_name_to_new_id[name] = new_id

    # Build final activityTimepoints (the checkmarks) using the new, consistent IDs
    final_activity_timepoints = []
    for act_name, tp_name in unique_activity_timepoint_pairs:
        if act_name in activity_name_to_new_id and tp_name in timepoint_name_to_new_id:
            final_activity_timepoints.append({
                "activityId": activity_name_to_new_id[act_name],
                "plannedTimepointId": timepoint_name_to_new_id[tp_name]
            })

    # Populate the final timeline, ensuring a consistent order
    final_timeline['activities'] = sorted(final_activities, key=lambda x: int(x['id'][3:]))
    final_timeline['plannedTimepoints'] = sorted(final_timepoints, key=lambda x: int(x['id'][2:]))
    final_timeline['activityTimepoints'] = final_activity_timepoints
    final_timeline['activityGroups'] = [] # Not currently handled

    return final_soa

def extract_and_merge_soa_from_images(image_paths, model_name, usdm_prompt):
    all_soa_parts = []
    # Process images one by one to get separate JSON outputs
    for image_path in image_paths:
        logger.info(f"Processing image: {image_path}")
        # We use the batch extractor but with a single image
        result = extract_soa_from_image_batch([image_path], model_name, usdm_prompt)
        if result:
            logger.info(f"[SUCCESS] Extracted SoA from {image_path}.")
            all_soa_parts.append(result)
        else:
            logger.warning(f"[FAILURE] No JSON returned from {image_path}.")

    if not all_soa_parts:
        logger.fatal("Vision extraction failed for all images. No valid JSON produced.")
        return None

    logger.info(f"Successfully extracted SoA data from {len(all_soa_parts)} images. Merging...")
    merged_soa = merge_soa_jsons(all_soa_parts)
    # Tag provenance for downstream auditing
    prov_map = merged_soa.setdefault('p2uProvenance', {}) if isinstance(merged_soa, dict) else {}
    def _tag(container_key, items):
        if not isinstance(merged_soa, dict):
            return
        cm = prov_map.setdefault(container_key, {})
        for obj in items:
            if isinstance(obj, dict) and obj.get('id'):
                cm[obj['id']] = 'vision'
    tl = merged_soa.get('study', {}).get('versions', [{}])[0].get('timeline', {}) if isinstance(merged_soa, dict) else {}
    _tag('plannedTimepoints', tl.get('plannedTimepoints', []))
    _tag('activities', tl.get('activities', []))
    _tag('encounters', tl.get('encounters', []))
    return merged_soa

def get_llm_prompt(prompt_file=None, header_structure_file=None):
    base_prompt = ''
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    else:
        # Fallback to a default prompt if file doesn't exist
        base_prompt = 'You are an expert in clinical trial protocols. Extract the Schedule of Activities (SoA) from this image in USDM v4.0 format.'

    if header_structure_file and os.path.exists(header_structure_file):
        try:
            with open(header_structure_file, 'r', encoding='utf-8') as f:
                structure_data = json.load(f)

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
        except Exception as e:
            print(f"[WARN] Could not read or parse header structure file {header_structure_file}: {e}")

    return base_prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("--images-dir", required=True, help="Directory containing the SoA image files.")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use.")
    parser.add_argument("--prompt-file", required=True, help="Path to the LLM prompt file.")
    parser.add_argument("--header-structure-file", required=True, help="Path to the header structure JSON file.")

    args = parser.parse_args()

    try:
        image_paths_to_process = sorted([
            os.path.join(args.images_dir, f)
            for f in os.listdir(args.images_dir)
            if f.lower().endswith('.png')
        ])
        if not image_paths_to_process:
            logger.error(f"No PNG images found in {args.images_dir}")
            sys.exit(1)
    except FileNotFoundError:
        logger.error(f"Images directory not found: {args.images_dir}")
        sys.exit(1)

    usdm_prompt = get_llm_prompt(args.prompt_file, args.header_structure_file)

    final_soa_json = extract_and_merge_soa_from_images(
        image_paths_to_process,
        args.model,
        usdm_prompt,
    )

    if not final_soa_json:
        logger.fatal("Vision extraction failed because no valid JSON could be produced.")
        sys.exit(1)

    # The final_soa_json from merging should already be in the correct Wrapper-Input format.
    # We just need to ensure the study object and its keys are robust.
    if 'study' not in final_soa_json:
        final_soa_json['study'] = {} # Should not happen with new merge logic, but safe.
    
    # Ensure attributes and relationships keys exist in the study object
    if 'attributes' not in final_soa_json['study']:
        final_soa_json['study']['attributes'] = {}
    if 'relationships' not in final_soa_json['study']:
        final_soa_json['study']['relationships'] = {}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_soa_json, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Wrote merged_soa SoA vision output to {args.output}")
