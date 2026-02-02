"""
Header Analyzer - Vision-based SoA structure extraction.

This module extracts ONLY the structural information from SoA table images:
- Epochs (study phases from column headers)
- Encounters (visits from column headers)
- PlannedTimepoints (timepoints from column headers)
- ActivityGroups (row section headers)

It does NOT extract:
- Activity details (names, descriptions) - this is text extraction's job
- Tick marks (activity-timepoint matrix) - this is text extraction's job

The output (HeaderStructure) provides the ANCHOR for text extraction,
ensuring text extraction uses the correct IDs and structure.

Usage:
    from extraction.header_analyzer import analyze_soa_headers
    
    result = analyze_soa_headers(image_paths, model_name="gemini-2.5-pro")
    header_structure = result.structure  # Use this to guide text extraction
"""

import json
import base64
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json
from core.usdm_types import HeaderStructure, Epoch, Encounter, PlannedTimepoint, ActivityGroup
from llm_providers import usage_tracker

logger = logging.getLogger(__name__)


# Focused prompt for STRUCTURE extraction only
HEADER_ANALYSIS_PROMPT = """You are analyzing a Schedule of Activities (SoA) table from a clinical trial protocol.

Your task is to extract ONLY the STRUCTURE of the table - the column headers and row group headers.
Do NOT extract the activity details or tick marks - only the structural elements.

EXTRACT:
1. **Epochs** - Study phases from the TOP-LEVEL merged header row
   - These span multiple columns (e.g., "Screening", "Treatment", "Follow-up")
   - Usually in the first header row with merged cells
   
2. **Encounters** - One per COLUMN, from SUB-HEADER rows below the epoch row
   - CRITICAL: Each encounter MUST have a UNIQUE name
   - Include timing info from sub-headers (e.g., "Screening (-42 to -9)", "Day -6 through -4", "Week 4")
   - If multiple columns are under the same epoch, use the sub-header text to make names unique
   - Pattern: "{Epoch} ({Timing})" or just "{Timing}" if timing is descriptive enough
   - NEVER use the same name for multiple encounters - look for day numbers, week numbers, or visit numbers
   
3. **PlannedTimepoints** - Timing information for each encounter (one per encounter)
   - The valueLabel should have the specific timing (e.g., "Day -14", "Week 0", "Day 28")
   - Link each timepoint to its encounter via encounterId
   
4. **ActivityGroups** - Row section headers (e.g., "Safety Assessments", "Efficacy", "Labs")
   - These are the bold/highlighted rows that group related activities
   - They typically have NO tick marks (empty cells across the row)
   - They may have merged cells spanning the activity column
   - IMPORTANT: Report visual properties for each group
   - CRITICAL: Include `activityNames` - a list of activity names that appear UNDER this group header
   - Read the activity names from the rows between this group header and the next group header

5. **Footnotes** - CRITICAL: Extract ALL footnotes from ALL pages
   - Look at the BOTTOM of EACH PAGE for footnote text
   - Footnotes are lettered (a, b, c... through x, y, z) or numbered (1, 2, 3...)
   - EXTRACT EVERY SINGLE FOOTNOTE - protocols often have 20-30+ footnotes
   - Include footnotes from appendix tables and continuation pages
   - Format: "a. Full text of footnote a", "b. Full text of footnote b", etc.
   - Do NOT skip any letters - if you see footnotes a, b, c, l, u, w, x there are likely d-k, m-t, v in between
   - Look for footnotes on EVERY page image provided

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{
  "columnHierarchy": {
    "epochs": [
      {"id": "epoch_1", "name": "Screening", "position": 1},
      {"id": "epoch_2", "name": "Treatment", "position": 2}
    ],
    "encounters": [
      {"id": "enc_1", "name": "Screening (-42 to -9)", "epochId": "epoch_1"},
      {"id": "enc_2", "name": "Screening (-21)", "epochId": "epoch_1"},
      {"id": "enc_3", "name": "Day 1 (Baseline)", "epochId": "epoch_2"},
      {"id": "enc_4", "name": "Week 4", "epochId": "epoch_2"},
      {"id": "enc_5", "name": "Week 8", "epochId": "epoch_2"}
    ],
    "plannedTimepoints": [
      {"id": "pt_1", "name": "Screening (-42 to -9)", "encounterId": "enc_1", "valueLabel": "Day -42 to -9", "description": "Initial screening"},
      {"id": "pt_2", "name": "Screening (-21)", "encounterId": "enc_2", "valueLabel": "Day -21", "description": "Final screening"},
      {"id": "pt_3", "name": "Day 1 (Baseline)", "encounterId": "enc_3", "valueLabel": "Day 1", "description": "Baseline visit"},
      {"id": "pt_4", "name": "Week 4", "encounterId": "enc_4", "valueLabel": "Week 4", "description": "Treatment visit"},
      {"id": "pt_5", "name": "Week 8", "encounterId": "enc_5", "valueLabel": "Week 8", "description": "Treatment visit"}
    ]
  },
  "rowGroups": [
    {
      "id": "grp_1", 
      "name": "Eligibility",
      "isBold": true,
      "hasMergedCells": true,
      "spansFullWidth": true,
      "visualConfidence": 0.95,
      "activityNames": ["Informed Consent", "Demographics", "Medical History"]
    },
    {
      "id": "grp_2", 
      "name": "Safety Assessments",
      "isBold": true,
      "hasMergedCells": false,
      "spansFullWidth": true,
      "visualConfidence": 0.9,
      "activityNames": ["Vital Signs", "Physical Examination", "ECG", "Adverse Events"]
    },
    {
      "id": "grp_3", 
      "name": "PK/PD Analyses",
      "isBold": true,
      "hasMergedCells": true,
      "spansFullWidth": true,
      "visualConfidence": 0.95,
      "activityNames": ["Blood Sampling for PK", "PD Biomarkers"]
    }
  ],
  "footnotes": [
    "a. Only for subjects in Cohort A",
    "b. Performed at screening and at early termination only",
    "c. Within 30 minutes of dosing"
  ]
}

RULES:
- Use snake_case IDs with sequential numbering (epoch_1, enc_1, pt_1, grp_1)
- Every encounter must reference its parent epoch via epochId
- Every plannedTimepoint must reference its encounter via encounterId
- The name and valueLabel for plannedTimepoints should preserve the exact text from the table
- Include ALL columns and row groups visible in the table
- For multi-page tables, combine all pages into one unified structure
- If epochs are not explicitly shown, create a single "Study Period" epoch

CRITICAL - UNIQUE ENCOUNTER NAMES:
- EVERY encounter MUST have a unique name (never duplicate names)
- Look at ALL header rows to find differentiating info: Day numbers, Week numbers, Visit numbers
- If columns are labeled "Day -6", "Day -5", "Day -4" under "Inpatient Period", use those as encounter names
- Pattern examples: "Day -6 through -4", "Inpatient Period (Day 1)", "Week 4 Visit"
- If you cannot find unique timing, number them: "Inpatient Day 1", "Inpatient Day 2", etc.
- The viewer needs unique names to distinguish columns - duplicates break the display

ROW GROUP VISUAL PROPERTIES (required for each group):
- `isBold`: true if the text appears bold/emphasized
- `hasMergedCells`: true if cells span across columns
- `spansFullWidth`: true if the row spans the full table width
- `visualConfidence`: 0.0-1.0 confidence this is truly a category header (not an activity)
- `activityNames`: REQUIRED - list of activity names that appear UNDER this group header (read from the rows between this group and the next)

Output ONLY the JSON object, no explanations or markdown."""


class RecitationBlockedError(Exception):
    """Raised when Gemini blocks response due to RECITATION (training data similarity).
    
    This is NOT an actual copyright issue - Gemini's RECITATION filter detects when
    output would be too similar to training data, regardless of the source's actual
    copyright status. Content from public domain sources like clinicaltrials.gov
    can still trigger this filter.
    
    This is a known Gemini limitation that cannot be disabled via API settings.
    """
    pass


@dataclass
class HeaderAnalysisResult:
    """Result of header structure analysis."""
    structure: HeaderStructure
    raw_response: str
    model_used: str
    image_count: int
    success: bool
    error: Optional[str] = None
    recitation_blocked: bool = False  # True if Gemini RECITATION filter triggered
    
    def to_dict(self):
        return {
            'structure': self.structure.to_dict() if self.structure else None,
            'model_used': self.model_used,
            'image_count': self.image_count,
            'success': self.success,
            'error': self.error,
            'recitation_blocked': self.recitation_blocked,
        }


def encode_image(image_path: str) -> str:
    """Encode image to base64 data URL."""
    with open(image_path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    
    # Determine MIME type
    suffix = Path(image_path).suffix.lower()
    mime_type = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }.get(suffix, 'image/png')
    
    return f"data:{mime_type};base64,{data}"


def analyze_soa_headers(
    image_paths: List[str],
    model_name: str = "gemini-2.5-pro",
    custom_prompt: Optional[str] = None,
) -> HeaderAnalysisResult:
    """
    Analyze SoA table images to extract structural information.
    
    This function extracts ONLY the structure (headers, groups) - not the full SoA data.
    The resulting HeaderStructure is used to anchor text extraction.
    
    Args:
        image_paths: List of paths to SoA table images
        model_name: LLM model to use (must support vision)
        custom_prompt: Optional custom prompt to override default
        
    Returns:
        HeaderAnalysisResult containing the extracted structure
        
    Example:
        >>> result = analyze_soa_headers(["soa_page1.png", "soa_page2.png"])
        >>> if result.success:
        ...     print(f"Found {len(result.structure.encounters)} encounters")
    """
    if not image_paths:
        return HeaderAnalysisResult(
            structure=None,
            raw_response="",
            model_used=model_name,
            image_count=0,
            success=False,
            error="No images provided"
        )
    
    logger.info(f"Analyzing {len(image_paths)} SoA images with {model_name}")
    
    try:
        # Build prompt
        prompt = custom_prompt or HEADER_ANALYSIS_PROMPT
        
        # Route to appropriate provider
        if 'gemini' in model_name.lower():
            return _analyze_with_gemini(image_paths, model_name, prompt)
        elif 'claude' in model_name.lower():
            return _analyze_with_claude(image_paths, model_name, prompt)
        else:
            return _analyze_with_openai(image_paths, model_name, prompt)
    
    except RecitationBlockedError as e:
        # RECITATION is a known Gemini issue - not an actual copyright problem
        logger.warning(f"Header analysis blocked by RECITATION filter: {e}")
        return HeaderAnalysisResult(
            structure=None,
            raw_response="",
            model_used=model_name,
            image_count=len(image_paths),
            success=False,
            error=str(e),
            recitation_blocked=True
        )
            
    except Exception as e:
        logger.error(f"Header analysis failed: {e}")
        # Check if the error message indicates RECITATION
        error_str = str(e).lower()
        is_recitation = 'recitation' in error_str or 'finish_reason is 4' in error_str
        if is_recitation:
            logger.warning("Detected RECITATION blocking from error message")
        return HeaderAnalysisResult(
            structure=None,
            raw_response="",
            model_used=model_name,
            image_count=len(image_paths),
            success=False,
            error=str(e),
            recitation_blocked=is_recitation
        )


def _analyze_with_gemini(
    image_paths: List[str], 
    model_name: str, 
    prompt: str
) -> HeaderAnalysisResult:
    """Analyze using Google Gemini."""
    from PIL import Image
    import io
    import os
    import time
    
    # Check if this is a Gemini 3 model
    is_gemini3 = any(g3 in model_name.lower() for g3 in ['gemini-3', 'gemini-3-flash', 'gemini-3-pro'])
    
    # Load images as base64
    image_parts = []
    for img_path in image_paths:
        img = Image.open(img_path)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        image_parts.append({
            'mime_type': 'image/png',
            'data': base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        })
    
    # Retry configuration
    max_retries = 3
    initial_backoff = 5
    
    def call_api_gemini3(images_data: List[dict]) -> Tuple[str, HeaderStructure]:
        """Make API call using google-genai SDK for Gemini 3."""
        from google import genai as genai_new
        from google.genai import types as genai_types
        
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        client = genai_new.Client(vertexai=True, project=project, location='global')
        
        content_parts = [prompt]
        for img_data in images_data:
            content_parts.append(genai_types.Part.from_bytes(
                data=base64.b64decode(img_data['data']),
                mime_type=img_data['mime_type']
            ))
        
        config = genai_types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
        )
        
        response = client.models.generate_content(
            model=model_name if 'preview' in model_name else f"{model_name}-preview",
            contents=content_parts,
            config=config,
        )
        
        # Track token usage
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
            usage_tracker.add_usage(input_tokens, output_tokens)
        
        raw = response.text or ""
        data = parse_llm_json(raw, fallback={})
        if isinstance(data, list) and data:
            data = data[0]
        struct = HeaderStructure.from_dict(data) if isinstance(data, dict) else HeaderStructure.from_dict({})
        return raw, struct
    
    def call_api_standard(images_data: List[dict]) -> Tuple[str, HeaderStructure]:
        """Make API call using standard AI Studio SDK."""
        import google.generativeai as genai
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        content_parts = [prompt]
        for img_data in images_data:
            content_parts.append({'inline_data': img_data})
        
        response = model.generate_content(
            content_parts,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        # Check for RECITATION blocking before accessing response.text
        # finish_reason: 1=STOP (normal), 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            # finish_reason 4 = RECITATION (blocked due to training data similarity)
            if finish_reason == 4 or str(finish_reason) == 'FinishReason.RECITATION':
                raise RecitationBlockedError(
                    "Gemini RECITATION filter triggered - model detected similarity to training data. "
                    "This is NOT an actual copyright issue (content is from public domain clinicaltrials.gov). "
                    "This is a known Gemini limitation that cannot be disabled via API settings."
                )
        
        # Track token usage
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
            usage_tracker.add_usage(input_tokens, output_tokens)
        
        raw = response.text or ""
        data = parse_llm_json(raw, fallback={})
        if isinstance(data, list) and data:
            data = data[0]
        struct = HeaderStructure.from_dict(data) if isinstance(data, dict) else HeaderStructure.from_dict({})
        return raw, struct
    
    def call_api_with_retry(images_data: List[dict]) -> Tuple[str, HeaderStructure]:
        """Call API with retry logic for rate limits."""
        for attempt in range(max_retries + 1):
            try:
                if is_gemini3:
                    return call_api_gemini3(images_data)
                else:
                    return call_api_standard(images_data)
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = '429' in error_str or 'rate' in error_str or 'exhausted' in error_str or 'quota' in error_str
                
                if is_rate_limit and attempt < max_retries:
                    wait_time = min(initial_backoff * (2 ** attempt), 60)
                    logger.warning(f"Rate limit in header analysis, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                else:
                    raise
        return "", HeaderStructure.from_dict({})  # Fallback
    
    # Try with all images first
    raw_response, structure = call_api_with_retry(image_parts)
    structure = _enforce_unique_encounter_names(structure)
    
    # If result is empty and we have multiple images, try with later images only
    # (Early pages often contain SoA title/text, actual table is on later pages)
    if len(image_parts) > 3 and not structure.encounters:
        logger.info(f"Empty result with all images, retrying with later images only...")
        later_images = image_parts[len(image_parts)//2:]
        raw_response, structure = call_api_with_retry(later_images)
        structure = _enforce_unique_encounter_names(structure)
        
        # If still empty, try middle images
        if not structure.encounters and len(image_parts) > 4:
            logger.info(f"Still empty, trying middle images...")
            mid_start = len(image_parts) // 3
            mid_end = 2 * len(image_parts) // 3
            mid_images = image_parts[mid_start:mid_end]
            raw_response, structure = call_api_with_retry(mid_images)
            structure = _enforce_unique_encounter_names(structure)
    
    return HeaderAnalysisResult(
        structure=structure,
        raw_response=raw_response,
        model_used=model_name,
        image_count=len(image_paths),
        success=True
    )


def _analyze_with_openai(
    image_paths: List[str], 
    model_name: str, 
    prompt: str
) -> HeaderAnalysisResult:
    """Analyze using OpenAI Responses API with vision."""
    from openai import OpenAI
    import os
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    
    def call_api(images: List[str]) -> Tuple[str, HeaderStructure]:
        """Make API call with given images using Responses API."""
        # Build input content for Responses API - use input_text and input_image types
        input_content = [{"type": "input_text", "text": prompt}]
        for img_path in images:
            data_url = encode_image(img_path)
            input_content.append({
                "type": "input_image",
                "image_url": data_url
            })
        
        # Build parameters for Responses API
        is_reasoning = any(rm in model_name.lower() for rm in ['o1', 'o3', 'gpt-5'])
        
        params = {
            "model": model_name,
            "input": [{"role": "user", "content": input_content}],
            "text": {"format": {"type": "json_object"}},
            "max_output_tokens": 4096,
        }
        
        if not is_reasoning:
            params["temperature"] = 0.1
        
        response = client.responses.create(**params)
        
        # Extract content from Responses API response
        raw = ""
        if hasattr(response, 'output_text'):
            raw = response.output_text
        elif hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content'):
                    for content_item in item.content:
                        if hasattr(content_item, 'text'):
                            raw = content_item.text
                            break
        
        data = parse_llm_json(raw, fallback={})
        struct = HeaderStructure.from_dict(data)
        return raw, struct
    
    # Try with all images first
    raw_response, structure = call_api(image_paths)
    structure = _enforce_unique_encounter_names(structure)
    
    # If result is empty and we have multiple images, try with later images only
    # (Early pages often contain SoA title/text, actual table is on later pages)
    if len(image_paths) > 3 and not structure.encounters:
        logger.info(f"Empty result with all images, retrying with later images only...")
        later_images = image_paths[len(image_paths)//2:]  # Use second half of images
        raw_response, structure = call_api(later_images)
        structure = _enforce_unique_encounter_names(structure)
        
        # If still empty, try middle images
        if not structure.encounters and len(image_paths) > 4:
            logger.info(f"Still empty, trying middle images...")
            mid_start = len(image_paths) // 3
            mid_end = 2 * len(image_paths) // 3
            mid_images = image_paths[mid_start:mid_end]
            raw_response, structure = call_api(mid_images)
            structure = _enforce_unique_encounter_names(structure)
    
    return HeaderAnalysisResult(
        structure=structure,
        raw_response=raw_response,
        model_used=model_name,
        image_count=len(image_paths),
        success=True
    )


def _analyze_with_claude(
    image_paths: List[str], 
    model_name: str, 
    prompt: str
) -> HeaderAnalysisResult:
    """Analyze using Anthropic Claude API with vision."""
    import anthropic
    import os
    
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY or CLAUDE_API_KEY not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    def call_api(images: List[str]) -> Tuple[str, HeaderStructure]:
        """Make API call with given images using Claude."""
        # Build message content with images
        content = []
        
        # Add images first
        for img_path in images:
            with open(img_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_data
                }
            })
        
        # Add text prompt
        content.append({
            "type": "text",
            "text": prompt
        })
        
        # Add JSON mode instruction to system
        system = "You must respond with valid JSON only. No markdown code blocks, no explanation, just the JSON object."
        
        response = client.messages.create(
            model=model_name,
            max_tokens=8192,  # Increased from 4096 to capture all footnotes (a-x)
            system=system,
            messages=[{"role": "user", "content": content}]
        )
        
        # Extract content from response
        raw = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    raw = block.text
                    break
        
        data = parse_llm_json(raw, fallback={})
        struct = HeaderStructure.from_dict(data)
        return raw, struct
    
    # Try with all images first
    raw_response, structure = call_api(image_paths)
    structure = _enforce_unique_encounter_names(structure)
    
    # If result is empty and we have multiple images, try with later images only
    if len(image_paths) > 3 and not structure.encounters:
        logger.info(f"Empty result with all images, retrying with later images only...")
        later_images = image_paths[len(image_paths)//2:]
        raw_response, structure = call_api(later_images)
        structure = _enforce_unique_encounter_names(structure)
        
        # If still empty, try middle images
        if not structure.encounters and len(image_paths) > 4:
            logger.info(f"Still empty, trying middle images...")
            mid_start = len(image_paths) // 3
            mid_end = 2 * len(image_paths) // 3
            mid_images = image_paths[mid_start:mid_end]
            raw_response, structure = call_api(mid_images)
            structure = _enforce_unique_encounter_names(structure)
    
    return HeaderAnalysisResult(
        structure=structure,
        raw_response=raw_response,
        model_used=model_name,
        image_count=len(image_paths),
        success=True
    )


def _enforce_unique_encounter_names(structure: HeaderStructure) -> HeaderStructure:
    """
    Post-process to ensure all encounter names are unique.
    If duplicates are found, append sequential numbers.
    
    Args:
        structure: HeaderStructure to process
        
    Returns:
        HeaderStructure with unique encounter names
    """
    if not structure or not structure.encounters:
        return structure
    
    # Count name occurrences
    name_counts = {}
    for enc in structure.encounters:
        name = enc.name
        name_counts[name] = name_counts.get(name, 0) + 1
    
    # Check if any duplicates exist
    has_duplicates = any(count > 1 for count in name_counts.values())
    if not has_duplicates:
        return structure
    
    logger.warning(f"Found duplicate encounter names, adding sequence numbers: {[n for n, c in name_counts.items() if c > 1]}")
    
    # Build epoch lookup for context
    epoch_map = {e.id: e.name for e in structure.epochs} if structure.epochs else {}
    
    # Assign unique names by appending sequential numbers
    name_seq = {}
    for enc in structure.encounters:
        original_name = enc.name
        if name_counts[original_name] > 1:
            seq = name_seq.get(original_name, 1)
            name_seq[original_name] = seq + 1
            
            # Try to create a meaningful name with epoch context
            epoch_name = epoch_map.get(enc.epochId, "")
            if epoch_name and epoch_name != original_name:
                enc.name = f"{epoch_name} - Column {seq}"
            else:
                enc.name = f"{original_name} (Column {seq})"
    
    # Also update matching plannedTimepoints
    if structure.plannedTimepoints:
        enc_name_map = {e.id: e.name for e in structure.encounters}
        for pt in structure.plannedTimepoints:
            if pt.encounterId and pt.encounterId in enc_name_map:
                # Keep timepoint name in sync with encounter if they matched
                enc_name = enc_name_map[pt.encounterId]
                if pt.name == original_name or not pt.name:
                    pt.name = enc_name
    
    return structure


def save_header_structure(structure: HeaderStructure, output_path: str) -> None:
    """
    Save header structure to JSON file.
    
    Args:
        structure: HeaderStructure to save
        output_path: Path to output JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info(f"Saved header structure to {output_path}")


def load_header_structure(input_path: str) -> HeaderStructure:
    """
    Load header structure from JSON file.
    
    Args:
        input_path: Path to input JSON file
        
    Returns:
        Loaded HeaderStructure
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return HeaderStructure.from_dict(data)
