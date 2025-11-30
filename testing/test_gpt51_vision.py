"""Test GPT-5.1 vision capability for SoA header extraction."""
import os
import json
import base64
import glob
from openai import OpenAI

def test_model_vision(model_name: str, client: OpenAI, data_url: str, prompt: str):
    """Test a specific model's vision capability."""
    print(f'\n{"="*60}')
    print(f'Testing: {model_name}')
    print(f'{"="*60}')
    
    try:
        # Handle reasoning models differently
        is_reasoning = any(rm in model_name.lower() for rm in ['o1', 'o3', 'gpt-5'])
        
        params = {
            "model": model_name,
            "messages": [{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': data_url}}
                ]
            }],
            "response_format": {'type': 'json_object'}
        }
        
        if is_reasoning:
            params["max_completion_tokens"] = 2048
        else:
            params["max_tokens"] = 2048
            params["temperature"] = 0.1
        
        response = client.chat.completions.create(**params)
        result = response.choices[0].message.content
        
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

if __name__ == '__main__':
    test_gpt51_vision()
