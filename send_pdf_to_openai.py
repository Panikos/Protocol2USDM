import os
from openai import OpenAI
from dotenv import load_dotenv
import fitz  # PyMuPDF

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set your OpenAI API key using environment variable for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--model', default=os.environ.get('OPENAI_MODEL', 'gpt-4o'))
parser.add_argument('pdf_path', nargs='?')
parser.add_argument('--output', default='soa_extracted.json')
args, _ = parser.parse_known_args()
MODEL_NAME = args.model
if 'OPENAI_MODEL' not in os.environ:
    os.environ['OPENAI_MODEL'] = MODEL_NAME
print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def send_text_to_openai(text):
    usdm_prompt = (
        "You are an expert in clinical trial protocol data modeling.\n"
        "Extract the Schedule of Activities (SoA) from the following protocol text and return it as a single JSON object conforming to the CDISC USDM v4.0 OpenAPI schema, specifically the Wrapper-Input object.\n"
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
        {"role": "user", "content": text}
    ]
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=16384
    )
    content = response.choices[0].message.content
    if len(content) > 3800:
        print("[WARNING] LLM output may be truncated. Consider splitting the task or increasing max_tokens if supported.")
    return content

# Path to your PDF file
pdf_path = 'c:/Users/panik/Documents/GitHub/Protcol2USDMv3/CDISC_Pilot_Study.pdf'

# Extract text and send to GPT-4o
pdf_text = extract_pdf_text(pdf_path)
import json

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

parsed_content = send_text_to_openai(pdf_text)
import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    parsed_json = json.loads(parsed_content)
except json.JSONDecodeError:
    cleaned = clean_llm_json(parsed_content)
    parsed_json = json.loads(cleaned)
print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

# Optionally, save to file
with open("STEP1_soa_text.json", "w", encoding="utf-8") as f:
    json.dump(parsed_json, f, indent=2, ensure_ascii=False)
