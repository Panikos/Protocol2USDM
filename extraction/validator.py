"""
Validator - Vision-based validation of text extraction.

This module validates text extraction results against SoA images:
- Confirms tick marks are actually present in images
- Flags potential hallucinations (ticks that may not exist)
- Detects missed ticks (visible in image but not in text extraction)

This REPLACES the complex reconciliation logic with simple validation.
Text extraction is the source of truth; vision validates it.

Usage:
    from extraction.validator import validate_extraction
    
    validation = validate_extraction(
        text_result, 
        header_structure,
        image_paths,
        model_name="gemini-2.5-pro"
    )
    
    if validation.issues:
        print(f"Found {len(validation.issues)} potential issues")
"""

import json
import base64
import logging
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json
from core.usdm_types import HeaderStructure, ActivityTimepoint
from core.provenance import ProvenanceTracker, ProvenanceSource
from llm_providers import usage_tracker

logger = logging.getLogger(__name__)


class IssueType(Enum):
    """Types of validation issues."""
    POSSIBLE_HALLUCINATION = "possible_hallucination"  # Tick in text, not visible in image
    MISSED_TICK = "missed_tick"                        # Visible in image, not in text
    UNCERTAIN = "uncertain"                            # Could not determine


@dataclass
class ValidationIssue:
    """A single validation issue."""
    issue_type: IssueType
    activity_id: str
    activity_name: str
    timepoint_id: str
    timepoint_name: str
    confidence: float  # 0-1, how confident we are this is an issue
    details: str
    
    def to_dict(self):
        return {
            'issue_type': self.issue_type.value,
            'activity_id': self.activity_id,
            'activity_name': self.activity_name,
            'timepoint_id': self.timepoint_id,
            'timepoint_name': self.timepoint_name,
            'confidence': self.confidence,
            'details': self.details,
        }


@dataclass
class ValidationResult:
    """Result of validation."""
    success: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    confirmed_ticks: int = 0
    total_ticks_checked: int = 0
    model_used: str = ""
    raw_response: str = ""
    error: Optional[str] = None
    
    @property
    def hallucination_count(self) -> int:
        return sum(1 for i in self.issues if i.issue_type == IssueType.POSSIBLE_HALLUCINATION)
    
    @property
    def missed_count(self) -> int:
        return sum(1 for i in self.issues if i.issue_type == IssueType.MISSED_TICK)
    
    def to_dict(self):
        return {
            'success': self.success,
            'issues': [i.to_dict() for i in self.issues],
            'confirmed_ticks': self.confirmed_ticks,
            'total_ticks_checked': self.total_ticks_checked,
            'hallucination_count': self.hallucination_count,
            'missed_count': self.missed_count,
            'model_used': self.model_used,
            'error': self.error,
        }


VALIDATION_PROMPT = """You are validating a Schedule of Activities (SoA) extraction.

I will provide:
1. A list of activities with their IDs
2. A list of timepoints with their IDs  
3. A list of activity-timepoint ticks (from text extraction)
4. Image(s) of the actual SoA table

Your task is to verify each tick by checking if it's visible in the image.

ACTIVITIES:
{activities_json}

TIMEPOINTS:
{timepoints_json}

TICKS TO VERIFY:
{ticks_json}

{context_section}

For each tick, check if you can see a mark (X, ✓, •, or similar) in the corresponding cell.

OUTPUT FORMAT:
Return a JSON object:
{{
  "verified_ticks": [
    {{"activity_id": "act_1", "timepoint_id": "pt_1", "visible": true, "confidence": 0.95}},
    {{"activity_id": "act_2", "timepoint_id": "pt_3", "visible": false, "confidence": 0.8, "reason": "Cell appears empty"}}
  ],
  "possible_missed_ticks": [
    {{"activity_id": "act_5", "timepoint_id": "pt_2", "confidence": 0.7, "reason": "Visible mark not in provided list"}}
  ]
}}

CRITICAL RULES:
- You MUST include BOTH activity_id AND timepoint_id for EVERY tick
- Use the EXACT IDs provided (act_*, pt_*)
- Set visible=true if you can see a tick mark in that cell
- Set visible=false if the cell appears empty
- Confidence should reflect your certainty (0-1)
- Only report missed_ticks if you're reasonably confident (>0.6)
- Focus on accuracy over completeness

Output ONLY the JSON object."""

# Context section for additional inference help
CONTEXT_SECTION_TEMPLATE = """
ADDITIONAL CONTEXT (use when uncertain):
Footnotes from the SoA table:
{footnotes}

Use footnotes to understand conditional ticks (marked with a, b, c or *, †, ‡).
"""


def validate_extraction(
    text_activities: List[dict],
    text_ticks: List[dict],
    header_structure: HeaderStructure,
    image_paths: List[str],
    model_name: str = "gemini-2.5-pro",
    protocol_text: str = "",
    footnotes: str = "",
) -> ValidationResult:
    """
    Validate text extraction against SoA images.
    
    Args:
        text_activities: Activities from text extraction
        text_ticks: ActivityTimepoints from text extraction
        header_structure: Header structure with timepoint info
        image_paths: Paths to SoA table images
        model_name: Vision model to use
        protocol_text: Full protocol text for context (optional, unused)
        footnotes: SoA footnotes for context (optional)
        
    Returns:
        ValidationResult with issues found
    """
    logger.info(f"Validating {len(text_ticks)} ticks against {len(image_paths)} images")
    
    if not image_paths:
        return ValidationResult(
            success=False,
            error="No images provided for validation"
        )
    
    if not text_ticks:
        return ValidationResult(
            success=True,
            confirmed_ticks=0,
            total_ticks_checked=0,
            model_used=model_name,
        )
    
    try:
        # Build activity and timepoint lookup
        activity_names = {a.get('id'): a.get('name', '') for a in text_activities}
        tp_names = {pt.id: pt.name for pt in header_structure.plannedTimepoints}
        
        # Build prompt with data
        activities_json = json.dumps(
            [{'id': a.get('id'), 'name': a.get('name')} for a in text_activities],
            indent=2
        )
        timepoints_json = json.dumps(
            [{'id': pt.id, 'name': pt.name, 'valueLabel': pt.valueLabel} 
             for pt in header_structure.plannedTimepoints],
            indent=2
        )
        ticks_json = json.dumps(
            [{'activity_id': t.get('activityId'), 
              'timepoint_id': t.get('plannedTimepointId') or t.get('encounterId')} 
             for t in text_ticks],
            indent=2
        )
        
        # Build context section if we have footnotes
        context_section = ""
        if footnotes:
            context_section = CONTEXT_SECTION_TEMPLATE.format(footnotes=footnotes)
        
        prompt = VALIDATION_PROMPT.format(
            activities_json=activities_json,
            timepoints_json=timepoints_json,
            ticks_json=ticks_json,
            context_section=context_section,
        )
        
        # Call vision model
        if 'gemini' in model_name.lower():
            result = _validate_with_gemini(prompt, image_paths, model_name)
        elif 'claude' in model_name.lower():
            result = _validate_with_claude(prompt, image_paths, model_name)
        else:
            result = _validate_with_openai(prompt, image_paths, model_name)
        
        # Parse results into issues
        issues = []
        confirmed = 0
        
        data = parse_llm_json(result['response'], fallback={})
        
        for tick in data.get('verified_ticks', []):
            if tick.get('visible', True):
                confirmed += 1
            else:
                # Potential hallucination
                act_id = tick.get('activity_id', '')
                tp_id = tick.get('timepoint_id', '')
                issues.append(ValidationIssue(
                    issue_type=IssueType.POSSIBLE_HALLUCINATION,
                    activity_id=act_id,
                    activity_name=activity_names.get(act_id, ''),
                    timepoint_id=tp_id,
                    timepoint_name=tp_names.get(tp_id, ''),
                    confidence=tick.get('confidence', 0.5),
                    details=tick.get('reason', 'Tick not visible in image'),
                ))
        
        for missed in data.get('possible_missed_ticks', []):
            act_id = missed.get('activity_id', '')
            tp_id = missed.get('timepoint_id', '')
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSED_TICK,
                activity_id=act_id,
                activity_name=activity_names.get(act_id, ''),
                timepoint_id=tp_id,
                timepoint_name=tp_names.get(tp_id, ''),
                confidence=missed.get('confidence', 0.5),
                details=missed.get('reason', 'Visible in image but not in text'),
            ))
        
        return ValidationResult(
            success=True,
            issues=issues,
            confirmed_ticks=confirmed,
            total_ticks_checked=len(text_ticks),
            model_used=model_name,
            raw_response=result['response'],
        )
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return ValidationResult(
            success=False,
            error=str(e),
            model_used=model_name,
        )


def _validate_with_gemini(prompt: str, image_paths: List[str], model_name: str) -> dict:
    """Run validation with Gemini via llm_providers for consistent retry/config handling."""
    from PIL import Image
    import io
    import os
    import time
    
    # Check if this is a Gemini 3 model that requires google-genai SDK
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
    
    # Retry configuration for rate limits
    max_retries = 3
    initial_backoff = 5
    
    for attempt in range(max_retries + 1):
        try:
            if is_gemini3:
                # Use google-genai SDK for Gemini 3 with thinking disabled
                try:
                    from google import genai as genai_new
                    from google.genai import types as genai_types
                    
                    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                    client = genai_new.Client(
                        vertexai=True,
                        project=project,
                        location='global',
                    )
                    
                    # Build content parts for vision
                    content_parts = [prompt]
                    for img_part in image_parts:
                        content_parts.append(genai_types.Part.from_bytes(
                            data=base64.b64decode(img_part['data']),
                            mime_type=img_part['mime_type']
                        ))
                    
                    # Config with thinking disabled
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
                    return {'response': response.text or ""}
                    
                except ImportError:
                    logger.warning("google-genai SDK not available, falling back to AI Studio")
                    is_gemini3 = False  # Fall through to AI Studio path
            
            # Standard AI Studio path for non-Gemini-3 models
            import google.generativeai as genai
            
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not set")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            content_parts = [prompt]
            for img_part in image_parts:
                content_parts.append({
                    'inline_data': img_part
                })
            
            response = model.generate_content(
                content_parts,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            # Track token usage
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                usage_tracker.add_usage(input_tokens, output_tokens)
            return {'response': response.text or ""}
            
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = '429' in error_str or 'rate' in error_str or 'exhausted' in error_str or 'quota' in error_str
            
            if is_rate_limit and attempt < max_retries:
                wait_time = min(initial_backoff * (2 ** attempt), 60)
                logger.warning(f"Rate limit in validation, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait_time)
            else:
                raise


def _validate_with_openai(prompt: str, image_paths: List[str], model_name: str) -> dict:
    """Run validation with OpenAI Responses API."""
    from openai import OpenAI
    import os
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    
    # Build input content for Responses API - use input_text and input_image types
    input_content = [{"type": "input_text", "text": prompt}]
    
    for img_path in image_paths:
        with open(img_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        input_content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{data}"
        })
    
    # Handle reasoning models differently
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
    
    return {'response': result}


def _validate_with_claude(prompt: str, image_paths: List[str], model_name: str) -> dict:
    """Run validation with Anthropic Claude API."""
    import anthropic
    import os
    
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY or CLAUDE_API_KEY not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Build message content with images
    content = []
    
    # Add images first
    for img_path in image_paths:
        with open(img_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": data
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
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": content}]
    )
    
    # Extract content from response
    result = ""
    if response.content:
        for block in response.content:
            if hasattr(block, 'text'):
                result = block.text
                break
    
    return {'response': result}


def apply_validation_fixes(
    text_ticks: List[dict],
    validation: ValidationResult,
    remove_hallucinations: bool = False,
    add_missed: bool = False,
    confidence_threshold: float = 0.7,
) -> Tuple[List[dict], ProvenanceTracker]:
    """
    Apply validation fixes to the tick list.
    
    Args:
        text_ticks: Original ticks from text extraction
        validation: Validation result
        remove_hallucinations: Remove ticks flagged as hallucinations (default False to keep all)
        add_missed: Add ticks that were missed
        confidence_threshold: Only act on issues above this confidence
        
    Returns:
        Tuple of (fixed_ticks, provenance_tracker)
    """
    provenance = ProvenanceTracker()
    fixed_ticks = text_ticks.copy()
    
    # Identify possible hallucinations (text found, vision didn't confirm)
    hallucination_keys = {
        (i.activity_id, i.timepoint_id)
        for i in validation.issues
        if i.issue_type == IssueType.POSSIBLE_HALLUCINATION
        and i.confidence >= confidence_threshold
    }
    
    # Helper to get timepoint ID from tick (handles both legacy and v4.0 formats)
    def get_tp_id(tick):
        return tick.get('plannedTimepointId') or tick.get('encounterId')
    
    if remove_hallucinations:
        # Remove hallucinations from output
        fixed_ticks = [
            t for t in fixed_ticks
            if (t.get('activityId'), get_tp_id(t)) not in hallucination_keys
        ]
        logger.info(f"Removed {len(hallucination_keys)} probable hallucinations")
        
        # Tag remaining ticks as confirmed (both sources agree)
        provenance.tag_cells_from_timepoints(fixed_ticks, ProvenanceSource.BOTH)
    else:
        # Keep all ticks but tag appropriately based on validation
        confirmed_ticks = []
        unconfirmed_ticks = []
        
        for tick in fixed_ticks:
            key = (tick.get('activityId'), get_tp_id(tick))
            if key in hallucination_keys:
                unconfirmed_ticks.append(tick)
            else:
                confirmed_ticks.append(tick)
        
        # Tag confirmed ticks as BOTH (text + vision agree)
        provenance.tag_cells_from_timepoints(confirmed_ticks, ProvenanceSource.BOTH)
        
        # Tag unconfirmed ticks as TEXT (text found, vision didn't confirm)
        # These stay as TEXT (not overwritten) to indicate they need review
        # Note: They were already tagged as TEXT during text extraction
        logger.info(f"Kept {len(unconfirmed_ticks)} unconfirmed ticks (text-only, marked for review)")
        logger.info(f"Confirmed {len(confirmed_ticks)} ticks (text + vision agree)")
    
    return fixed_ticks, provenance


def save_validation_result(validation: ValidationResult, output_path: str) -> None:
    """Save validation result to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(validation.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info(f"Saved validation result to {output_path}")
