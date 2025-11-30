"""Test GPT-5.1 vision capability for SoA header extraction."""
import os
import json
import base64
import glob
from openai import OpenAI

def test_model_vision(model_name: str, client: OpenAI, data_url: str, prompt: str):
    """Test a specific model's vision capability using Responses API."""
    print(f'\n{"="*60}')
    print(f'Testing: {model_name}')
    print(f'{"="*60}')
    
    try:
        # Handle reasoning models differently
        is_reasoning = any(rm in model_name.lower() for rm in ['o1', 'o3', 'gpt-5'])
        
        # Build input for Responses API - use input_text and input_image types
        input_content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": data_url}
        ]
        
        params = {
            "model": model_name,
            "input": [{"role": "user", "content": input_content}],
            "text": {"format": {"type": "json_object"}},
            "max_output_tokens": 2048,
        }
        
        if not is_reasoning:
            params["temperature"] = 0.1
        
        response = client.responses.create(**params)
        
        # Extract content from Responses API response
        result = ""
        if hasattr(response, 'output_text'):
            result = response.output_text
        elif hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content'):
                    for content_item in item.content:
                        if hasattr(content_item, 'text'):
                            result = content_item.text
                            break
        
        print(f'Response: {result[:500]}...' if len(result) > 500 else f'Response: {result}')
        
        # Parse and show structure
        try:
            data = json.loads(result)
            epochs = data.get("epochs", [])
            encounters = data.get("encounters", [])
            print(f'\nParsed: {len(epochs)} epochs, {len(encounters)} encounters')
            if encounters:
                print(f'Sample encounters: {[e.get("name", e) for e in encounters[:5]]}')
            return data
        except json.JSONDecodeError as e:
            print(f'JSON parse error: {e}')
            return None
            
    except Exception as e:
        print(f'API Error: {e}')
        return None

def test_gpt51_vision():
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    # Simple diagnostic prompt first
    simple_prompt = """Describe what you see in this image. 
Is this a table? How many columns? How many rows?
Return JSON: {"is_table": true/false, "columns": <number>, "rows": <number>, "description": "..."}"""
    
    # SoA extraction prompt
    soa_prompt = """Look at this clinical trial Schedule of Activities (SoA) table image.
    
Extract the table structure and return a JSON object with:
{
  "epochs": [{"name": "..."}],
  "encounters": [{"name": "..."}],
  "activity_count": <number of activity rows you see>
}

List ALL the column headers (visits/timepoints) you can see in the table.
"""
    
    # Find an SoA image - use page 11 or 12 which should be the actual SoA table
    soa_dirs = sorted(glob.glob('output/*/3_soa_images'), reverse=True)
    img_path = None
    if soa_dirs:
        # Try to find page 14 or 15 (more likely to be actual SoA grid)
        for page_num in ['014', '015', '016']:
            candidate = os.path.join(soa_dirs[0], f'soa_page_{page_num}.png')
            if os.path.exists(candidate):
                img_path = candidate
                break
        
        # Fallback to first image
        if not img_path:
            imgs = sorted(glob.glob(soa_dirs[0] + '/*.png'))
            if imgs:
                img_path = imgs[0]
    
    if not img_path:
        print('No SoA images found')
        return
    
    print(f'Using image: {img_path}')
    
    with open(img_path, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('utf-8')
    
    data_url = f'data:image/png;base64,{img_data}'
    
    # Test 1: Simple diagnostic - can the model see the image?
    print('\n' + '='*60)
    print('TEST 1: Simple diagnostic - can models see the table?')
    print('='*60)
    
    models_to_test = ['gpt-5.1', 'gpt-4o-mini', 'gpt-4o']
    
    for model in models_to_test:
        test_model_vision(model, client, data_url, simple_prompt)
    
    # Test 2: SoA extraction with best working model
    print('\n' + '='*60)
    print('TEST 2: SoA structure extraction')
    print('='*60)
    
    for model in models_to_test:
        test_model_vision(model, client, data_url, soa_prompt)

def test_full_soa_extraction():
    """Test GPT-5.1 with multiple SoA table pages for complete extraction."""
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    # Get all SoA images
    soa_dirs = sorted(glob.glob('output/*/3_soa_images'), reverse=True)
    if not soa_dirs:
        print('No SoA images found')
        return
    
    soa_dir = soa_dirs[0]
    all_images = sorted(glob.glob(soa_dir + '/*.png'))
    
    print(f'Total SoA images: {len(all_images)}')
    for img in all_images:
        print(f'  {os.path.basename(img)}')
    
    # Use pages 14-18 (the actual table pages)
    table_pages = [img for img in all_images 
                   if any(p in img for p in ['014', '015', '016', '017', '018', '019'])]
    
    print(f'\nUsing table pages: {[os.path.basename(p) for p in table_pages]}')
    
    prompt = """Analyze these Schedule of Activities (SoA) table pages from a clinical trial protocol.

These pages form a MULTI-PAGE SoA table. Extract the COMPLETE structure across ALL pages.

Return JSON with:
{
  "epochs": [{"name": "..."}],
  "encounters": [{"name": "..."}],  
  "activity_count": <total number of activity rows across all pages>
}

IMPORTANT: 
- Count ALL column headers (visits/timepoints) across ALL pages
- The table may continue across pages - combine them into ONE unified list
- Look for headers like Day -7, Day 1, Week 4, Screening, etc.
- Include ALL visits you can see in the column headers
"""
    
    # Build input for Responses API - use input_text and input_image types
    input_content = [{'type': 'input_text', 'text': prompt}]
    for img_path in table_pages:
        with open(img_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        input_content.append({
            'type': 'input_image',
            'image_url': f'data:image/png;base64,{img_data}'
        })
    
    print(f'\nCalling GPT-5.1 with {len(table_pages)} images (Responses API)...')
    response = client.responses.create(
        model='gpt-5.1',
        input=[{"role": "user", "content": input_content}],
        text={"format": {"type": "json_object"}},
        max_output_tokens=8192,
    )
    
    # Extract content from Responses API response
    result = ""
    if hasattr(response, 'output_text'):
        result = response.output_text
    elif hasattr(response, 'output') and response.output:
        for item in response.output:
            if hasattr(item, 'content'):
                for content_item in item.content:
                    if hasattr(content_item, 'text'):
                        result = content_item.text
                        break
    print('\nGPT-5.1 Response:')
    print(result[:2000] + '...' if len(result) > 2000 else result)
    
    data = json.loads(result)
    epochs = data.get('epochs', [])
    encounters = data.get('encounters', [])
    
    print(f'\n{"="*60}')
    print(f'RESULTS: {len(epochs)} epochs, {len(encounters)} encounters, {data.get("activity_count", "N/A")} activities')
    print(f'{"="*60}')
    
    if encounters:
        print('\nAll encounters:')
        for i, enc in enumerate(encounters):
            name = enc.get('name', enc) if isinstance(enc, dict) else enc
            print(f'  {i+1}. {name}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        test_full_soa_extraction()
    else:
        test_gpt51_vision()
