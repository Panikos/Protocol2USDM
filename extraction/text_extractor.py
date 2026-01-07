"""
Text Extractor - Text-based SoA data extraction.

This module extracts the DATA from protocol text:
- Activities (procedures, assessments) with full details
- ActivityTimepoints (the tick matrix)

It uses the HeaderStructure from vision analysis as an ANCHOR:
- Uses the EXACT IDs from header structure for timepoints/encounters
- Maps activities to the correct timepoints using those IDs
- Prevents ID mismatches between vision and text

This is the PRIMARY data source. Vision provides structure, text provides data.

Usage:
    from extraction.text_extractor import extract_soa_from_text
    from extraction.header_analyzer import load_header_structure
    
    header = load_header_structure("4_soa_header_structure.json")
    result = extract_soa_from_text(protocol_text, header, model_name="gemini-2.5-pro")
"""

import json
import logging
from typing import Optional, List
from dataclasses import dataclass

from core.llm_client import get_llm_client, LLMConfig
from core.json_utils import parse_llm_json
from core.usdm_types import (
    HeaderStructure, Timeline, Activity, ActivityTimepoint,
    create_wrapper_input
)
from core.provenance import ProvenanceTracker, ProvenanceSource
from core.constants import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION

logger = logging.getLogger(__name__)

MAX_EXTRACTION_RETRIES = 2  # Retry if response format is invalid


def validate_extraction_response(data: dict, min_activities: int = 1) -> tuple[bool, str]:
    """
    Validate that LLM response has expected structure.
    
    Returns:
        (is_valid, error_message)
    """
    # Check for required top-level keys
    if 'activities' not in data:
        # Check if model returned nested USDM structure instead
        if 'study' in data or 'studyDesigns' in data or 'activityGroups' in data:
            return False, "Response has wrong structure (nested USDM format instead of flat {activities, activityTimepoints})"
        return False, "Missing 'activities' key in response"
    
    if not isinstance(data.get('activities'), list):
        return False, "'activities' must be an array"
    
    activities = data.get('activities', [])
    
    # Check minimum activities
    if len(activities) < min_activities:
        return False, f"Expected at least {min_activities} activities, got {len(activities)}"
    
    # Validate activity structure
    for i, act in enumerate(activities):
        if not isinstance(act, dict):
            return False, f"Activity {i} is not an object"
        if 'id' not in act:
            return False, f"Activity {i} missing 'id'"
        if 'name' not in act:
            return False, f"Activity {i} missing 'name'"
    
    # Check activityTimepoints if present
    timepoints = data.get('activityTimepoints', [])
    if not isinstance(timepoints, list):
        return False, "'activityTimepoints' must be an array"
    
    return True, ""


def build_extraction_prompt(header_structure: HeaderStructure) -> str:
    """
    Build the text extraction prompt with embedded header structure.
    
    The header structure provides:
    - Exact IDs to use for timepoints and encounters
    - Column structure (which visits exist)
    - Row groups (how activities should be grouped)
    
    Output format follows USDM v4.0 OpenAPI schema requirements.
    """
    header_json = json.dumps(header_structure.to_dict(), indent=2)
    
    # Build a clear list of group names and their activities for the LLM
    group_lines = []
    for g in header_structure.activityGroups:
        activity_names = getattr(g, 'activity_names', []) or []
        if activity_names:
            # Show group with its expected activities (from header analyzer)
            activities_str = ", ".join(f'"{a}"' for a in activity_names[:5])
            if len(activity_names) > 5:
                activities_str += f" ... (+{len(activity_names) - 5} more)"
            group_lines.append(f"  - `{g.id}`: \"{g.name}\" → activities: [{activities_str}]")
        else:
            group_lines.append(f"  - `{g.id}`: \"{g.name}\"")
    
    group_list = "\n".join(group_lines) if group_lines else "  (No groups detected)"
    
    return f"""You are extracting Schedule of Activities (SoA) data from a clinical trial protocol.
Your output must conform to USDM v4.0 schema specifications.

## HEADER STRUCTURE (from visual analysis)
The following structure has been extracted from the SoA table images. 
You MUST use these EXACT IDs when referencing timepoints and encounters.

```json
{header_json}
```

## ACTIVITY GROUPS (row section headers)
The following activity groups (section headers) were identified in the SoA table:
{group_list}

**IMPORTANT:** If activity names are shown after "→ activities:", these are the expected activities
under that group (detected visually). Use this as a HINT for assigning `activityGroupId`.

These are CATEGORY HEADERS that group related activities. They are typically:
- Bold or highlighted rows
- Spanning the full table width
- Have NO tick marks (they are headers, not activities)

## YOUR TASK
Extract the ACTIVITIES and TICK MATRIX from the protocol text.

For each activity row in the SoA table:
1. Extract the activity name and description  
2. Assign it to its parent group using `activityGroupId`
3. Identify which timepoints have a tick (X, ✓, or similar marker)
4. Create an ActivityTimepoint entry for EACH tick
5. **IMPORTANT**: If a tick has a superscript footnote reference (e.g., "X^a", "✓^m", "X^a,b"),
   capture the footnote letters in the `footnoteRefs` array (e.g., ["a"] or ["a", "b"])

## USDM v4.0 Output Format (MUST follow exactly)

Every entity MUST have `id` and `instanceType` fields.
Every activity MUST have `activityGroupId` linking it to its parent group.

```json
{{
  "activities": [
    {{
      "id": "act_1",
      "name": "Informed Consent",
      "description": "Obtain written informed consent from participant",
      "activityGroupId": "grp_1",
      "instanceType": "Activity"
    }},
    {{
      "id": "act_2",
      "name": "Physical Examination",
      "description": "Complete physical examination",
      "activityGroupId": "grp_2",
      "instanceType": "Activity"
    }},
    {{
      "id": "act_3",
      "name": "Blood Sampling for PK",
      "description": "PK blood samples",
      "activityGroupId": "grp_3",
      "instanceType": "Activity"
    }}
  ],
  "activityTimepoints": [
    {{
      "id": "at_1",
      "activityId": "act_1",
      "encounterId": "enc_1",
      "instanceType": "ActivityTimepoint"
    }},
    {{
      "id": "at_2",
      "activityId": "act_2",
      "encounterId": "enc_1",
      "footnoteRefs": ["a"],
      "instanceType": "ActivityTimepoint"
    }},
    {{
      "id": "at_3",
      "activityId": "act_3",
      "encounterId": "enc_2",
      "footnoteRefs": ["m", "n"],
      "instanceType": "ActivityTimepoint"
    }}
  ]
}}
```

## CRITICAL RULES

1. **Every entity MUST have `id` and `instanceType`** - mandatory for USDM compliance
2. **Use sequential IDs** - act_1, act_2 for activities; at_1, at_2 for timepoints
3. **Use EXACT encounter IDs from header structure** for encounterId (enc_1, enc_2, etc.) - do not create new ones
4. **ONLY create ActivityTimepoints where you see explicit tick marks** (X, ✓, •)
5. **Do NOT infer ticks** from clinical logic or "at every visit" text
6. **If unsure about a tick, OMIT it** - false negatives are better than false positives
7. **DO NOT include group headers as activities** - only extract the individual activities UNDER each group
8. **Include ALL activities** from the SoA table with their descriptions
9. **Every activity MUST have `activityGroupId`** - MANDATORY, see rules below

## HOW TO ASSIGN activityGroupId (MANDATORY)

Look at the header structure's rowGroups. Each activity belongs to the group whose header row appears ABOVE it in the table.

Example: If the header structure has:
- grp_1: "Eligibility" 
- grp_2: "Safety Assessments"
- grp_3: "PK/PD Analyses"

And the table shows:
```
Eligibility              <- group header (grp_1)
  Informed Consent       <- activityGroupId: "grp_1"
  Demographics           <- activityGroupId: "grp_1"
Safety Assessments       <- group header (grp_2)
  Vital Signs            <- activityGroupId: "grp_2"
  Physical Exam          <- activityGroupId: "grp_2"
PK/PD Analyses           <- group header (grp_3)
  Blood Sampling for PK  <- activityGroupId: "grp_3"
```

**If no groups exist, use "grp_default" for all activities.**

## Activity Fields
- `id`: Unique identifier (act_1, act_2, etc.)
- `name`: Activity name exactly as shown in SoA
- `description`: Expanded description if available (can be same as name)
- `activityGroupId`: The ID of the parent group (grp_1, grp_2, etc.) - REQUIRED
- `instanceType`: Must be "Activity"

## ActivityTimepoint Fields  
- `id`: Unique identifier (at_1, at_2, etc.)
- `activityId`: Reference to the activity (must match an activity's id)
- `encounterId`: Reference to encounter from header (enc_1, enc_2, etc.) - must match exactly
- `footnoteRefs`: (OPTIONAL) Array of footnote letters if the tick has superscript references
  - Example: "X^a" → `["a"]`, "✓^m,n" → `["m", "n"]`
  - Only include if superscript is present on the tick mark
- `instanceType`: Must be "ActivityTimepoint"

Output ONLY the JSON object, no explanations or markdown fences.

## STRICT FORMAT REQUIREMENTS

**YOUR OUTPUT MUST BE EXACTLY THIS STRUCTURE:**
```
{{
  "activities": [...],
  "activityTimepoints": [...]
}}
```

**DO NOT:**
- Wrap in "study", "studyDesigns", or any USDM container
- Use "activityGroups" with "activityNames" arrays
- Add any other top-level keys
- Return nested structures

**DO:**
- Return FLAT JSON with only "activities" and "activityTimepoints" at root
- Each activity must have: id, name, activityGroupId, instanceType
- Each timepoint must have: id, activityId, encounterId, instanceType"""


@dataclass
class TextExtractionResult:
    """Result of text-based SoA extraction."""
    activities: List[Activity]
    activity_timepoints: List[ActivityTimepoint]
    raw_response: str
    model_used: str
    success: bool
    provenance: ProvenanceTracker
    error: Optional[str] = None
    
    def to_timeline(self, header: HeaderStructure) -> Timeline:
        """Convert to Timeline by combining with header structure."""
        return Timeline(
            activities=self.activities,
            plannedTimepoints=header.plannedTimepoints,
            encounters=header.encounters,
            epochs=header.epochs,
            activityGroups=header.activityGroups,
            activityTimepoints=self.activity_timepoints,
        )


def extract_soa_from_text(
    protocol_text: str,
    header_structure: HeaderStructure,
    model_name: str = "gemini-2.5-pro",
    soa_pages: Optional[List[int]] = None,
) -> TextExtractionResult:
    """
    Extract SoA data from protocol text using header structure as anchor.
    
    Args:
        protocol_text: Full protocol text or SoA-specific text
        header_structure: Structure from vision analysis (provides IDs)
        model_name: LLM model to use
        soa_pages: Optional list of page numbers to focus on
        
    Returns:
        TextExtractionResult containing activities and ticks
        
    Example:
        >>> header = load_header_structure("header.json")
        >>> result = extract_soa_from_text(text, header)
        >>> print(f"Found {len(result.activities)} activities")
    """
    logger.info(f"Extracting SoA from text with {model_name}")
    
    provenance = ProvenanceTracker()
    provenance.metadata['model'] = model_name
    provenance.metadata['extraction_type'] = 'text'
    
    # Estimate minimum expected activities from header structure
    min_expected = max(1, len(header_structure.activityGroups) * 2)  # At least 2 per group
    
    try:
        # Build prompt with header structure embedded
        prompt = build_extraction_prompt(header_structure)
        
        # Get LLM client
        client = get_llm_client(model_name)
        
        # Build base messages
        base_messages = [
            {"role": "system", "content": "You are an expert in clinical trial protocols and CDISC USDM standards."},
            {"role": "user", "content": f"{prompt}\n\nPROTOCOL TEXT:\n\n{protocol_text}"}
        ]
        
        # Configure for JSON output
        config = LLMConfig(
            temperature=0.0,
            json_mode=True,
        )
        
        raw_response = ""
        data = {}
        last_error = ""
        
        # Retry loop with validation
        for attempt in range(MAX_EXTRACTION_RETRIES + 1):
            messages = base_messages.copy()
            
            # Add correction prompt on retry
            if attempt > 0 and last_error:
                logger.warning(f"  Retry {attempt}/{MAX_EXTRACTION_RETRIES}: {last_error}")
                correction = f"""Your previous response had an invalid format: {last_error}

REMINDER: You MUST return ONLY this structure:
{{
  "activities": [
    {{"id": "act_1", "name": "...", "activityGroupId": "grp_1", "instanceType": "Activity"}},
    ...
  ],
  "activityTimepoints": [
    {{"id": "at_1", "activityId": "act_1", "encounterId": "enc_1", "instanceType": "ActivityTimepoint"}},
    ...
  ]
}}

DO NOT wrap in "study" or any other container. Return FLAT JSON only."""
                messages.append({"role": "assistant", "content": raw_response[:500] + "..."})
                messages.append({"role": "user", "content": correction})
            
            # Generate response
            response = client.generate(messages, config)
            raw_response = response.content
            
            # Parse response
            data = parse_llm_json(raw_response, fallback={})
            
            # Validate response structure
            is_valid, error_msg = validate_extraction_response(data, min_activities=min_expected)
            
            if is_valid:
                logger.info(f"  Response validated on attempt {attempt + 1}")
                break
            else:
                last_error = error_msg
                if attempt == MAX_EXTRACTION_RETRIES:
                    logger.error(f"  Extraction failed validation after {MAX_EXTRACTION_RETRIES + 1} attempts: {error_msg}")
                    # Log what we got for debugging
                    logger.error(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        
        # Extract activities
        activities = [
            Activity.from_dict(a) for a in data.get('activities', [])
        ]
        
        # Safety filter: remove any activities matching group header names
        group_names = {g.name.lower() for g in header_structure.activityGroups}
        logger.debug(f"  Filter check: {len(header_structure.activityGroups)} groups, group_names={group_names}")
        original_count = len(activities)
        activities = [a for a in activities if a.name.lower() not in group_names]
        if len(activities) < original_count:
            removed = original_count - len(activities)
            logger.info(f"  Filtered out {removed} group headers that were incorrectly extracted as activities")
        elif group_names:
            logger.debug(f"  No group headers filtered (0 matches from {len(group_names)} group names)")
        
        # Extract activity timepoints
        activity_timepoints = [
            ActivityTimepoint.from_dict(at) for at in data.get('activityTimepoints', [])
        ]
        
        # Tag provenance
        provenance.tag_entities('activities', [a.to_dict() for a in activities], ProvenanceSource.TEXT)
        provenance.tag_cells_from_timepoints(
            [at.to_dict() for at in activity_timepoints], 
            ProvenanceSource.TEXT
        )
        
        logger.info(f"Extracted {len(activities)} activities, {len(activity_timepoints)} ticks")
        
        # Determine success based on validation
        extraction_success = len(activities) >= min_expected
        if not extraction_success:
            logger.warning(f"  Extraction returned fewer activities ({len(activities)}) than expected ({min_expected})")
        
        return TextExtractionResult(
            activities=activities,
            activity_timepoints=activity_timepoints,
            raw_response=raw_response,
            model_used=model_name,
            success=extraction_success,
            provenance=provenance,
            error=last_error if not extraction_success else None,
        )
        
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return TextExtractionResult(
            activities=[],
            activity_timepoints=[],
            raw_response="",
            model_used=model_name,
            success=False,
            provenance=provenance,
            error=str(e),
        )


def build_usdm_output(
    extraction_result: TextExtractionResult,
    header_structure: HeaderStructure,
) -> dict:
    """
    Build complete USDM Wrapper-Input JSON from extraction results.
    
    Combines:
    - Structure from header analysis (epochs, encounters, timepoints, groups)
    - Data from text extraction (activities, ticks)
    
    Args:
        extraction_result: Result from text extraction
        header_structure: Structure from header analysis
        
    Returns:
        Complete USDM Wrapper-Input dict
    """
    timeline = extraction_result.to_timeline(header_structure)
    
    return create_wrapper_input(
        timeline=timeline,
        usdm_version=USDM_VERSION,
        system_name=SYSTEM_NAME,
        system_version=SYSTEM_VERSION,
    )


def save_extraction_result(
    result: TextExtractionResult,
    header: HeaderStructure,
    output_path: str,
    provenance_path: Optional[str] = None,
) -> None:
    """
    Save extraction result to USDM JSON file.
    
    Args:
        result: Extraction result
        header: Header structure to combine with
        output_path: Path for USDM JSON output
        provenance_path: Optional path for provenance JSON (separate file)
    """
    # Build and save USDM output
    usdm_output = build_usdm_output(result, header)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(usdm_output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved USDM output to {output_path}")
    
    # Save provenance separately if path provided
    if provenance_path:
        result.provenance.save(provenance_path)
        logger.info(f"Saved provenance to {provenance_path}")
