import os
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from json_utils import clean_llm_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Ensure console can print UTF-8 (Windows default codepage causes logging errors)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
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
    fh = logging.FileHandler(log_file)
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

    system_msg = {
        "role": "system",
        "content": (
            "You are an expert medical writer specializing in authoring clinical trial protocols. "
            "Return ONLY a single valid JSON object that matches the USDM Wrapper-Input schema. "
            "Do NOT output any markdown, explanation, or additional text."
        ),
    }

    # Build user message: prompt text + each image as a base-64 data URL
    user_content = [{"type": "text", "text": usdm_prompt}]
    for img_path in image_paths:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": encode_image_to_data_url(img_path)},
            }
        )

    messages = [system_msg, {"role": "user", "content": user_content}]

    # Try strict JSON enforcement first; if the API refuses, fall back.
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.15,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(f"Retrying without response_format due to API error: {e}")
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.15,
                max_tokens=4096,
            )
        except Exception as e2:
            logger.error(f"OpenAI API error on second attempt: {e2}")
            return None
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None

    content = response.choices[0].message.content if response and response.choices else None
    if not content:
        logger.warning("Model returned empty content.")
        return None

    logger.debug(f"Raw LLM output: {content}")
    cleaned = clean_llm_json(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
        return None

def merge_soa_jsons(soa_parts):
    if not soa_parts:
        return None

    # Find the first valid base structure from the parts
    base_soa = None
    for part in soa_parts:
        if 'study' in part and 'versions' in part['study'] and part['study']['versions']:
            base_soa = part
            break
    
    if not base_soa:
        logger.error("No valid SoA structure found in any of the parts to merge.")
        return None

    # Use a deep copy to avoid modifying the original part
    import copy
    merged_soa = copy.deepcopy(base_soa)

    timepoints = {tp['id']: tp for tp in merged_soa['study']['versions'][0]['timeline'].get('plannedTimepoints', []) if tp.get('id')}
    activities = {act['id']: act for act in merged_soa['study']['versions'][0]['timeline'].get('activities', []) if act.get('id')}
    groups = {grp['id']: grp for grp in merged_soa['study']['versions'][0]['timeline'].get('activityGroups', []) if grp.get('id')}
    activity_timepoints = {f"{at.get('activityId')}-{at.get('plannedTimepointId')}": at for at in merged_soa['study']['versions'][0]['timeline'].get('activityTimepoints', []) if at.get('activityId') and at.get('plannedTimepointId')}

    for part in soa_parts:
        timeline = part.get('study', {}).get('versions', [{}])[0].get('timeline', {})
        
        for tp in timeline.get('plannedTimepoints', []):
            if tp.get('id') and tp['id'] not in timepoints:
                timepoints[tp['id']] = tp
        
        for act in timeline.get('activities', []):
            if act.get('id') and act['id'] not in activities:
                activities[act['id']] = act

        for grp in timeline.get('activityGroups', []):
            if grp.get('id') and grp['id'] not in groups:
                groups[grp['id']] = grp

        for at in timeline.get('activityTimepoints', []):
            key = f"{at.get('activityId')}-{at.get('plannedTimepointId')}"
            if key not in activity_timepoints:
                activity_timepoints[key] = at

    final_timeline = merged_soa['study']['versions'][0]['timeline']
    final_timeline['plannedTimepoints'] = list(timepoints.values())
    final_timeline['activities'] = list(activities.values())
    final_timeline['activityGroups'] = list(groups.values())
    final_timeline['activityTimepoints'] = list(activity_timepoints.values())
    
    # Ensure usdmVersion is set
    merged_soa['usdmVersion'] = base_soa.get('usdmVersion', '4.0.0')

    return merged_soa

def extract_and_merge_soa_from_images(image_paths, model_name, usdm_prompt, batch_size=None, max_workers=4):
    if batch_size is None:
        batch_size = len(image_paths)

    logger.info(f"Processing {len(image_paths)} images in batches of {batch_size} with {max_workers} workers.")

    all_batches = [image_paths[i:i + batch_size] for i in range(0, len(image_paths), batch_size)]
    all_soa_parts = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {executor.submit(extract_soa_from_image_batch, batch, model_name, usdm_prompt): batch for batch in all_batches}
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                result = future.result()
                if result:
                    logger.info(f"[SUCCESS] Extracted SoA from batch of {len(batch)} images.")
                    all_soa_parts.append(result)
                else:
                    logger.warning(f"[FAILURE] No JSON returned from batch of {len(batch)} images.")
            except Exception as exc:
                logger.error(f"Batch processing failed for batch of {len(batch)} images: {exc}")
    
    if not all_soa_parts:
        logger.fatal("Vision extraction failed for all batches. No valid JSON produced.")
        return None

    logger.info(f"Successfully extracted SoA data from {len(all_soa_parts)} batches. Merging...")
    merged_soa = merge_soa_jsons(all_soa_parts)
    return merged_soa

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("image_paths", nargs="+", help="List of image paths to process")
    parser.add_argument("--output", default="STEP2_soa_vision.json", help="Output JSON file")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use")
    parser.add_argument("--prompt-file", default="llm_soa_prompt.txt", help="Path to the LLM prompt file.")
    parser.add_argument("--batch-size", type=int, default=None, help="Optional: Number of images per batch (default: all)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker threads (default: 4)")
    args = parser.parse_args()

    try:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            usdm_prompt_text = f.read()
    except FileNotFoundError:
        print(f"[FATAL] Prompt file not found: {args.prompt_file}")
        sys.exit(1)
    
    final_soa_json = extract_and_merge_soa_from_images(
        args.image_paths,
        args.model,
        usdm_prompt_text,
        batch_size=args.batch_size,
        max_workers=args.workers,
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
    
    logger.info(f"Wrote merged SoA vision output to {args.output}")
