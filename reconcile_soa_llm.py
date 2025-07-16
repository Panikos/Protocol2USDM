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
    try:
        print(f"[INFO] Loading text-extracted SoA from: {text_path}")
        text_soa = load_json(text_path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FATAL] Could not load or parse text SoA from {text_path}: {e}")
        raise

    try:
        print(f"[INFO] Loading vision-extracted SoA from: {vision_path}")
        vision_soa = load_json(vision_path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FATAL] Could not load or parse vision SoA from {vision_path}: {e}")
        raise

    # If we have both, proceed with LLM-based reconciliation.
    is_gemini_requested = 'gemini' in model_name.lower()
    print("[INFO] Both text and vision SoA found. Reconciling with LLM...")
    user_content = (
        "TEXT-EXTRACTED SoA JSON:\n" + json.dumps(text_soa, ensure_ascii=False, indent=2) +
        "\nVISION-EXTRACTED SoA JSON:\n" + json.dumps(vision_soa, ensure_ascii=False, indent=2)
    )
    messages = [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": user_content}
    ]
    # -------------------- GEMINI PRIMARY PATH --------------------
    if is_gemini_requested:
        if not (genai and os.environ.get('GOOGLE_API_KEY')):
            raise RuntimeError("Gemini model requested but google.generativeai not available or GOOGLE_API_KEY not set.")
        try:
            print(f"[INFO] Using Gemini model: {model_name} for reconciliation…")
            genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
            gemini_client = genai.GenerativeModel(model_name)
            gemini_prompt = LLM_PROMPT + "\n\n" + user_content + "\nReturn ONLY the final reconciled JSON."
            response = gemini_client.generate_content([
                gemini_prompt
            ], generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            ))
            result = response.text.strip()
            parsed = json.loads(result)
            # Ensure required StudyVersion fields
            if isinstance(parsed, dict):
                versions = parsed.get('study', {}).get('versions', [])
                for version in versions:
                    version.setdefault('rationale', 'Not specified')
                    version.setdefault('studyIdentifiers', [])
                    version.setdefault('titles', [])
                # --- Preserve wrapper-level provenance & QC metadata ---
                # Deep merge provenance dictionaries so nested maps (e.g., plannedTimepoints, activities) are combined
                def _merge_prov(dest: dict, src: dict) -> dict:
                    """Recursively merge provenance dictionaries, preserving all tags."""
                    for key, val in src.items():
                        if isinstance(val, dict) and isinstance(dest.get(key), dict):
                            # Merge inner dicts of IDs -> provenance tags
                            for inner_id, inner_val in val.items():
                                existing_val = dest[key].get(inner_id)
                                if existing_val is None:
                                    dest[key][inner_id] = inner_val
                                else:
                                    # Normalise to sets then union
                                    if not isinstance(existing_val, (list, set)):
                                        existing_val_set = {existing_val}
                                    else:
                                        existing_val_set = set(existing_val)
                                    if not isinstance(inner_val, (list, set)):
                                        inner_val_set = {inner_val}
                                    else:
                                        inner_val_set = set(inner_val)
                                    merged = existing_val_set | inner_val_set
                                    dest[key][inner_id] = sorted(merged) if len(merged) > 1 else next(iter(merged))
                        else:
                            # For scalar or list at top level, prefer union if both are list-like
                            if key in dest and isinstance(val, (list, set)) and isinstance(dest[key], (list, set)):
                                dest[key] = sorted(set(dest[key]) | set(val))
                            else:
                                dest[key] = val
                    return dest

                prov_merged: dict = {}
                for _src in (text_soa, vision_soa, parsed):
                    if isinstance(_src, dict):
                        _prov = _src.get('p2uProvenance')
                        if isinstance(_prov, dict):
                            prov_merged = _merge_prov(prov_merged, _prov)
                if prov_merged:
                    parsed['p2uProvenance'] = prov_merged

                # Ensure activityGroups are not lost during reconciliation.
                try:
                    parsed_tl = parsed.get('study', {}).get('versions', [])[0].get('timeline', {})
                    vision_tl = vision_soa.get('study', {}).get('versions', [])[0].get('timeline', {}) if isinstance(vision_soa, dict) else {}
                    if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                        parsed_tl['activityGroups'] = vision_tl['activityGroups']
                except Exception:
                    pass
                for _meta_key in (
                    'p2uProvenance',
                    'p2uOrphans',
                    'p2uGroupConflicts',
                    'p2uTimelineOrderIssues',
                ):
                    if _meta_key not in parsed:
                        if _meta_key in vision_soa:
                            parsed[_meta_key] = vision_soa[_meta_key]
                        elif _meta_key in text_soa:
                            parsed[_meta_key] = text_soa[_meta_key]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] Gemini-reconciled SoA written to {output_path}")
            return
        except Exception as ge:
            print(f"[WARNING] Gemini reconciliation failed: {ge}. Falling back to OpenAI if available…")
            # fall through to OpenAI logic if available

    # -------------------- OPENAI PRIMARY PATH (default) --------------------
    # Model fallback logic (OpenAI first, then Gemini) if Gemini wasn't explicitly requested.
    model_order = [model_name]
    # Only use models that are available to the user
    # Remove o3-mini-high if not available
    available_models = ['o3', 'gpt-4o']  # OpenAI models
    if model_name == 'o3':
        model_order += ['gpt-4o']
    elif model_name == 'gpt-4o':
        pass
    else:
        # fallback to gpt-4o if unknown model
        model_order += ['gpt-4o']
    tried = []
    # --- Try OpenAI first if available ---
    for model_try in model_order if client else []:
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
            # Ensure required StudyVersion fields
            if isinstance(parsed, dict):
                versions = parsed.get('study', {}).get('versions', [])
                for version in versions:
                    version.setdefault('rationale', 'Not specified')
                    version.setdefault('studyIdentifiers', [])
                    version.setdefault('titles', [])
                # --- Preserve wrapper-level provenance & QC metadata ---
                # Deep merge provenance dictionaries so nested maps (e.g., plannedTimepoints, activities) are combined
                def _merge_prov(dest: dict, src: dict) -> dict:
                    """Recursively merge provenance dictionaries, preserving all tags."""
                    for key, val in src.items():
                        if isinstance(val, dict) and isinstance(dest.get(key), dict):
                            # Merge inner dicts of IDs -> provenance tags
                            for inner_id, inner_val in val.items():
                                existing_val = dest[key].get(inner_id)
                                if existing_val is None:
                                    dest[key][inner_id] = inner_val
                                else:
                                    # Normalise to sets then union
                                    if not isinstance(existing_val, (list, set)):
                                        existing_val_set = {existing_val}
                                    else:
                                        existing_val_set = set(existing_val)
                                    if not isinstance(inner_val, (list, set)):
                                        inner_val_set = {inner_val}
                                    else:
                                        inner_val_set = set(inner_val)
                                    merged = existing_val_set | inner_val_set
                                    dest[key][inner_id] = sorted(merged) if len(merged) > 1 else next(iter(merged))
                        else:
                            # For scalar or list at top level, prefer union if both are list-like
                            if key in dest and isinstance(val, (list, set)) and isinstance(dest[key], (list, set)):
                                dest[key] = sorted(set(dest[key]) | set(val))
                            else:
                                dest[key] = val
                    return dest

                prov_merged: dict = {}
                for _src in (text_soa, vision_soa, parsed):
                    if isinstance(_src, dict):
                        _prov = _src.get('p2uProvenance')
                        if isinstance(_prov, dict):
                            prov_merged = _merge_prov(prov_merged, _prov)
                if prov_merged:
                    parsed['p2uProvenance'] = prov_merged

                # Ensure activityGroups are not lost during reconciliation.
                try:
                    parsed_tl = parsed.get('study', {}).get('versions', [])[0].get('timeline', {})
                    vision_tl = vision_soa.get('study', {}).get('versions', [])[0].get('timeline', {}) if isinstance(vision_soa, dict) else {}
                    if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                        parsed_tl['activityGroups'] = vision_tl['activityGroups']
                except Exception:
                    pass
                for _meta_key in (
                    'p2uProvenance',
                    'p2uOrphans',
                    'p2uGroupConflicts',
                    'p2uTimelineOrderIssues',
                ):
                    if _meta_key not in parsed:
                        if _meta_key in vision_soa:
                            parsed[_meta_key] = vision_soa[_meta_key]
                        elif _meta_key in text_soa:
                            parsed[_meta_key] = text_soa[_meta_key]

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

            # --- Ensure required StudyVersion fields are present ---
            if isinstance(parsed, dict):
                versions = parsed.get('study', {}).get('versions', [])
                for version in versions:
                    version.setdefault('rationale', 'Not specified')
                    version.setdefault('studyIdentifiers', [])
                    version.setdefault('titles', [])
                # --- Preserve wrapper-level provenance & QC metadata ---
                # Deep merge provenance dictionaries so nested maps (e.g., plannedTimepoints, activities) are combined
                def _merge_prov(dest: dict, src: dict) -> dict:
                    """Recursively merge provenance dictionaries, preserving all tags."""
                    for key, val in src.items():
                        if isinstance(val, dict) and isinstance(dest.get(key), dict):
                            # Merge inner dicts of IDs -> provenance tags
                            for inner_id, inner_val in val.items():
                                existing_val = dest[key].get(inner_id)
                                if existing_val is None:
                                    dest[key][inner_id] = inner_val
                                else:
                                    # Normalise to sets then union
                                    if not isinstance(existing_val, (list, set)):
                                        existing_val_set = {existing_val}
                                    else:
                                        existing_val_set = set(existing_val)
                                    if not isinstance(inner_val, (list, set)):
                                        inner_val_set = {inner_val}
                                    else:
                                        inner_val_set = set(inner_val)
                                    merged = existing_val_set | inner_val_set
                                    dest[key][inner_id] = sorted(merged) if len(merged) > 1 else next(iter(merged))
                        else:
                            # For scalar or list at top level, prefer union if both are list-like
                            if key in dest and isinstance(val, (list, set)) and isinstance(dest[key], (list, set)):
                                dest[key] = sorted(set(dest[key]) | set(val))
                            else:
                                dest[key] = val
                    return dest

                prov_merged: dict = {}
                for _src in (text_soa, vision_soa, parsed):
                    if isinstance(_src, dict):
                        _prov = _src.get('p2uProvenance')
                        if isinstance(_prov, dict):
                            prov_merged = _merge_prov(prov_merged, _prov)
                if prov_merged:
                    parsed['p2uProvenance'] = prov_merged

                # Ensure activityGroups are not lost during reconciliation.
                try:
                    parsed_tl = parsed.get('study', {}).get('versions', [])[0].get('timeline', {})
                    vision_tl = vision_soa.get('study', {}).get('versions', [])[0].get('timeline', {}) if isinstance(vision_soa, dict) else {}
                    if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                        parsed_tl['activityGroups'] = vision_tl['activityGroups']
                except Exception:
                    pass
                for _meta_key in (
                    'p2uProvenance',
                    'p2uOrphans',
                    'p2uGroupConflicts',
                    'p2uTimelineOrderIssues',
                ):
                    if _meta_key not in parsed:
                        if _meta_key in vision_soa:
                            parsed[_meta_key] = vision_soa[_meta_key]
                        elif _meta_key in text_soa:
                            parsed[_meta_key] = text_soa[_meta_key]
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
    # If OpenAI attempts failed or unavailable, try Gemini as fallback (only if Gemini wasn't the primary request above)
    if genai and os.environ.get('GOOGLE_API_KEY'):
        try:
            print("[INFO] Falling back to Gemini for reconciliation...")
            genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
            gemini_client = genai.GenerativeModel('gemini-2.5-pro')
            gemini_prompt = LLM_PROMPT + "\n\n" + user_content + "\nReturn ONLY the final reconciled JSON."
            response = gemini_client.generate_content([
                gemini_prompt
            ], generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            ))
            result = response.text.strip()
            parsed = json.loads(result)
            # Ensure required StudyVersion fields
            if isinstance(parsed, dict):
                versions = parsed.get('study', {}).get('versions', [])
                for version in versions:
                    version.setdefault('rationale', 'Not specified')
                    version.setdefault('studyIdentifiers', [])
                    version.setdefault('titles', [])
                # --- Preserve wrapper-level provenance & QC metadata ---
                # Deep merge provenance dictionaries so nested maps (e.g., plannedTimepoints, activities) are combined
                def _merge_prov(dest: dict, src: dict) -> dict:
                    """Recursively merge provenance dictionaries, preserving all tags."""
                    for key, val in src.items():
                        if isinstance(val, dict) and isinstance(dest.get(key), dict):
                            # Merge inner dicts of IDs -> provenance tags
                            for inner_id, inner_val in val.items():
                                existing_val = dest[key].get(inner_id)
                                if existing_val is None:
                                    dest[key][inner_id] = inner_val
                                else:
                                    # Normalise to sets then union
                                    if not isinstance(existing_val, (list, set)):
                                        existing_val_set = {existing_val}
                                    else:
                                        existing_val_set = set(existing_val)
                                    if not isinstance(inner_val, (list, set)):
                                        inner_val_set = {inner_val}
                                    else:
                                        inner_val_set = set(inner_val)
                                    merged = existing_val_set | inner_val_set
                                    dest[key][inner_id] = sorted(merged) if len(merged) > 1 else next(iter(merged))
                        else:
                            # For scalar or list at top level, prefer union if both are list-like
                            if key in dest and isinstance(val, (list, set)) and isinstance(dest[key], (list, set)):
                                dest[key] = sorted(set(dest[key]) | set(val))
                            else:
                                dest[key] = val
                    return dest

                prov_merged: dict = {}
                for _src in (text_soa, vision_soa, parsed):
                    if isinstance(_src, dict):
                        _prov = _src.get('p2uProvenance')
                        if isinstance(_prov, dict):
                            prov_merged = _merge_prov(prov_merged, _prov)
                if prov_merged:
                    parsed['p2uProvenance'] = prov_merged

                # Ensure activityGroups are not lost during reconciliation.
                try:
                    parsed_tl = parsed.get('study', {}).get('versions', [])[0].get('timeline', {})
                    vision_tl = vision_soa.get('study', {}).get('versions', [])[0].get('timeline', {}) if isinstance(vision_soa, dict) else {}
                    if not parsed_tl.get('activityGroups') and vision_tl.get('activityGroups'):
                        parsed_tl['activityGroups'] = vision_tl['activityGroups']
                except Exception:
                    pass
                for _meta_key in (
                    'p2uProvenance',
                    'p2uOrphans',
                    'p2uGroupConflicts',
                    'p2uTimelineOrderIssues',
                ):
                    if _meta_key not in parsed:
                        if _meta_key in vision_soa:
                            parsed[_meta_key] = vision_soa[_meta_key]
                        elif _meta_key in text_soa:
                            parsed[_meta_key] = text_soa[_meta_key]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] Gemini-reconciled SoA written to {output_path}")
            return
        except Exception as ge:
            print(f"[WARNING] Gemini reconciliation failed: {ge}")
    print(f"[FATAL] All model attempts failed: {tried if tried else 'No OpenAI client and Gemini failed'}")
    raise RuntimeError("Reconciliation failed with both OpenAI and Gemini models")

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
