#!/usr/bin/env python3
"""
LLM-based epoch-encounter mapping using vision analysis.
Analyzes the SoA table structure to determine which encounters belong to which epochs.
"""

import json
import argparse
import sys
from pathlib import Path
from openai import OpenAI
import google.generativeai as genai
import base64
from PIL import Image
import io

def load_json(path):
    """Load JSON file safely."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        return None

def save_json(data, path):
    """Save JSON file safely."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {path}: {e}")
        return False

def encode_image_base64(image_path):
    """Encode image to base64 for vision models."""
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"[ERROR] Failed to encode image {image_path}: {e}")
        return None

def map_epochs_encounters_gemini(soa_pages_path, soa_json_path, model_name='gemini-2.0-flash-exp'):
    """Use Gemini vision model to map encounters to epochs."""
    
    # Load the SoA JSON to get current epochs and encounters
    soa_data = load_json(soa_json_path)
    if not soa_data:
        return None
    
    timeline = soa_data.get('study', {}).get('versions', [{}])[0].get('timeline', {})
    epochs = timeline.get('epochs', [])
    encounters = timeline.get('encounters', [])
    
    if not epochs or not encounters:
        print("[INFO] No epochs or encounters found in SoA JSON")
        return soa_data
    
    # Load SoA page images
    pages_data = load_json(soa_pages_path)
    if not pages_data or not pages_data.get('pages'):
        print("[ERROR] No SoA pages found")
        return None
    
    # Configure Gemini
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(model_name)
    
    # Prepare the prompt
    epoch_list = "\n".join([f"- {ep['id']}: {ep['name']}" for ep in epochs])
    encounter_list = "\n".join([f"- {enc['id']}: {enc['name']}" for enc in encounters])
    
    prompt = f"""Analyze this Schedule of Activities table to determine which encounters belong to which epochs.

EPOCHS (study phases):
{epoch_list}

ENCOUNTERS (visit windows/timepoints):
{encounter_list}

Looking at the table structure, please map each encounter to its corresponding epoch based on:
1. Visual column groupings and headers
2. Logical study phase progression
3. Any epoch labels or separators visible in the table

Return a JSON object with this structure:
{{
  "epoch_encounter_mapping": {{
    "epoch-1": ["enc_1", "enc_2", ...],
    "epoch-2": ["enc_3", "enc_4", ...],
    ...
  }}
}}

Only include encounters that clearly belong to each epoch. If uncertain, leave the encounter unmapped."""

    try:
        # Process the first SoA page (usually contains the main table)
        page_path = pages_data['pages'][0]['path']
        
        # Upload image to Gemini
        image_file = genai.upload_file(page_path)
        
        # Generate response
        response = model.generate_content([prompt, image_file])
        
        # Parse the response
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith('```'):
            response_text = response_text[3:-3].strip()
        
        mapping_result = json.loads(response_text)
        epoch_encounter_mapping = mapping_result.get('epoch_encounter_mapping', {})
        
        # Apply the mapping to epochs
        for epoch in epochs:
            epoch_id = epoch['id']
            if epoch_id in epoch_encounter_mapping:
                encounter_ids = epoch_encounter_mapping[epoch_id]
                epoch['encounters'] = [enc for enc in encounters if enc['id'] in encounter_ids]
                print(f"[INFO] Mapped {len(encounter_ids)} encounters to epoch {epoch_id}")
        
        print(f"[SUCCESS] Epoch-encounter mapping completed using {model_name}")
        return soa_data
        
    except Exception as e:
        print(f"[ERROR] Gemini vision analysis failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Map encounters to epochs using LLM vision analysis')
    parser.add_argument('--soa-pages', required=True, help='Path to SoA pages JSON file')
    parser.add_argument('--soa-json', required=True, help='Path to SoA JSON file to update')
    parser.add_argument('--output', required=True, help='Output path for updated SoA JSON')
    parser.add_argument('--model', default='gemini-2.0-flash-exp', help='Model to use for analysis')
    
    args = parser.parse_args()
    
    # Import os here to avoid issues if not available
    import os
    
    # Check for API key
    if not os.getenv('GEMINI_API_KEY'):
        print("[ERROR] GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Perform the mapping
    result = map_epochs_encounters_gemini(args.soa_pages, args.soa_json, args.model)
    
    if result:
        if save_json(result, args.output):
            print(f"[SUCCESS] Updated SoA with epoch-encounter mapping saved to {args.output}")
        else:
            sys.exit(1)
    else:
        print("[ERROR] Failed to map epochs to encounters")
        sys.exit(1)

if __name__ == '__main__':
    main()
