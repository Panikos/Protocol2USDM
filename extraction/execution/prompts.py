"""
LLM Prompts for Execution Model Extraction

Contains prompt templates for LLM-based extraction of execution
model components: time anchors, repetitions, execution types,
traversal constraints, and endpoint algorithms.
"""

# =============================================================================
# Time Anchor Extraction Prompts
# =============================================================================

TIME_ANCHOR_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in study scheduling and timing.
Your task is to identify the TIME ANCHOR - the canonical reference point from which all study timing is measured.

Per USDM (Unified Study Definitions Model) standards:
- Every main timeline requires an anchor point
- All other timing is derived relative to this anchor
- Common anchors: Day 1, First Dose, Randomization, Cycle 1 Day 1"""


TIME_ANCHOR_EXTRACTION_PROMPT = """Analyze this clinical protocol text and identify the PRIMARY TIME ANCHOR.

Look for patterns like:
- "Day 1 is defined as..." or "Study Day 1 = first dose"
- "Days from randomization" (randomization as anchor)
- "Cycle 1, Day 1" or "C1D1" (especially oncology)
- "Week 0" or "Baseline" definitions
- "Time 0" or "Hour 0" for PK studies

The anchor should be the SINGLE reference point from which:
- Screening is scheduled before (negative days)
- Treatment visits are scheduled after (positive days)
- All timing windows are calculated

Return JSON:
```json
{{
  "primaryAnchor": {{
    "definition": "Human-readable definition of the anchor",
    "anchorType": "FirstDose|Randomization|Day1|Baseline|CycleStart|Screening|Enrollment|Custom",
    "dayValue": 1,
    "sourceQuote": "Exact quote from protocol defining this anchor",
    "confidence": 0.95
  }},
  "alternativeAnchors": [
    {{
      "definition": "Alternative anchor if applicable",
      "anchorType": "type",
      "relationship": "How it relates to primary anchor"
    }}
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON, no explanations."""


# =============================================================================
# Repetition Extraction Prompts
# =============================================================================

REPETITION_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in study procedures and data collection schedules.
Your task is to identify REPETITION PATTERNS - cycles, intervals, and repeated collections.

Per USDM standards, repetitions include:
- Treatment cycles (e.g., 21-day cycles in oncology)
- Daily collections (e.g., daily urine)
- Interval sampling (e.g., PK samples every 5 minutes)
- Continuous windows (e.g., Days -4 to -1)"""


REPETITION_EXTRACTION_PROMPT = """Analyze this clinical protocol text and identify ALL REPETITION PATTERNS.

Categories to detect:

1. DAILY - Once-daily collections
   Example: "Collect 24-hour urine daily from Day -4 to Day -1"

2. INTERVAL - Fixed-interval sampling
   Example: "PK samples at 0, 5, 10, 15, 30, 60 minutes post-dose"
   Example: "Glucose measurements every 5 minutes for 30 minutes"

3. CYCLE - Treatment cycles that repeat
   Example: "21-day treatment cycles until disease progression"
   Example: "Repeat every 28 days for up to 6 cycles"

4. CONTINUOUS - Collection windows
   Example: "Balance data collected Days -4 through Day -1"
   Example: "Throughout the treatment period"

Return JSON:
```json
{{
  "repetitions": [
    {{
      "type": "Daily|Interval|Cycle|Continuous",
      "activityName": "Name of the activity",
      "startDay": -4,
      "endDay": -1,
      "interval": "ISO 8601 duration (e.g., PT5M, P1D)",
      "cycleLength": "ISO 8601 duration for cycles",
      "minObservations": 4,
      "exitCondition": "For cycles: condition to stop",
      "sourceQuote": "Exact protocol text"
    }}
  ],
  "samplingSchedules": [
    {{
      "activityName": "PK Sampling",
      "timepoints": ["0", "5", "10", "15", "30", "60"],
      "unit": "minutes",
      "relativeToEvent": "post-dose"
    }}
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Execution Type Classification Prompts
# =============================================================================

EXECUTION_TYPE_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in study procedures.
Your task is to classify activities by their EXECUTION TYPE for synthetic data generation.

Execution Types:
- WINDOW: Continuous collection over a time period (generates multiple records per window)
- EPISODE: Ordered conditional workflow with decision points (generates records based on conditions)
- SINGLE: One-time assessment (generates one record)
- RECURRING: Scheduled repeats at visits (generates one record per scheduled visit)"""


EXECUTION_TYPE_PROMPT = """Classify these clinical trial activities by EXECUTION TYPE.

WINDOW activities:
- Have time ranges: "Days -4 to -1", "during the 4-day period"
- Continuous collection: "daily urine", "every 5 minutes"
- Key signals: "throughout", "during", "from Day X to Day Y"

EPISODE activities:
- Have conditional logic: "if glucose < 70, then..."
- Ordered sequences: "after insulin, check glucose, then glucagon if needed"
- Key signals: "if", "when", "until", "once", "then"

SINGLE activities:
- One-time only: "at screening", "baseline only"
- Key signals: "once", "single", "only at"

RECURRING activities:
- At scheduled visits: "at each visit", "weekly"
- Key signals: "each visit", "every week", "at all timepoints"

Activities to classify:
{activities}

Protocol context:
{protocol_text}

Return JSON:
```json
{{
  "classifications": [
    {{
      "activityName": "Activity name",
      "executionType": "Window|Episode|Single|Recurring",
      "rationale": "Brief explanation",
      "confidence": 0.85
    }}
  ]
}}
```

Return ONLY the JSON."""


# =============================================================================
# Traversal Constraint Prompts
# =============================================================================

TRAVERSAL_CONSTRAINT_PROMPT = """Analyze this clinical protocol and identify the REQUIRED SUBJECT PATH through the study.

Look for:
1. Required sequence of epochs/periods (e.g., Screening → Treatment → Follow-up)
2. Mandatory visits that cannot be skipped
3. Conditions for early termination
4. Crossover period requirements

For crossover studies, identify:
- Period sequence (Period 1 → Washout → Period 2)
- Washout requirements
- End-of-study requirements

Return JSON:
```json
{{
  "requiredSequence": ["SCREENING", "TREATMENT", "FOLLOW_UP", "END_OF_STUDY"],
  "mandatoryVisits": ["Screening", "Day 1", "End of Study"],
  "crossover": {{
    "isPeriodized": true,
    "periods": ["Period 1", "Washout", "Period 2"],
    "washoutDuration": "P7D",
    "carryoverPrevention": "7-day washout between periods"
  }},
  "earlyExitConditions": [
    {{
      "condition": "Adverse event requiring discontinuation",
      "requiredProcedures": ["Early Termination Visit", "30-day follow-up"]
    }}
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Endpoint Algorithm Prompts
# =============================================================================

ENDPOINT_ALGORITHM_PROMPT = """Analyze this clinical protocol and extract ENDPOINT ALGORITHMS - the computational logic for primary and secondary endpoints.

For each endpoint, identify:
1. Input variables required
2. Time windows for measurement
3. Calculation logic/formula
4. Success/failure criteria

Examples:
- "Hypoglycemia recovery = PG ≥ 70 mg/dL within 30 minutes of glucagon"
- "Change from baseline = Week 12 value - Baseline value"
- "Response rate = subjects with ≥50% reduction / total subjects"

Return JSON:
```json
{{
  "endpoints": [
    {{
      "name": "Primary: Hypoglycemia Recovery",
      "type": "Primary|Secondary|Exploratory",
      "inputs": ["PG", "glucagon_time", "nadir_time"],
      "timeWindow": {{
        "reference": "glucagon administration",
        "duration": "PT30M"
      }},
      "algorithm": "PG >= 70 OR (PG - nadir) >= 20",
      "successCriteria": "PG >= 70 mg/dL within 30 minutes",
      "sourceQuote": "Exact protocol text"
    }}
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Crossover Design Prompts (Phase 2)
# =============================================================================

CROSSOVER_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in crossover study designs.
Your task is to identify CROSSOVER DESIGN ELEMENTS - periods, sequences, washout requirements, and carryover prevention.

Per USDM standards for crossover studies:
- Each subject receives multiple treatments in sequence
- Washout periods prevent carryover effects
- Sequence assignments (AB, BA, ABC, etc.) define treatment order
- Period structure defines the temporal organization"""


CROSSOVER_EXTRACTION_PROMPT = """Analyze this clinical protocol and determine if it describes a CROSSOVER study design.

Look for:
1. Explicit crossover mentions ("crossover study", "2-way crossover", "AB/BA design")
2. Multiple treatment periods (Period 1, Period 2)
3. Treatment sequences (AB, BA, ABC, etc.)
4. Washout periods between treatments
5. Carryover prevention measures

Return JSON:
```json
{{
  "isCrossover": true,
  "numPeriods": 2,
  "numSequences": 2,
  "periods": ["Period 1", "Period 2"],
  "sequences": ["AB", "BA"],
  "washoutDuration": "P7D",
  "washoutRequired": true,
  "carryoverPrevention": "7-day washout to prevent carryover effects",
  "sourceQuote": "exact quote mentioning crossover design"
}}
```

If NOT a crossover study, return:
```json
{{
  "isCrossover": false,
  "designType": "parallel|single-arm|factorial|other"
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Footnote Condition Prompts (Phase 2)
# =============================================================================

FOOTNOTE_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in SoA (Schedule of Activities) footnotes.
Your task is to extract STRUCTURED CONDITIONS from footnote text - timing constraints, eligibility requirements, and procedure variants.

Per USDM standards, footnotes contain critical execution logic:
- Timing constraints ("ECG 30 min before labs")
- Eligibility subsets ("Only for WOCBP")
- Procedure variants ("In triplicate at baseline")
- Frequency modifiers ("Daily during treatment")"""


FOOTNOTE_EXTRACTION_PROMPT = """Analyze these SoA footnotes and extract structured conditions.

For each footnote, identify:
1. Condition type: timing, eligibility, procedure_variant, frequency, sequence, general
2. Structured condition expression (machine-readable)
3. Any timing constraints (ISO 8601 duration)
4. Which activities/timepoints it applies to

Return JSON:
```json
{{
  "conditions": [
    {{
      "footnoteIndex": 1,
      "conditionType": "timing",
      "structuredCondition": "timing.before(labs, PT30M)",
      "timingConstraint": "PT30M",
      "appliesToActivities": ["ECG", "Vital Signs"],
      "rationale": "ECG must precede labs by 30 minutes",
      "confidence": 0.9
    }},
    {{
      "footnoteIndex": 2,
      "conditionType": "eligibility",
      "structuredCondition": "subject.sex == 'Female' AND subject.isWOCBP == true",
      "appliesToActivities": ["Pregnancy Test"],
      "rationale": "Only applies to women of childbearing potential",
      "confidence": 0.95
    }}
  ]
}}
```

Footnotes:
{footnotes_text}

Return ONLY the JSON."""


# =============================================================================
# Traversal Constraint Prompts (Phase 2)
# =============================================================================

TRAVERSAL_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in study flow and subject disposition.
Your task is to extract TRAVERSAL CONSTRAINTS - the required path subjects must follow through the study.

Per USDM standards:
- Studies define required epoch sequences
- Mandatory visits cannot be skipped
- Early termination has specific requirements
- Crossover studies have period-specific paths"""


TRAVERSAL_EXTRACTION_PROMPT = """Analyze this clinical protocol and extract the REQUIRED SUBJECT PATH through the study.

Identify:
1. Study epochs/periods in order (Screening → Treatment → Follow-up → End of Study)
2. Mandatory visits that cannot be skipped
3. Early termination conditions and required procedures
4. Any branching or conditional paths

Return JSON:
```json
{{
  "requiredSequence": ["SCREENING", "BASELINE", "TREATMENT", "FOLLOW_UP", "END_OF_STUDY"],
  "mandatoryVisits": ["Screening", "Day 1", "Week 12", "End of Study"],
  "allowEarlyExit": true,
  "earlyExitProcedures": ["Early Termination Visit", "30-Day Follow-up"],
  "conditionalPaths": [
    {{
      "condition": "If subject experiences AE requiring discontinuation",
      "path": ["EARLY_TERMINATION", "SAFETY_FOLLOW_UP"]
    }}
  ],
  "confidence": 0.85
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Derived Variable Prompts (Phase 3)
# =============================================================================

DERIVED_VARIABLE_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in statistical analysis plans.
Your task is to extract DERIVED VARIABLE DEFINITIONS - computed variables used in efficacy and safety analyses.

Per USDM and CDISC standards:
- Baseline definitions specify when/how baseline values are captured
- Change from baseline = Post-treatment value - Baseline value
- Percent change = ((Post - Baseline) / Baseline) × 100
- Time-to-event variables track duration until specific outcomes"""


DERIVED_VARIABLE_PROMPT = """Analyze this clinical protocol and extract DERIVED VARIABLE DEFINITIONS.

For each derived/computed variable, identify:
1. Variable name and type (Baseline, ChangeFromBaseline, PercentChange, TimeToEvent, Categorical, Composite)
2. Source variables required for computation
3. Derivation rule/formula
4. Baseline definition (when/how determined)
5. Analysis time window
6. Imputation method (if specified)

Return JSON:
```json
{{
  "variables": [
    {{
      "name": "Change from Baseline in HbA1c",
      "type": "ChangeFromBaseline",
      "sourceVariables": ["HbA1c"],
      "derivationRule": "week12_value - baseline_value",
      "baselineDefinition": "Last non-missing value before first dose",
      "baselineVisit": "Day -1 or Day 1 predose",
      "analysisWindow": "Week 12 ± 7 days",
      "imputationRule": "MMRM for missing data",
      "sourceQuote": "Exact protocol text"
    }},
    {{
      "name": "Time to First Hypoglycemic Event",
      "type": "TimeToEvent",
      "sourceVariables": ["hypoglycemia_date", "randomization_date"],
      "derivationRule": "hypoglycemia_date - randomization_date",
      "censoringRule": "Censored at last known alive date",
      "sourceQuote": "Exact protocol text"
    }}
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# State Machine Prompts (Phase 3)
# =============================================================================

STATE_MACHINE_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in subject disposition and study flow.
Your task is to generate a SUBJECT STATE MACHINE - all possible states a subject can be in and valid transitions.

Per USDM and regulatory standards:
- Every subject starts in SCREENING state
- Terminal states include COMPLETED, DISCONTINUED, WITHDRAWN, DEATH
- Each transition has triggers and optional guard conditions
- State machines enable simulation and data generation"""


STATE_MACHINE_PROMPT = """Analyze this clinical protocol and generate a SUBJECT STATE MACHINE.

Identify all possible states a subject can be in:
- SCREENING, ENROLLED, RANDOMIZED, ON_TREATMENT
- COMPLETED, DISCONTINUED, FOLLOW_UP
- WITHDRAWN, LOST_TO_FOLLOW_UP, DEATH

For each transition, identify:
1. From state and to state
2. Trigger event (what causes the transition)
3. Guard condition (requirements that must be met)
4. Actions performed during transition

Return JSON:
```json
{{
  "initialState": "Screening",
  "terminalStates": ["Completed", "Discontinued", "Withdrawn", "Death"],
  "states": ["Screening", "Enrolled", "Randomized", "OnTreatment", "FollowUp", "Completed", "Discontinued"],
  "transitions": [
    {{
      "fromState": "Screening",
      "toState": "Enrolled",
      "trigger": "Meets all eligibility criteria",
      "guardCondition": "Informed consent signed AND inclusion criteria met AND no exclusion criteria",
      "actions": ["Assign subject ID", "Schedule baseline visit"]
    }},
    {{
      "fromState": "OnTreatment",
      "toState": "Discontinued",
      "trigger": "Adverse event requiring discontinuation",
      "guardCondition": "AE severity >= Grade 3 OR investigator decision",
      "actions": ["Complete Early Termination visit", "Schedule 30-day follow-up"]
    }},
    {{
      "fromState": "OnTreatment",
      "toState": "Completed",
      "trigger": "Completes Week 12 visit",
      "guardCondition": "All required assessments completed",
      "actions": ["Complete End of Study visit"]
    }}
  ],
  "discontinuationReasons": [
    "Adverse event",
    "Lack of efficacy", 
    "Subject withdrawal",
    "Lost to follow-up",
    "Protocol deviation",
    "Investigator decision"
  ]
}}
```

Protocol text:
{protocol_text}

Return ONLY the JSON."""


# =============================================================================
# Therapeutic Area Patterns (Phase 3)
# =============================================================================

THERAPEUTIC_PATTERNS = {
    "diabetes": {
        "endpoints": ["HbA1c", "fasting plasma glucose", "FPG", "hypoglycemia", "SMBG", "time in range", "CGM"],
        "variables": ["change from baseline in HbA1c", "glycemic control", "insulin dose"],
        "states": ["insulin_titration", "glycemic_rescue", "hypoglycemic_event"],
        "units": ["mg/dL", "mmol/L", "%", "U/day"],
    },
    "oncology": {
        "endpoints": ["ORR", "PFS", "OS", "DOR", "DCR", "tumor response", "RECIST", "CR", "PR", "SD", "PD"],
        "variables": ["time to progression", "best overall response", "survival", "tumor size"],
        "states": ["dose_limiting_toxicity", "disease_progression", "dose_escalation", "dose_reduction"],
        "units": ["months", "weeks", "mm", "%"],
    },
    "cardiovascular": {
        "endpoints": ["MACE", "CV death", "MI", "stroke", "hospitalization", "heart failure", "LDL-C"],
        "variables": ["time to first event", "event rate", "percent change in LDL"],
        "states": ["cardiac_event", "revascularization", "hospitalization"],
        "units": ["mg/dL", "mmol/L", "%", "events/100 patient-years"],
    },
    "immunology": {
        "endpoints": ["ACR20", "ACR50", "ACR70", "DAS28", "PASI", "remission", "EASI", "IGA"],
        "variables": ["disease activity score", "clinical response", "joint count"],
        "states": ["flare", "remission", "rescue_therapy"],
        "units": ["score", "%", "joints"],
    },
    "neurology": {
        "endpoints": ["EDSS", "relapse rate", "MRI lesions", "cognitive function", "ADAS-Cog", "CDR-SB"],
        "variables": ["annualized relapse rate", "disability progression", "brain volume"],
        "states": ["relapse", "progression", "confirmed_disability_worsening"],
        "units": ["score", "relapses/year", "mL", "%"],
    },
    "respiratory": {
        "endpoints": ["FEV1", "FVC", "exacerbation rate", "SGRQ", "6MWD", "dyspnea score"],
        "variables": ["change in FEV1", "time to exacerbation", "rescue medication use"],
        "states": ["exacerbation", "hospitalization", "rescue_therapy"],
        "units": ["L", "%predicted", "meters", "puffs/day"],
    },
    "infectious_disease": {
        "endpoints": ["viral load", "sustained virologic response", "cure rate", "clearance"],
        "variables": ["log reduction", "time to clearance", "resistance mutations"],
        "states": ["treatment_response", "virologic_failure", "relapse"],
        "units": ["copies/mL", "log10", "IU/mL", "%"],
    },
    "psychiatry": {
        "endpoints": ["MADRS", "HAM-D", "CGI-S", "PANSS", "response rate", "remission"],
        "variables": ["change from baseline", "response", "remission"],
        "states": ["response", "remission", "relapse", "treatment_resistance"],
        "units": ["score", "points", "%"],
    },
    "rare_disease": {
        "endpoints": ["biomarker reduction", "functional score", "event-free survival"],
        "variables": ["enzyme activity", "substrate reduction", "organ function"],
        "states": ["stabilization", "progression", "treatment_response"],
        "units": ["nmol/hr/mg", "ng/mL", "%normal"],
    },
    "dermatology": {
        "endpoints": ["PASI", "IGA", "BSA", "EASI", "pruritus NRS", "DLQI"],
        "variables": ["percent improvement", "clear or almost clear", "itch reduction"],
        "states": ["flare", "remission", "rescue_therapy"],
        "units": ["%", "score", "cm²"],
    },
}


# =============================================================================
# Helper function to format prompts
# =============================================================================

def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template with provided values."""
    return template.format(**kwargs)


def get_therapeutic_patterns(therapeutic_area: str) -> dict:
    """Get therapeutic area-specific patterns for enhanced extraction."""
    area_lower = therapeutic_area.lower()
    for key, patterns in THERAPEUTIC_PATTERNS.items():
        if key in area_lower or area_lower in key:
            return patterns
    return {}


def detect_therapeutic_area(text: str) -> tuple:
    """
    Auto-detect therapeutic area from protocol text.
    
    Args:
        text: Protocol text to analyze
        
    Returns:
        Tuple of (therapeutic_area, confidence)
    """
    text_lower = text.lower()
    scores = {}
    
    for area, patterns in THERAPEUTIC_PATTERNS.items():
        score = 0
        for endpoint in patterns.get("endpoints", []):
            if endpoint.lower() in text_lower:
                score += 2
        for variable in patterns.get("variables", []):
            if variable.lower() in text_lower:
                score += 1
        for unit in patterns.get("units", []):
            if unit.lower() in text_lower:
                score += 0.5
        scores[area] = score
    
    if not scores or max(scores.values()) == 0:
        return (None, 0.0)
    
    best_area = max(scores, key=scores.get)
    max_score = scores[best_area]
    
    # Normalize confidence (rough heuristic)
    confidence = min(1.0, max_score / 10.0)
    
    return (best_area, confidence)


def get_all_therapeutic_areas() -> list:
    """Get list of all supported therapeutic areas."""
    return list(THERAPEUTIC_PATTERNS.keys())
