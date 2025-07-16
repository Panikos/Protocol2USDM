import os
import json
import base64
import mimetypes
from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Configure Gemini client
if os.environ.get("GOOGLE_API_KEY"):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Load visual guide snippet for better instructions
_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "Visual_guide_SOA", "USDM_viewer_Structure_and_Examples.md")
try:
    _guide_text = open(_GUIDE_PATH, "r", encoding="utf-8").read()
except FileNotFoundError:
    _guide_text = ""

LLM_PROMPT = (
    "You are an expert in analyzing the structure of clinical trial documents, specifically the Schedule of Activities (SoA). "
    "From the provided SoA images, your task is to extract the structural elements that define the schedule's timeline and activity categories. "
    "You must use the following USDM v4.0 entity definitions to structure your output.\n\n"
    "The following excerpt from our internal guide may help you understand the desired SoA layout:\n\n" + _guide_text[:1500] + "\n\n**Entity Definitions to Extract:**\n\n"
    "1. **Encounter:** Represents a visit or visit window (typically the main column headers).\n"
    "   - Key Attributes: `id`, `name`, `description`.\n"
    "2. **PlannedTimepoint:** Represents the specific timepoints within an encounter, often used for hierarchical columns (e.g., a 'Week 4' column header under a 'Treatment' phase).\n"
    "   - Key Attributes: `id`, `name`, `description`, `value`, `valueLabel`.\n"
    "3. **ActivityGroup:** Represents optional groupings of related activities, often indicated by a merged cell spanning multiple rows in the first column (e.g., 'Screening Assessments').\n"
    "   - Key Attributes: `id`, `name`, `activities` (a list of exact activity names belonging to the group).\n\n"
    "**Output Rules:**\n"
    "- Your output MUST be a single, valid JSON object **with exactly two top-level keys**: `columnHierarchy` and `rowHierarchy`.\n    * `columnHierarchy` must contain `epochs`, `encounters`, and `plannedTimepoints` arrays.\n    * `rowHierarchy` must contain `activityGroups` (and may include an empty `activities` array for orphan rows).\n"
    "- Within `columnHierarchy`, provide the encounter and plannedTimepoint objects exactly as defined below. Within `rowHierarchy`, provide activityGroups. These lists can be empty but must be present.\n"
    "- Focus ONLY on extracting these structural elements. Do NOT extract individual activities that aren't part of a group, and do NOT extract checkmarks.\n"
    "- Ensure all `id` fields are unique within the document.\n"
    "- If an entity type is not present (e.g., no activity groups are found), return an empty list for that key.\n"
)

def analyze_structure(image_paths, output_path, model_name='gpt-4o'):
    print(f"[INFO] Analyzing header structure for {len(image_paths)} images with model {model_name}...", flush=True)
    
    try:
        result = ""
        if 'gemini' in model_name.lower():
            model = genai.GenerativeModel(model_name)
            image_parts = []
            for img_path in image_paths:
                mime_type, _ = mimetypes.guess_type(img_path)
                if not mime_type or not mime_type.startswith('image'):
                    print(f"[WARN] Skipping non-image file: {img_path}")
                    continue
                image_parts.append({'mime_type': mime_type, 'data': Path(img_path).read_bytes()})
            
            if not image_parts:
                print("[FATAL] No valid images could be prepared for Gemini. Aborting analysis.")
                return False

            response = model.generate_content([LLM_PROMPT] + image_parts, generation_config={"response_mime_type": "application/json"})
            result = response.text
        else:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            content = [{"type": "text", "text": LLM_PROMPT}]
            for img_path in image_paths:
                with open(img_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}", "detail": "high"}
                    })
            if len(content) <= 1:
                print("[FATAL] No images could be read or encoded for OpenAI. Aborting analysis.")
                return False
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content

        if not result:
            print("[FATAL] LLM returned an empty response.")
            return False

        # Clean the response to ensure it's valid JSON
        # It should start with { and end with }
        result_cleaned = result.strip()
        if result_cleaned.startswith('```json'):
            result_cleaned = result_cleaned[7:-4].strip()
        
        parsed_json = json.loads(result_cleaned)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] SoA header structure analysis complete. Output saved to {output_path}")
        return True

    except Exception as e:
        print(f"[FATAL] An error occurred during LLM analysis: {e}")
        print(f"[DEBUG] Model: {model_name}")
        return False

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Analyze the hierarchical structure of SoA table headers from images.")
    parser.add_argument("--images-dir", required=True, help="Directory containing the SoA image files.")
    parser.add_argument("--output", required=True, help="Path to write the output JSON file.")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="LLM model to use (e.g., gpt-4o, gemini-1.5-pro-latest).")
    args = parser.parse_args()

    try:
        image_paths = sorted([
            os.path.join(args.images_dir, f)
            for f in os.listdir(args.images_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ])
        if not image_paths:
            print(f"[ERROR] No PNG or JPG images found in {args.images_dir}", file=sys.stderr)
            exit(1)
    except FileNotFoundError:
        print(f"[ERROR] Images directory not found: {args.images_dir}", file=sys.stderr)
        exit(1)

    if not analyze_structure(image_paths, args.output, args.model):
        exit(1)
