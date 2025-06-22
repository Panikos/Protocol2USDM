import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--model', default=os.environ.get('OPENAI_MODEL', 'o3'))
args, _ = parser.parse_known_args()
MODEL_NAME = args.model
if 'OPENAI_MODEL' not in os.environ:
    os.environ['OPENAI_MODEL'] = MODEL_NAME
print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

LLM_PROMPT = (
    "You are an expert in clinical trial data curation and CDISC USDM v4.0 standards.\n"
    "You will be given two JSON objects, each representing a Schedule of Activities (SoA) extracted from a clinical trial protocol. Both are intended to conform to the USDM v4.0 Wrapper-Input OpenAPI schema.\n"
    "Compare and reconcile the two objects, resolving any discrepancies by using your best judgment and the USDM v4.0 standard.\n"
    "IMPORTANT: Output ALL column headers (timepoints) from the table EXACTLY as shown, including ranges (e.g., 'Day 2-3', 'Day 30-35'), even if they appear similar or redundant. Do NOT drop or merge any timepoints unless they are exact duplicates.\n"
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

def reconcile_soa(text_path, vision_path, output_path):
    text_soa = load_json(text_path)
    vision_soa = load_json(vision_path)
    user_content = (
        "TEXT-EXTRACTED SoA JSON:\n" + json.dumps(text_soa, ensure_ascii=False, indent=2) +
        "\nVISION-EXTRACTED SoA JSON:\n" + json.dumps(vision_soa, ensure_ascii=False, indent=2)
    )
    messages = [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": user_content}
    ]
    # Model fallback logic (unchanged)
    model_order = [MODEL_NAME]
    # Only use models that are available to the user
    # Remove o3-mini-high if not available
    available_models = ['o3', 'gpt-4o']
    if MODEL_NAME == 'o3':
        model_order += ['gpt-4o']
    elif MODEL_NAME == 'gpt-4o':
        pass
    else:
        # fallback to gpt-4o if unknown model
        model_order += ['gpt-4o']
    tried = []
    for model_try in model_order:
        print(f"[INFO] Using OpenAI model: {model_try}")
        params = dict(model=model_try, messages=messages)
        if model_try == 'o3':
            params['max_completion_tokens'] = 90000
        else:
            params['max_tokens'] = 16384
        try:
            response = client.chat.completions.create(**params)
            result = response.choices[0].message.content
            # Clean up: remove code block markers, trailing text
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            last_brace = result.rfind('}')
            if last_brace != -1:
                result = result[:last_brace+1]
            parsed = json.loads(result)

            # --- NEW GROUPING-AWARE LOGIC ---
            # Validate and handle new structure: activityGroups, activities, visitGroups, visits, matrix
            activity_groups = parsed.get('activityGroups', [])
            activities = parsed.get('activities', [])
            visit_groups = parsed.get('visitGroups', [])
            visits = parsed.get('visits', [])
            matrix = parsed.get('matrix', [])

            # Validate group references
            ag_ids = {ag['id'] for ag in activity_groups}
            vg_ids = {vg['id'] for vg in visit_groups}
            for act in activities:
                if act.get('groupId') not in ag_ids and act.get('groupId') is not None:
                    print(f"[WARNING] Activity '{act['name']}' references missing activityGroupId: {act.get('groupId')}")
            for vis in visits:
                if vis.get('groupId') not in vg_ids and vis.get('groupId') is not None:
                    print(f"[WARNING] Visit '{vis['name']}' references missing visitGroupId: {vis.get('groupId')}")

            # Write out the reconciled SoA (grouping-aware)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] LLM-reconciled SoA written to {output_path}")
            return
        except Exception as e:
            err_msg = str(e)
            print(f"[WARNING] Model '{model_try}' failed: {err_msg}")
            tried.append(model_try)
            continue
    print(f"[FATAL] All model attempts failed: {tried}")
    raise RuntimeError(f"No available model succeeded: {tried}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM-based reconciliation of SoA JSONs.")
    parser.add_argument("--text", default="soa_text.json", help="Path to text-extracted SoA JSON")
    parser.add_argument("--vision", default="soa_vision.json", help="Path to vision-extracted SoA JSON")
    parser.add_argument("--output", default="STEP5_soa_final.json", help="Path to write reconciled SoA JSON")
    args = parser.parse_args()
    reconcile_soa(args.text, args.vision, args.output)
