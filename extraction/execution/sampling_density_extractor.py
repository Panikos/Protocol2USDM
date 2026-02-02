"""
Sampling Density Extractor

Extracts minimum observation requirements for study activities:
- PK/PD sampling schedules with timepoints
- Minimum samples per visit/window
- Dense sampling windows (intensive periods)
- Sparse sampling specifications
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .schema import (
    SamplingConstraint,
    ExecutionModelResult,
    ExecutionModelData,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Patterns for Sampling Density Detection
# =============================================================================

# PK sampling patterns with timepoints
PK_SAMPLING_PATTERNS = [
    # "0, 5, 10, 15, 30, 60, 120 minutes"
    (r'(?:PK|pharmacokinetic|blood)\s*(?:sampling|samples?)?\s*(?:at|:)?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:min(?:utes?)?|h(?:ours?)?)', 0.9),
    # "Predose, 5, 10, 15, 20, 25, 30 min"
    (r'(?:predose|pre-dose|baseline)\s*,?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:min(?:utes?)?|h(?:ours?)?)', 0.85),
    # "sampling at time 0, 0.25, 0.5, 1, 2, 4, 6, 8, 12, 24 hours"
    (r'(?:sampling|samples?)\s*(?:at)?\s*(?:time)?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:h(?:ours?)?|min(?:utes?)?)', 0.85),
]

# FIX D: PD/Glucose sampling patterns with timepoints
PD_GLUCOSE_PATTERNS = [
    # "plasma glucose at 0, 5, 10, 15, 20, 25, 30 minutes"
    (r'(?:plasma\s+)?glucose\s*(?:sampling|samples?|measurements?)?\s*(?:at|:)?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:min(?:utes?)?)', 0.9),
    # "PD sampling", "pharmacodynamic sampling"
    (r'(?:PD|pharmacodynamic)\s*(?:sampling|samples?)\s*(?:at|:)?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:min(?:utes?)?)', 0.9),
    # "glucose measured at times 0, 5, 10..."
    (r'glucose\s*(?:measured|collected)\s*(?:at)?\s*(?:times?)?\s*((?:\d+(?:\.\d+)?(?:\s*,\s*)?)+)\s*(?:min(?:utes?)?)', 0.85),
    # "bedside glucose monitoring"
    (r'bedside\s*(?:plasma\s+)?glucose\s*(?:monitoring)?', 0.8),
]

# Endpoint-linked sampling patterns (for nadir/success windows)
ENDPOINT_SAMPLING_PATTERNS = [
    # "nadir within 30 minutes"
    (r'nadir\s*(?:within|in|during)?\s*(\d+)\s*(?:min(?:utes?)?)', 0.9),
    # "treatment success" + "30 minutes"
    (r'treatment\s*success.*?(\d+)\s*(?:min(?:utes?)?)', 0.85),
    # "increase in PG to >70 mg/dl"
    (r'increase\s*(?:in)?\s*(?:PG|plasma\s*glucose).*?(\d+)\s*(?:min(?:utes?)?)', 0.85),
]

# Minimum sample count patterns
MIN_SAMPLE_PATTERNS = [
    # "minimum of 5 samples"
    (r'minimum\s*(?:of)?\s*(\d+)\s*(?:samples?|observations?|measurements?)', 0.9),
    # "at least 3 samples per window"
    (r'at\s*least\s*(\d+)\s*(?:samples?|observations?)\s*(?:per|each)\s*(?:window|period|visit)', 0.9),
    # "no fewer than 5 observations"
    (r'no\s*fewer\s*than\s*(\d+)\s*(?:samples?|observations?)', 0.85),
    # "≥ 3 samples required"
    (r'[≥>=]\s*(\d+)\s*(?:samples?|observations?)\s*(?:required|necessary)', 0.85),
]

# Dense/intensive sampling patterns
DENSE_SAMPLING_PATTERNS = [
    # "intensive PK sampling"
    (r'intensive\s*(?:PK|pharmacokinetic)?\s*sampling', 0.85),
    # "dense sampling window"
    (r'dense\s*sampling\s*(?:window|period)?', 0.85),
    # "serial blood sampling"
    (r'serial\s*(?:blood)?\s*sampling', 0.8),
    # "frequent sampling"
    (r'frequent\s*sampling', 0.75),
]

# Sparse sampling patterns
SPARSE_SAMPLING_PATTERNS = [
    # "sparse sampling design"
    (r'sparse\s*sampling\s*(?:design|approach)?', 0.85),
    # "population PK sampling"
    (r'population\s*(?:PK|pharmacokinetic)\s*(?:sampling)?', 0.8),
    # "limited sampling"
    (r'limited\s*sampling', 0.75),
]

# Window/period duration patterns
WINDOW_DURATION_PATTERNS = [
    # "over 24 hours"
    (r'over\s*(\d+)\s*(hours?|h|minutes?|min|days?|d)', 0.8),
    # "within 4 hours"
    (r'within\s*(\d+)\s*(hours?|h|minutes?|min)', 0.8),
    # "during the first 6 hours"
    (r'during\s*(?:the)?\s*(?:first)?\s*(\d+)\s*(hours?|h|minutes?|min)', 0.8),
]

# Keywords for page detection
SAMPLING_KEYWORDS = [
    "pharmacokinetic", "PK sampling", "blood sampling", "sample collection",
    "sampling schedule", "timepoints", "predose", "postdose",
    "intensive sampling", "sparse sampling", "serial samples",
    "minimum samples", "sampling window", "PK/PD", "bioanalytical",
]


@dataclass
class DenseSamplingWindow:
    """Represents an intensive/dense sampling period."""
    id: str
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: Optional[str] = None  # ISO 8601
    timepoints: List[str] = field(default_factory=list)
    num_samples: int = 0
    activity_type: str = "PK"  # PK, PD, biomarker
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "duration": self.duration,
            "timepoints": self.timepoints,
            "numSamples": self.num_samples,
            "activityType": self.activity_type,
            "sourceText": self.source_text,
        }


def extract_sampling_density(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
) -> ExecutionModelResult:
    """
    Extract sampling density requirements from a protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model for enhancement
        use_llm: Whether to use LLM
        
    Returns:
        ExecutionModelResult with SamplingConstraints
    """
    logger.info("Starting sampling density extraction...")
    
    # Find relevant pages
    pages = _find_sampling_pages(pdf_path)
    if not pages:
        logger.info("No sampling pages found, searching full document")
        pages = list(range(1, 81))  # First 80 pages
    
    logger.info(f"Found {len(pages)} potential sampling pages")
    
    # Extract text from pages
    text = _extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            data=ExecutionModelData(),
            error="Could not extract text from PDF",
            pages_used=[],
            model_used=model,
        )
    
    # Extract sampling constraints
    constraints = []
    dense_windows = []
    
    # Detect PK sampling schedules
    pk_constraints = _detect_pk_sampling(text)
    constraints.extend(pk_constraints)
    
    # FIX D: Detect PD glucose sampling schedules
    pd_constraints = _detect_pd_glucose_sampling(text)
    constraints.extend(pd_constraints)
    logger.info(f"  Detected {len(pd_constraints)} PD glucose sampling constraints")
    
    # Detect minimum sample requirements
    min_constraints = _detect_minimum_samples(text)
    constraints.extend(min_constraints)
    
    # Detect dense sampling windows
    dense_windows = _detect_dense_windows(text)
    
    # Detect sparse sampling
    sparse_info = _detect_sparse_sampling(text)
    
    # LLM enhancement if requested
    if use_llm and (constraints or dense_windows):
        try:
            llm_result = _enhance_with_llm(text, constraints, dense_windows, model)
            if llm_result:
                constraints = llm_result.get('constraints', constraints)
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
    
    # Deduplicate constraints
    unique_constraints = _deduplicate_constraints(constraints)
    
    # Build result
    data = ExecutionModelData(
        sampling_constraints=unique_constraints,
    )
    
    # Add dense windows to extension data if needed
    if dense_windows:
        # Store dense windows info (could be added to schema later)
        pass
    
    # SamplingConstraint doesn't have confidence, use fixed value based on detection
    avg_confidence = 0.75 if unique_constraints else 0.0
    
    result = ExecutionModelResult(
        success=len(unique_constraints) > 0,
        data=data,
        pages_used=pages[:20],  # Limit pages reported
        model_used=model if use_llm else "heuristic",
    )
    
    logger.info(f"Extracted {len(unique_constraints)} sampling constraints, {len(dense_windows)} dense windows")
    
    return result


def _find_sampling_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain sampling information."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num in range(min(len(doc), 100)):
            page = doc[page_num]
            text = page.get_text().lower()
            
            # Check for sampling keywords
            score = sum(1 for kw in SAMPLING_KEYWORDS if kw.lower() in text)
            if score >= 2:
                pages.append(page_num + 1)
        
        doc.close()
        return pages
        
    except Exception as e:
        logger.warning(f"Error finding sampling pages: {e}")
        return []


def _extract_text_from_pages(pdf_path: str, pages: List[int]) -> str:
    """Extract text from specified pages."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num in pages:
            if page_num <= len(doc):
                page = doc[page_num - 1]
                text_parts.append(page.get_text())
        
        doc.close()
        return "\n".join(text_parts)
        
    except Exception as e:
        logger.warning(f"Error extracting text: {e}")
        return ""


def _detect_pk_sampling(text: str) -> List[SamplingConstraint]:
    """Detect PK sampling schedules with timepoints."""
    constraints = []
    
    for pattern, confidence in PK_SAMPLING_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            timepoints_str = match.group(1)
            timepoints = re.findall(r'(\d+(?:\.\d+)?)', timepoints_str)
            
            if len(timepoints) >= 3:  # At least 3 timepoints
                # Determine time unit
                full_match = match.group()
                if 'hour' in full_match.lower() or ' h' in full_match.lower():
                    unit = "hours"
                else:
                    unit = "minutes"
                
                constraints.append(SamplingConstraint(
                    id=f"pk_sampling_{len(constraints)+1}",
                    activity_id="PK_Blood_Sampling",
                    min_per_window=len(timepoints),
                    window_duration=_estimate_window_duration(timepoints, unit),
                    timepoints=[f"{t} {unit}" for t in timepoints],
                    source_text=match.group()[:200],
                ))
    
    return constraints


def _detect_minimum_samples(text: str) -> List[SamplingConstraint]:
    """Detect minimum sample count requirements."""
    constraints = []
    
    for pattern, confidence in MIN_SAMPLE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            min_count = int(match.group(1))
            
            if min_count >= 2 and min_count <= 50:  # Reasonable range
                constraints.append(SamplingConstraint(
                    id=f"min_samples_{len(constraints)+1}",
                    activity_id="sampling_requirement",
                    min_per_window=min_count,
                    source_text=match.group()[:200],
                ))
    
    return constraints


def _detect_dense_windows(text: str) -> List[DenseSamplingWindow]:
    """Detect intensive/dense sampling windows."""
    windows = []
    
    for pattern, confidence in DENSE_SAMPLING_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Extract surrounding context
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            
            # Try to find duration
            duration = None
            for dur_pattern, _ in WINDOW_DURATION_PATTERNS:
                dur_match = re.search(dur_pattern, context, re.IGNORECASE)
                if dur_match:
                    value = dur_match.group(1)
                    unit = dur_match.group(2)
                    duration = _convert_to_iso8601(value, unit)
                    break
            
            windows.append(DenseSamplingWindow(
                id=f"dense_window_{len(windows)+1}",
                name=f"Dense Sampling Period {len(windows)+1}",
                duration=duration,
                source_text=context[:300],
            ))
    
    return windows


def _detect_sparse_sampling(text: str) -> Dict[str, Any]:
    """Detect sparse sampling design information."""
    info = {
        "is_sparse": False,
        "is_population_pk": False,
        "sources": [],
    }
    
    for pattern, confidence in SPARSE_SAMPLING_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            info["is_sparse"] = True
            if "population" in pattern.lower():
                info["is_population_pk"] = True
    
    return info


def _detect_pd_glucose_sampling(text: str) -> List[SamplingConstraint]:
    """
    FIX D: Detect PD glucose sampling constraints.
    
    Creates constraints for:
    - Nadir detection window (0-10 min)
    - Treatment success window (0-30 min)
    - Extended follow-out (if specified)
    """
    constraints = []
    
    # Detect explicit glucose timepoints
    for pattern, confidence in PD_GLUCOSE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                timepoints_str = match.group(1)
                timepoints = re.findall(r'(\d+(?:\.\d+)?)', timepoints_str)
                
                if len(timepoints) >= 3:
                    constraints.append(SamplingConstraint(
                        id=f"pd_glucose_sampling_{len(constraints)+1}",
                        activity_id="Plasma_Glucose",
                        min_per_window=len(timepoints),
                        window_duration=_estimate_window_duration(timepoints, "minutes"),
                        timepoints=[f"PT{int(float(t))}M" for t in timepoints],
                        domain="PD",
                        anchor_id="anchor_treatment_admin",
                        window_start="PT0M",
                        window_end=f"PT{int(float(max(timepoints)))}M",
                        rationale="PD glucose sampling for primary endpoint",
                        source_text=match.group()[:200],
                    ))
            except (IndexError, ValueError):
                continue
    
    # Detect endpoint-linked sampling requirements (nadir, treatment success)
    for pattern, confidence in ENDPOINT_SAMPLING_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                window_minutes = int(match.group(1))
                
                # Determine constraint type from pattern match
                full_match = match.group().lower()
                if 'nadir' in full_match:
                    constraint_id = "pd_glucose_nadir"
                    # Nadir typically requires dense sampling in first 10-15 min
                    timepoints = ["PT0M", "PT5M", "PT10M"]
                    if window_minutes > 10:
                        timepoints.append(f"PT{window_minutes}M")
                    rationale = f"Nadir detection requires observations through {window_minutes} min"
                elif 'success' in full_match:
                    constraint_id = "pd_glucose_success"
                    # Treatment success at 30 min requires observations 0-30 min
                    timepoints = ["PT0M", "PT5M", "PT10M", "PT15M", "PT20M", "PT25M", "PT30M"]
                    rationale = f"Treatment success endpoint requires observations through {window_minutes} min"
                else:
                    constraint_id = f"pd_glucose_endpoint_{len(constraints)+1}"
                    timepoints = ["PT0M", f"PT{window_minutes}M"]
                    rationale = f"Endpoint-linked glucose sampling through {window_minutes} min"
                
                # Only add if not duplicate
                existing_ids = [c.id for c in constraints]
                if constraint_id not in existing_ids:
                    constraints.append(SamplingConstraint(
                        id=constraint_id,
                        activity_id="Plasma_Glucose",
                        min_per_window=len(timepoints),
                        timepoints=timepoints,
                        domain="PD",
                        anchor_id="anchor_treatment_admin",
                        window_start="PT0M",
                        window_end=f"PT{window_minutes}M",
                        rationale=rationale,
                        source_text=match.group()[:200],
                    ))
            except (IndexError, ValueError):
                continue
    
    return constraints


def _estimate_window_duration(timepoints: List[str], unit: str) -> str:
    """Estimate window duration from timepoints."""
    try:
        values = [float(t) for t in timepoints]
        max_val = max(values)
        
        if unit == "minutes":
            if max_val >= 60:
                hours = int(max_val / 60) + 1
                return f"PT{hours}H"
            else:
                return f"PT{int(max_val)}M"
        else:  # hours
            return f"PT{int(max_val)}H"
    except:
        return None


def _convert_to_iso8601(value: str, unit: str) -> str:
    """Convert duration to ISO 8601 format."""
    try:
        val = int(float(value))
        unit_lower = unit.lower()
        
        if 'hour' in unit_lower or unit_lower == 'h':
            return f"PT{val}H"
        elif 'min' in unit_lower:
            return f"PT{val}M"
        elif 'day' in unit_lower or unit_lower == 'd':
            return f"P{val}D"
        else:
            return f"PT{val}H"
    except:
        return None


def _deduplicate_constraints(constraints: List[SamplingConstraint]) -> List[SamplingConstraint]:
    """Remove duplicate constraints."""
    seen = set()
    unique = []
    
    for c in constraints:
        # Handle both SamplingConstraint objects and dicts (from LLM)
        if isinstance(c, dict):
            activity_id = c.get('activity_id') or c.get('activityId', '')
            min_per_window = c.get('min_per_window') or c.get('minPerWindow', 0)
            timepoints = c.get('timepoints', [])[:5]
            key = (activity_id, min_per_window, tuple(timepoints))
            if key not in seen:
                seen.add(key)
                # Convert dict to SamplingConstraint
                unique.append(SamplingConstraint(
                    id=c.get('id', f"sampling_{len(unique)+1}"),
                    activity_id=activity_id,
                    min_per_window=min_per_window,
                    timepoints=c.get('timepoints', []),
                    window_duration=c.get('window_duration') or c.get('windowDuration'),
                    source_text=c.get('source_text', ''),
                ))
        else:
            key = (c.activity_id, c.min_per_window, tuple(c.timepoints[:5]))
            if key not in seen:
                seen.add(key)
                unique.append(c)
    
    return unique


def _enhance_with_llm(
    text: str,
    constraints: List[SamplingConstraint],
    dense_windows: List[DenseSamplingWindow],
    model: str,
) -> Optional[Dict[str, Any]]:
    """Enhance sampling extraction using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and extract SAMPLING DENSITY requirements.

For each sampling schedule, identify:
1. Activity type (PK, PD, biomarker, safety labs)
2. Specific timepoints (e.g., predose, 0.5h, 1h, 2h, 4h, 8h, 24h)
3. Minimum samples required per window/visit
4. Window/period duration
5. Whether it's intensive (dense) or sparse sampling

Current detected constraints: {len(constraints)}
Current detected dense windows: {len(dense_windows)}

Return JSON:
```json
{{
  "constraints": [
    {{
      "activityId": "PK_Blood_Sampling",
      "activityType": "PK",
      "minPerWindow": 12,
      "windowDuration": "PT24H",
      "timepoints": ["predose", "0.5h", "1h", "2h", "4h", "8h", "12h", "24h"],
      "samplingType": "intensive",
      "confidence": 0.9
    }}
  ],
  "denseWindows": [
    {{
      "name": "First-dose PK",
      "duration": "PT24H",
      "numSamples": 12
    }}
  ]
}}
```

Protocol text:
{text[:6000]}

Return ONLY the JSON."""

    try:
        result = call_llm(
            prompt=prompt,
            model_name=model,
            extractor_name="sampling_density",
        )
        
        # Extract response text from dict
        if isinstance(result, dict):
            if 'error' in result:
                logger.warning(f"LLM call error: {result['error']}")
                return None
            response = result.get('response', '')
        else:
            response = str(result)
        
        if not response:
            return None
        
        import json
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning(f"LLM parsing failed: {e}")
    
    return None
