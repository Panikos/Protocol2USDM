import os
import json
from dotenv import load_dotenv

# --- Optional imports (only if available) ---
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
openai_api_key = os.environ.get("OPENAI_API_KEY")
if OpenAI and openai_api_key:
    client = OpenAI(api_key=openai_api_key)
else:
    client = None

# The model name is now passed as a parameter to the main function.

LLM_PROMPT = (
    "You are an expert in clinical trial data curation and CDISC USDM v4.0 standards.\n"
    "You will be given two JSON objects, each representing a Schedule of Activities (SoA) extracted from a clinical trial protocol. Both are intended to conform to the USDM v4.0 Wrapper-Input OpenAPI schema.\n"
    "Compare and reconcile the two objects, resolving any discrepancies by using your best judgment and the USDM v4.0 standard.\n"
    "IMPORTANT: Output ALL column headers (timepoints) from the table EXACTLY as shown, including ranges (e.g., 'Day 2-3', 'Day 30-35'), even if they appear similar or redundant. Do NOT drop or merge any timepoints unless they are exact duplicates.\n"
    "When creating the `plannedTimepoints` array, you MUST standardize the `name` for each timepoint. If a timepoint has a simple `name` (e.g., 'Screening') and a more detailed `description` (e.g., 'Visit 1 / Week -2'), combine them into a single, user-friendly `name` in the format 'Visit X (Week Y)'. For example, a timepoint with `name: 'Screening'` and `description: 'Visit 1 / Week -2'` should be reconciled into a final timepoint with `name: 'Visit 1 (Week -2)'`. Preserve the original `description` field as well.\n"
    "CRITICAL: When reconciling the `activityTimepoints` (the matrix of checkmarks), you MUST prioritize the data from the VISION-EXTRACTED SoA. The vision model is more reliable for identifying which activities occur at which timepoints. If the vision JSON indicates a checkmark (`isPerformed: true`) for an activity at a timepoint, ensure it is present in the final output, even if the text JSON disagrees.\n"
    "Your output must be a single, unified JSON object that:\n"
    "- Strictly conforms to the USDM v4.0 Wrapper-Input schema (including the top-level keys: study, usdmVersion, systemName, systemVersion).\n"
    "- The study object must include all required and as many optional fields as possible, including a fully detailed SoA: activities, plannedTimepoints, activityGroups, activityTimepoints, and all appropriate groupings and relationships.\n"
    "- All objects must have their correct instanceType. Use unique IDs and preserve correct mappings.\n"
    "- The output must be ready for validation and for visualization in a SoA table viewer (with correct groupings, milestones, and 'ticks' as per the protocol template).\n"
    "Output ONLY valid JSON (no markdown, comments, or explanations)."
)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def reconcile_soa(vision_path, output_path, text_path, model_name='o3'):

    def standardize_ids_recursive(data):
        if isinstance(data, dict):
            return {k.replace('-', '_'): standardize_ids_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [standardize_ids_recursive(i) for i in data]
        else:
            return data

    def _merge_prov(dest: dict, src: dict) -> dict:
        """Recursively merge provenance dictionaries, preserving all tags."""
        for key, val in src.items():
            if isinstance(val, dict) and isinstance(dest.get(key), dict):
                for inner_id, inner_val in val.items():
                    existing_val = dest[key].get(inner_id)
                    if existing_val is None:
                        dest[key][inner_id] = inner_val
                    else:
                        existing_val_set = set(existing_val) if isinstance(existing_val, list) else {existing_val}
                        inner_val_set = set(inner_val) if isinstance(inner_val, list) else {inner_val}
                        merged = existing_val_set | inner_val_set
                        dest[key][inner_id] = sorted(list(merged))
            elif key not in dest or isinstance(dest.get(key), (type(None), str, int, float)):
                dest[key] = val
        return dest

    def _post_process_and_save(parsed_json, text_soa, vision_soa, output_path):
        """Applies all post-reconciliation fixes and saves the final JSON."""
        # 1. Deep merge provenance from all three sources.
        prov_merged = {}
        for source in (text_soa, vision_soa, parsed_json):
            if isinstance(source, dict) and 'p2uProvenance' in source:
                prov_merged = _merge_prov(prov_merged, source['p2uProvenance'])
        
        # 2. Standardize all keys in the merged provenance to snake_case.
        if prov_merged:
            parsed_json['p2uProvenance'] = standardize_ids_recursive(prov_merged)

        # 3. Inject missing but critical data from vision SoA as a fallback.
        try:
            parsed_tl = parsed_json.get('study', {}).get('versions', [{}])[0].get('timeline', {})
            vision_tl = vision_soa.get('study', {}).get('versions', [{}])[0].get('timeline', {})

            if vision_tl:
                # If LLM misses activityTimepoints, inject from vision to restore checkmarks.
                if not parsed_tl.get('activityTimepoints') and vision_tl.get('activityTimepoints'):
                    print("[INFO] Injecting missing 'activityTimepoints' from vision SoA.")
                    parsed_tl['activityTimepoints'] = vision_tl['activityTimepoints']
                
                # If LLM misses activityGroups, inject from vision.
                if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                    print("[INFO] Injecting missing 'activityGroups' from vision SoA.")
                    parsed_tl['activityGroups'] = vision_tl['activityGroups']
        except (KeyError, IndexError, AttributeError) as e:
            print(f"[WARNING] Could not perform fallback data injection: {e}")

        # 4. Carry over other top-level metadata keys if they are missing.
        for meta_key in ['p2uOrphans', 'p2uGroupConflicts', 'p2uTimelineOrderIssues']:
            if meta_key not in parsed_json:
                if meta_key in vision_soa:
                    parsed_json[meta_key] = vision_soa[meta_key]
                elif meta_key in text_soa:
                    parsed_json[meta_key] = text_soa[meta_key]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Reconciled and processed SoA written to {output_path}")

    # --- Main Execution Logic ---
    try:
        print(f"[INFO] Loading text-extracted SoA from: {text_path}")
        text_soa = load_json(text_path)
        print(f"[INFO] Loading vision-extracted SoA from: {vision_path}")
        vision_soa = load_json(vision_path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FATAL] Could not load or parse input SoA JSONs: {e}")
        raise

    user_content = (
        "TEXT-EXTRACTED SoA JSON:\n" + json.dumps(text_soa, ensure_ascii=False, indent=2) +
        "\nVISION-EXTRACTED SoA JSON:\n" + json.dumps(vision_soa, ensure_ascii=False, indent=2)
    )

    tried_models = []

    # Attempt 1: Gemini (if requested)
    if 'gemini' in model_name.lower():
        tried_models.append(model_name)
        try:
            print(f"[INFO] Attempting reconciliation with Gemini model: {model_name}")
            if not genai:
                raise ImportError("Gemini library not available.")
            genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
            gemini_client = genai.GenerativeModel(model_name)
            response = gemini_client.generate_content(
                [LLM_PROMPT, user_content],
                generation_config=genai.types.GenerationConfig(temperature=0.1, response_mime_type="application/json")
            )
            parsed = json.loads(response.text.strip())
            _post_process_and_save(parsed, text_soa, vision_soa, output_path)
            return
        except Exception as e:
            print(f"[WARNING] Gemini model '{model_name}' failed: {e}")

    # Attempt 2: OpenAI (if available and not already tried)
    if client and model_name not in tried_models:
        tried_models.append(model_name)
        try:
            print(f"[INFO] Attempting reconciliation with OpenAI model: {model_name}")
            messages = [{"role": "system", "content": LLM_PROMPT}, {"role": "user", "content": user_content}]
            response = client.chat.completions.create(model=model_name, messages=messages, max_tokens=16384, temperature=0.1)
            result = response.choices[0].message.content.strip()
            if result.startswith('```json'):
                result = result[7:-3].strip()
            parsed = json.loads(result)
            _post_process_and_save(parsed, text_soa, vision_soa, output_path)
            return
        except Exception as e:
            print(f"[WARNING] OpenAI model '{model_name}' failed: {e}")

    raise RuntimeError(f"Reconciliation failed with all attempted models: {', '.join(tried_models)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM-based reconciliation of SoA JSONs.")
    parser.add_argument("--text-input", required=True, help="Path to text-extracted SoA JSON.")
    parser.add_argument("--vision-input", required=True, help="Path to vision-extracted SoA JSON.")
    parser.add_argument("--output", required=True, help="Path to write reconciled SoA JSON.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'o3'), help="LLM model to use (e.g., 'o3', 'gpt-4o', or 'gemini-2.5-pro')")
    args = parser.parse_args()

    # Set the environment variable if it's not already set.
    # This ensures that if this script were to call another script, the model choice would propagate.
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = args.model
    print(f"[INFO] Using OpenAI model: {args.model}")

    reconcile_soa(vision_path=args.vision_input, output_path=args.output, text_path=args.text_input, model_name=args.model)
