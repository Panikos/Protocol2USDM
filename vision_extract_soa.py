import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--model', default=os.environ.get('OPENAI_MODEL', 'gpt-4o'))
args, _ = parser.parse_known_args()
MODEL_NAME = args.model
if 'OPENAI_MODEL' not in os.environ:
    os.environ['OPENAI_MODEL'] = MODEL_NAME
print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

def encode_image_to_base64(image_path):
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def extract_soa_from_images(image_paths):
    usdm_prompt = (
        "You are an expert in clinical trial protocol data modeling.\n"
        "Extract the Schedule of Activities (SoA) from the following protocol images and return it as a single JSON object conforming to the CDISC USDM v4.0 OpenAPI schema, specifically the Wrapper-Input object.\n"
        "\n"
        "Requirements:\n"
        "- The top-level object must have these keys:\n"
        "  - study: an object conforming to the Study-Input schema, fully populated with all required and as many optional fields as possible.\n"
        "  - usdmVersion: string, always set to '4.0'.\n"
        "  - systemName: string, set to 'Protocol2USDMv3'.\n"
        "  - systemVersion: string, set to '1.0'.\n"
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
        "    - activities: array of Activity-Input (each with unique id, name, instanceType, etc.).\n"
        "    - activityGroups: array of ActivityGroup-Input (each with unique id, name, instanceType, etc.).\n"
        "    - activityTimepoints: array of ActivityTimepoint-Input (each mapping an activity to a timepoint).\n"
        "- amendments: array (can be empty).\n"
        "- instanceType: string, must be 'StudyVersion'.\n"
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
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=16384
    )
    content = response.choices[0].message.content
    if len(content) > 3800:
        print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
    return content


if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser(description="Extract SoA from protocol images.")
    parser.add_argument("image_paths", nargs="+", help="List of image paths to process")
    parser.add_argument("--output", default="STEP2_soa_vision.json", help="Output JSON file")
    args = parser.parse_args()
    soa_vision = extract_soa_from_images(args.image_paths)
    def clean_llm_json(raw):
        raw = raw.strip()
        # Remove code block markers
        if raw.startswith('```json'):
            raw = raw[7:]
        if raw.startswith('```'):
            raw = raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]
        # Remove anything after the last closing brace
        last_brace = raw.rfind('}')
        if last_brace != -1:
            raw = raw[:last_brace+1]
        return raw
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
