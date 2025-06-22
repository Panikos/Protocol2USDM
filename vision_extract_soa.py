import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))



def encode_image_to_base64(image_path):
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def extract_soa_from_images(image_paths):
    usdm_prompt = (
        "You are an expert in clinical trial protocol data modeling.\n"
        "Extract the Schedule of Activities (SoA) from the following protocol images and return it as a single JSON object conforming to the CDISC USDM v4.0 OpenAPI schema, specifically the Wrapper-Input object.\n"
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
        "\n"
        "For the Schedule of Activities:\n"
        "- plannedTimepoints: List all planned visits/timepoints (e.g., Screening, Baseline, Week 1, End of Study). Each must have id, name, and instanceType ('PlannedTimepoint').\n"
        "- activities: List all activities/procedures (e.g., Informed Consent, Blood Draw, ECG). Each must have id, name, and instanceType ('Activity').\n"
        "- activityGroups: If the protocol groups activities (e.g., Labs, Safety Assessments), define these here.\n"
        "- activityTimepoints: For each cell in the SoA table (i.e., each activity at each timepoint), create an object mapping the activity to the timepoint. Each must have id, activityId, plannedTimepointId, and instanceType ('ActivityTimepoint').\n"
        "- Use unique IDs for all entities.\n"
        "\n"
        "General Instructions:\n"
        "- Output ONLY valid JSON (no markdown, explanations, or comments).\n"
        "- If a required field is missing in the protocol, use null or an empty array as appropriate.\n"
        "- All objects must include their required instanceType property with the correct value.\n"
        "- Follow the OpenAPI schema exactly for field names, types, and nesting.\n"
        "\n"
        "If you need the full field list for each object, refer to the OpenAPI schema.\n"
    )
    messages = [
        {"role": "system", "content": usdm_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "The following are images of the Schedule of Activities table from a clinical trial protocol. If the table spans both images, merge them into one SoA."}
        ]}
    ]
    for image_path in image_paths:
        img_b64 = encode_image_to_base64(image_path)
        messages[1]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        })
    # Model fallback logic
    model_order = [MODEL_NAME]
    if MODEL_NAME == 'o3':
        model_order += ['o3-mini-high', 'gpt-4o']
    elif MODEL_NAME == 'o3-mini-high':
        model_order += ['gpt-4o']
    tried = []
    for model_try in model_order:
        print(f"[INFO] Using OpenAI model: {model_try}")
        try:
            params = dict(model=model_try, messages=messages)
            if model_try in ['o3', 'o3-mini', 'o3-mini-high']:
                params['max_completion_tokens'] = 90000
            else:
                params['max_tokens'] = 16384
            response = client.chat.completions.create(**params)
            content = response.choices[0].message.content
            if len(content) > 3800:
                print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
            return content
        except Exception as e:
            err_msg = str(e)
            print(f"[WARNING] Model '{model_try}' failed: {err_msg}")
            tried.append(model_try)
            continue
    print(f"[FATAL] All model attempts failed: {tried}")
    raise RuntimeError(f"No available model succeeded: {tried}")


if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("image_paths", nargs="+", help="List of image paths to process")
    parser.add_argument("--output", default="STEP2_soa_vision.json", help="Output JSON file")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'o3'), help="OpenAI model to use")
    args = parser.parse_args()
    MODEL_NAME = args.model
    if 'OPENAI_MODEL' not in os.environ:
        os.environ['OPENAI_MODEL'] = MODEL_NAME
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")
    soa_vision = extract_soa_from_images(args.image_paths)
    from json_utils import clean_llm_json
    if not soa_vision or not soa_vision.strip():
        with open("soa_vision_raw.txt", "w", encoding="utf-8") as f:
            f.write(str(soa_vision))
        print("[ERROR] LLM response was empty. Raw output saved to soa_vision_raw.txt.")
        sys.exit(1)
    cleaned = clean_llm_json(soa_vision)
    try:
        parsed_json = json.loads(cleaned)
    except json.JSONDecodeError:
        with open("soa_vision_raw.txt", "w", encoding="utf-8") as f:
            f.write(str(soa_vision))
        print("[ERROR] Cleaned LLM response was not valid JSON. Raw output saved to soa_vision_raw.txt.")
        print(f"[FATAL] Could not recover JSON.")
        sys.exit(1)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote SoA vision output to {args.output}")
