import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Load JSON files
def load_json(path):
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        exit(1)
    if os.path.getsize(path) == 0:
        print(f"ERROR: File is empty: {path}")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {path}: {e}")
            exit(1)

# Save JSON file
def save_json(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# Render ASCII table for human review
def render_ascii_table(merged):
    visits = sorted({v for row in merged for v in row['Visits'].keys()})
    header = ['Activity'] + visits
    print(' | '.join(header))
    print('-' * (len(header) * 16))
    for row in merged:
        line = [row['Activity']] + [row['Visits'].get(v, '') for v in visits]
        print(' | '.join(line))

# Use GPT-4o to judge discrepancies
def llm_judge(activity, visit, value_text, value_vision):
    prompt = f"""
You are an expert in clinical trial protocol data extraction. For the following Schedule of Activities cell, choose the correct value between two extractions:

Activity: {activity}
Visit: {visit}
Option 1 (text extraction): {value_text}
Option 2 (vision extraction): {value_vision}

Reply with only the correct value (or empty string if neither is correct).
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert in clinical trial data curation."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=10
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    text_soa = load_json('soa_text.json')
    vision_soa = load_json('soa_vision.json')

    # Convert text_soa to a dict for easier lookup
    # text_soa: {visit: {week, activities}}
    text_lookup = {}
    for visit in text_soa['Schedule of Events']:
        vnum = visit['Visit']
        for act in visit['Activities']:
            text_lookup.setdefault(act, {})[vnum] = 'X'  # Just mark as present

    # vision_soa: list of {Activity, Visits: {visit: mark}}
    merged = []
    for row in vision_soa:
        activity = row['Activity']
        visits = row['Visits']
        merged_visits = {}
        for v, vval in visits.items():
            tval = text_lookup.get(activity, {}).get(v, '')
            if vval == tval or not tval:
                merged_visits[v] = vval
            elif not vval:
                merged_visits[v] = tval
            else:
                # Discrepancy: ask LLM
                merged_visits[v] = llm_judge(activity, v, tval, vval)
        merged.append({'Activity': activity, 'Visits': merged_visits})

    save_json(merged, 'soa_merged.json')
    render_ascii_table(merged)
    print("\nMerged SoA saved to soa_merged.json")
