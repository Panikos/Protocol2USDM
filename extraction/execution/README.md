# Execution Model Extraction Module

This module provides extractors for execution-level semantics that enable **deterministic synthetic data generation** from USDM output.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Protocol PDF                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Pipeline Integration                           │
│  extract_execution_model() - 13-step extraction pipeline         │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Phase 1    │ │  Phase 2    │ │  Phase 3    │ │  Phase 4    │ │  Phase 5    │
│ ───────────│ │ ───────────│ │ ───────────│ │ ───────────│ │ ───────────│
│ TimeAnchors │ │ Crossover   │ │ Endpoints   │ │ Dosing      │ │ Sampling    │
│ Repetitions │ │ Traversal   │ │ Variables   │ │ Visits      │ │ Density     │
│ ExecTypes   │ │ Footnotes   │ │ StateMachine│ │ Stratific.  │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ExecutionModelData                             │
│  Merged results from all phases                                  │
└─────────────────────────────────────────────────────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Validation   │   │    Export     │   │     USDM      │
│ ─────────────│   │ ─────────────│   │ ─────────────│
│ Quality Score │   │ JSON/CSV/MD   │   │ Extensions    │
│ Error/Warning │   │ Reports       │   │ Attributes    │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Overview

The execution model captures information that goes beyond static protocol structure:

### Phase 1 Components

| Component | What It Captures | Why It Matters |
|-----------|-----------------|----------------|
| **Time Anchors** | Canonical Day 1 definition | All timing derives from this |
| **Repetitions** | Cycles, intervals, daily collections | Know how many records to generate |
| **Execution Types** | WINDOW vs EPISODE classification | Different generation patterns |
| **Sampling Constraints** | Minimum observations per window | Ensure analyzable data |

### Phase 2 Components

| Component | What It Captures | Why It Matters |
|-----------|-----------------|----------------|
| **Crossover Design** | Periods, sequences, washout | Period-specific subject paths |
| **Traversal Constraints** | Required epochs, mandatory visits | Valid subject journeys |
| **Footnote Conditions** | Timing, eligibility, procedure variants | Structured execution rules |

### Phase 3 Components

| Component | What It Captures | Why It Matters |
|-----------|-----------------|----------------|
| **Endpoint Algorithms** | Calculation logic, success criteria | Computable endpoint definitions |
| **Derived Variables** | Baseline definitions, derivation rules | How to compute analysis variables |
| **State Machine** | States, transitions, triggers | Valid subject disposition paths |

### Phase 4 Components

| Component | What It Captures | Why It Matters |
|-----------|-----------------|----------------|
| **Dosing Regimens** | Dose amounts, frequencies, titration | Generate realistic treatment data |
| **Visit Windows** | Scheduled visits, timing allowances | Know when visits should occur |
| **Stratification** | Randomization ratio, stratification factors | Realistic subject allocation |

### Phase 5 Components

| Component | What It Captures | Why It Matters |
|-----------|-----------------|----------------|
| **Sampling Density** | PK/PD timepoints, minimum samples | Know exact sampling schedule |
| **Dense Windows** | Intensive sampling periods | Identify high-frequency collection |
| **Sparse Sampling** | Population PK designs | Recognize reduced sampling |

## Model Selection (v6.9+)

When running with `gemini-3-flash-preview`, the execution model extractors use the main model for all phases. The SoA extraction fallback only affects the Schedule of Activities text extraction step, not the execution model extraction.

**Recommended command:**
```bash
python main_v2.py protocol.pdf --complete --model gemini-3-flash-preview
```

## Installation

The module is included in Protocol2USDMv3. No additional installation required.

## Usage

### Command Line

```bash
# Basic extraction (heuristic only)
python extract_execution_model.py protocol.pdf

# With LLM enhancement
python extract_execution_model.py protocol.pdf --use-llm

# Save output to directory
python extract_execution_model.py protocol.pdf --output-dir output/

# With validation
python extract_execution_model.py protocol.pdf --output-dir output/ --validate
```

### Complete Extraction (Recommended)

```bash
# Run EVERYTHING with one command
python extract_execution_model.py protocol.pdf --output-dir output/ --complete

# With SAP document for enhanced endpoint/variable extraction
python extract_execution_model.py protocol.pdf --output-dir output/ --complete --sap sap.pdf
```

### SAP Integration

The SAP (Statistical Analysis Plan) document provides more detailed information about:
- **Endpoint algorithms**: Analysis methods, statistical approaches
- **Derived variables**: Detailed derivation rules, imputation methods
- **Baseline definitions**: Exact timing and handling rules

```bash
# Extract with SAP support
python extract_execution_model.py protocol.pdf --sap sap.pdf --output-dir output/
```

When SAP is provided:
- Endpoints from SAP are merged with protocol endpoints
- Missing algorithms/success criteria are filled from SAP
- Derived variable definitions are enhanced with SAP details
- Items extracted only from SAP are marked with `[SAP]` prefix

**`--complete` enables:**
| Option | Description |
|--------|-------------|
| `--use-llm` | LLM-enhanced extraction (gemini-2.5-pro) |
| `--validate` | Quality validation with scoring |
| `--export-csv` | Export 8 CSV files (one per component) |
| `--report` | Generate Markdown summary report |

**Output files created:**
```bash
output/
├── 11_execution_model.json           # Main extraction result
├── 11_execution_model_validation.json # Quality validation
├── 11_execution_model_report.md      # Markdown summary
├── execution_model_time_anchors.csv
├── execution_model_repetitions.csv
├── execution_model_execution_types.csv
├── execution_model_traversal.csv
├── execution_model_footnotes.csv
├── execution_model_endpoints.csv
├── execution_model_derived_variables.csv
└── execution_model_state_machine.csv
```

### Phase-Specific Extraction

```bash
# Phase-specific extraction
python extract_execution_model.py protocol.pdf --phase1-only  # Time anchors, repetitions, types
python extract_execution_model.py protocol.pdf --phase2-only  # Crossover, traversal, footnotes
python extract_execution_model.py protocol.pdf --phase3-only  # Endpoints, variables, state machine

# Skip specific extractors
python extract_execution_model.py protocol.pdf --skip-endpoints --skip-state-machine
```

### Python API

```python
from extraction.execution import (
    extract_execution_model,
    enrich_usdm_with_execution_model,
    create_execution_model_summary,
)

# Extract execution model
result = extract_execution_model(
    pdf_path="protocol.pdf",
    model="gemini-2.5-pro",
    use_llm=True,
)

if result.success:
    # Print summary
    print(create_execution_model_summary(result.data))
    
    # Enrich existing USDM output
    enriched_usdm = enrich_usdm_with_execution_model(
        usdm_output=existing_usdm,
        execution_data=result.data,
    )
```

### Individual Extractors

```python
from extraction.execution import (
    extract_time_anchors,
    extract_repetitions,
    classify_execution_types,
    # Phase 2 extractors
    extract_crossover_design,
    extract_traversal_constraints,
    extract_footnote_conditions,
)

# Just time anchors
anchor_result = extract_time_anchors(pdf_path="protocol.pdf")
for anchor in anchor_result.data.time_anchors:
    print(f"{anchor.anchor_type.value}: {anchor.definition}")

# Just repetitions
rep_result = extract_repetitions(pdf_path="protocol.pdf")
for rep in rep_result.data.repetitions:
    print(f"{rep.type.value}: {rep.interval}")

# Crossover design (Phase 2)
crossover_result = extract_crossover_design(pdf_path="protocol.pdf")
if crossover_result.data.crossover_design:
    cd = crossover_result.data.crossover_design
    print(f"Crossover: {cd.num_periods} periods, sequences: {cd.sequences}")

# Traversal constraints (Phase 2)
traversal_result = extract_traversal_constraints(pdf_path="protocol.pdf")
for tc in traversal_result.data.traversal_constraints:
    print(f"Path: {' → '.join(tc.required_sequence)}")

# Footnote conditions (Phase 2)
footnote_result = extract_footnote_conditions(pdf_path="protocol.pdf")
for fc in footnote_result.data.footnote_conditions:
    print(f"[{fc.condition_type}] {fc.text[:50]}...")

# Endpoint algorithms (Phase 3)
endpoint_result = extract_endpoint_algorithms(pdf_path="protocol.pdf")
for ep in endpoint_result.data.endpoint_algorithms:
    print(f"[{ep.endpoint_type.value}] {ep.name}: {ep.algorithm}")

# Derived variables (Phase 3)
variable_result = extract_derived_variables(pdf_path="protocol.pdf")
for dv in variable_result.data.derived_variables:
    print(f"{dv.name}: {dv.derivation_rule}")

# State machine (Phase 3)
sm_result = generate_state_machine(pdf_path="protocol.pdf")
if sm_result.data.state_machine:
    sm = sm_result.data.state_machine
    print(f"States: {[s.value for s in sm.states]}")
    print(f"Transitions: {len(sm.transitions)}")

# Dosing regimens (Phase 4)
from extraction.execution import extract_dosing_regimens
dosing_result = extract_dosing_regimens(pdf_path="protocol.pdf")
for dr in dosing_result.data.dosing_regimens:
    doses = ", ".join(f"{d.amount}{d.unit}" for d in dr.dose_levels)
    print(f"{dr.treatment_name}: {doses} {dr.frequency.value}")

# Visit windows (Phase 4) - with SOA context
from extraction.execution import extract_visit_windows
visit_result = extract_visit_windows(pdf_path="protocol.pdf", soa_data=soa_data)
for vw in visit_result.data.visit_windows:
    print(f"{vw.visit_name}: Day {vw.target_day} ±{vw.window_before}/{vw.window_after}d")

# Stratification (Phase 4)
from extraction.execution import extract_stratification
strat_result = extract_stratification(pdf_path="protocol.pdf")
if strat_result.data.randomization_scheme:
    rs = strat_result.data.randomization_scheme
    print(f"Ratio: {rs.ratio}, Factors: {[f.name for f in rs.stratification_factors]}")
```

## Schema

### TimeAnchor

```python
@dataclass
class TimeAnchor:
    id: str
    definition: str           # "First administration of study drug"
    anchor_type: AnchorType   # FIRST_DOSE, RANDOMIZATION, DAY_1, etc.
    day_value: int            # Usually 1
    source_text: str          # Original protocol text
```

**AnchorType Enum:**
- `FIRST_DOSE` - First drug administration
- `RANDOMIZATION` - Randomization date
- `DAY_1` - Study Day 1
- `BASELINE` - Baseline visit
- `CYCLE_START` - Cycle 1 Day 1
- `SCREENING` - Screening visit
- `ENROLLMENT` - Enrollment date
- `INFORMED_CONSENT` - IC date
- `CUSTOM` - Other

### Repetition

```python
@dataclass
class Repetition:
    id: str
    type: RepetitionType      # DAILY, INTERVAL, CYCLE, CONTINUOUS
    interval: str             # ISO 8601 duration (e.g., "PT5M", "P1D")
    start_offset: str         # From anchor (e.g., "-P4D")
    end_offset: str           # From anchor (e.g., "-P1D")
    min_observations: int     # Minimum samples required
    cycle_length: str         # For CYCLE type (e.g., "P21D")
    exit_condition: str       # "Disease progression"
    source_text: str
```

**RepetitionType Enum:**
- `DAILY` - Once daily collection
- `INTERVAL` - Fixed interval (e.g., every 5 min)
- `CYCLE` - Treatment cycles
- `CONTINUOUS` - Continuous window
- `ON_DEMAND` - As needed

### CrossoverDesign (Phase 2)

```python
@dataclass
class CrossoverDesign:
    id: str
    is_crossover: bool         # True if crossover design detected
    num_periods: int           # Number of treatment periods (2, 3, etc.)
    num_sequences: int         # Number of sequences (AB/BA = 2)
    periods: List[str]         # ["Period 1", "Period 2"]
    sequences: List[str]       # ["AB", "BA"]
    washout_duration: str      # ISO 8601 (e.g., "P7D")
    washout_required: bool     # Whether washout is mandatory
    carryover_prevention: str  # Prevention strategy
    source_text: str
    confidence: float
```

### TraversalConstraint (Phase 2)

```python
@dataclass
class TraversalConstraint:
    id: str
    required_sequence: List[str]  # ["SCREENING", "TREATMENT", "FOLLOW_UP"]
    allow_early_exit: bool        # Can subjects exit early?
    exit_epoch_ids: List[str]     # ["EARLY_TERMINATION"]
    mandatory_visits: List[str]   # ["Screening", "Day 1", "End of Study"]
    source_text: str
    confidence: float
```

### FootnoteCondition (Phase 2)

```python
@dataclass
class FootnoteCondition:
    id: str
    footnote_id: str              # Original marker (e.g., "a", "1")
    condition_type: str           # timing, eligibility, procedure_variant, etc.
    text: str                     # Original footnote text
    structured_condition: str     # Machine-readable (e.g., "timing.before(labs, PT30M)")
    applies_to_activity_ids: List[str]
    timing_constraint: str        # ISO 8601 duration if applicable
    confidence: float
```

**Condition Types:**
- `timing_before` / `timing_after` - Temporal ordering
- `eligibility_wocbp` - Women of childbearing potential
- `eligibility_condition` - Patient subset
- `procedure_replicate` - Triplicate/duplicate
- `procedure_fasting` - Fasting requirement
- `frequency_daily` / `frequency_weekly` - Frequency modifiers

### EndpointAlgorithm (Phase 3)

```python
@dataclass
class EndpointAlgorithm:
    id: str
    name: str                      # "Primary: Hypoglycemia Recovery"
    endpoint_type: EndpointType    # PRIMARY, SECONDARY, EXPLORATORY, SAFETY
    inputs: List[str]              # ["PG", "glucagon_time"]
    time_window_reference: str     # "glucagon administration"
    time_window_duration: str      # ISO 8601 (e.g., "PT30M")
    algorithm: str                 # "PG >= 70 OR (PG - nadir) >= 20"
    success_criteria: str          # "PG >= 70 mg/dL within 30 minutes"
    unit: str                      # "mg/dL"
    confidence: float
```

### DerivedVariable (Phase 3)

```python
@dataclass
class DerivedVariable:
    id: str
    name: str                      # "Change from Baseline in HbA1c"
    variable_type: VariableType    # BASELINE, CHANGE_FROM_BASELINE, PERCENT_CHANGE, etc.
    source_variables: List[str]    # ["HbA1c"]
    derivation_rule: str           # "week12_value - baseline_value"
    baseline_definition: str       # "Last non-missing value before Day 1"
    baseline_visit: str            # "Day -1"
    analysis_window: str           # "Week 12 ± 7 days"
    imputation_rule: str           # "MMRM" or "LOCF"
    confidence: float
```

**VariableType Enum:**
- `BASELINE` - Baseline value
- `CHANGE_FROM_BASELINE` - Post - Baseline
- `PERCENT_CHANGE` - Percentage change
- `TIME_TO_EVENT` - Survival/event time
- `CATEGORICAL` - Binary/categorical
- `COMPOSITE` - Multi-component
- `CUSTOM` - Other derivation

### SubjectStateMachine (Phase 3)

```python
@dataclass
class SubjectStateMachine:
    id: str
    initial_state: StateType       # Usually SCREENING
    terminal_states: List[StateType]  # [COMPLETED, DISCONTINUED, ...]
    states: List[StateType]        # All possible states
    transitions: List[StateTransition]
    confidence: float

@dataclass
class StateTransition:
    from_state: StateType
    to_state: StateType
    trigger: str                   # "Meets eligibility criteria"
    guard_condition: str           # Optional condition
    actions: List[str]             # Actions to perform
```

**StateType Enum:**
- `SCREENING`, `ENROLLED`, `RANDOMIZED`, `ON_TREATMENT`
- `COMPLETED`, `DISCONTINUED`, `FOLLOW_UP`
- `LOST_TO_FOLLOW_UP`, `WITHDRAWN`, `DEATH`

### ExecutionType

```python
class ExecutionType(Enum):
    WINDOW = "Window"      # Continuous collection period
    EPISODE = "Episode"    # Ordered conditional workflow
    SINGLE = "Single"      # One-time event
    RECURRING = "Recurring"  # Scheduled repeats
```

## USDM Compliance

All output is USDM v4.0 compliant per the official `dataStructure.yml`. As of v6.6:

### Entity Placement (per dataStructure.yml)

| Entity | Location |
|--------|----------|
| `timings` | `scheduleTimeline.timings[]` |
| `exits` | `scheduleTimeline.exits[]` |
| `conditions` | `studyVersion.conditions[]` |
| `analysisPopulations` | `studyDesign.analysisPopulations[]` |
| `footnote conditions` | `studyDesign.notes[]` or `activity.notes[]` |

### Extension Attributes

Execution-specific metadata is stored in `extensionAttributes` using the `x-executionModel` namespace:

```json
{
  "studyDesign": {
    "id": "sd_1",
    "extensionAttributes": [
      {
        "x-executionModel-timeAnchors": [
          {
            "definition": "First dose of study drug",
            "anchorType": "FirstDose",
            "dayValue": 1
          }
        ]
      },
      {
        "x-executionModel-repetitions": [
          {
            "type": "Daily",
            "interval": "P1D",
            "startOffset": "-P4D",
            "endOffset": "-P1D"
          }
        ]
      }
    ],
    "scheduleTimelines": [
      {
        "id": "tl_main",
        "timings": [...],
        "exits": [...]
      }
    ],
    "activities": [
      {
        "id": "act_1",
        "name": "Balance Collection",
        "definedProcedures": [...],
        "notes": [...]
      }
    ]
  }
}
```

## Integration with Pipeline

The execution model extraction is designed to run **after** existing extractors and **enrich** the output:

```python
from extraction import run_extraction_pipeline
from extraction.execution import (
    extract_execution_model,
    enrich_usdm_with_execution_model,
)

# Run existing pipeline
pipeline_result = run_extraction_pipeline(pdf_path="protocol.pdf")

# Extract execution model
exec_result = extract_execution_model(pdf_path="protocol.pdf")

# Enrich USDM output
if exec_result.success:
    enriched = enrich_usdm_with_execution_model(
        usdm_output=pipeline_result.usdm_output,
        execution_data=exec_result.data,
    )
```

## Detection Patterns

### Time Anchor Detection

| Pattern | Anchor Type | Confidence |
|---------|-------------|------------|
| "first dose of study drug" | FIRST_DOSE | 0.95 |
| "day 1 of cycle 1" | FIRST_DOSE | 0.90 |
| "days from randomization" | RANDOMIZATION | 0.85 |
| "week 0 of treatment" | BASELINE | 0.80 |
| "C1D1" | CYCLE_START | 0.80 |

### Repetition Detection

| Pattern | Type | Example |
|---------|------|---------|
| "daily urine collection" | DAILY | P1D interval |
| "every 5 minutes" | INTERVAL | PT5M interval |
| "21-day cycles" | CYCLE | P21D cycle length |
| "Days -4 to -1" | CONTINUOUS | -P4D to -P1D |

### Execution Type Classification

| Signal Words | Execution Type |
|--------------|----------------|
| "Day X to Day Y", "throughout" | WINDOW |
| "if", "until", "when threshold" | EPISODE |
| "at screening only" | SINGLE |
| "at each visit" | RECURRING |

## Output Files

When `--output-dir` is specified:

- `11_execution_model.json` - Complete extraction results
- `11_execution_model_validation.json` - Validation results (with `--validate`)

## Validation

The module includes a validation system to check extracted data for quality and consistency:

```python
from extraction.execution import validate_execution_model, create_validation_summary

result = extract_execution_model("protocol.pdf")
validation = validate_execution_model(result.data)

print(f"Valid: {validation.is_valid}")
print(f"Quality Score: {validation.score:.2f}")
print(f"Errors: {len(validation.errors)}")
print(f"Warnings: {len(validation.warnings)}")

# Human-readable summary
print(create_validation_summary(validation))
```

### Validation Checks

| Component | Checks |
|-----------|--------|
| **Time Anchors** | Presence of key anchors, duplicates, confidence thresholds |
| **Repetitions** | Interval patterns have durations |
| **Execution Types** | Classification confidence levels |
| **Traversal** | Sequence length, SCREENING at start |
| **Crossover** | Period count, sequence definitions |
| **Endpoints** | Primary endpoint present, algorithm defined |
| **Variables** | Baseline definitions, derivation rules |
| **State Machine** | Terminal states, reachability, dead-ends |
| **Cross-Component** | Consistency between traversal/state machine |

## Therapeutic Area Patterns

The module includes domain-specific patterns for enhanced extraction:

```python
from extraction.execution.prompts import get_therapeutic_patterns

diabetes = get_therapeutic_patterns("diabetes")
# Returns: {"endpoints": ["HbA1c", "FPG", ...], "variables": [...], "states": [...]}

oncology = get_therapeutic_patterns("oncology")
# Returns: {"endpoints": ["ORR", "PFS", "OS", ...], ...}
```

Supported areas: `diabetes`, `oncology`, `cardiovascular`, `immunology`, `neurology`, `respiratory`, `infectious_disease`, `psychiatry`, `rare_disease`, `dermatology`

### Auto-Detection

```python
from extraction.execution.prompts import detect_therapeutic_area

area, confidence = detect_therapeutic_area(protocol_text)
print(f"Detected: {area} (confidence: {confidence:.0%})")
```

## Configuration

The module supports configuration via files or environment variables:

### Config File

```bash
# Create default config
python extract_execution_model.py --create-config execution_config.json

# Use config file
python extract_execution_model.py protocol.pdf --config execution_config.json
```

### Config Options

```json
{
  "model": "gemini-2.5-pro",
  "use_llm": true,
  "min_confidence": 0.5,
  "enable_phase1": true,
  "enable_phase2": true,
  "enable_phase3": true,
  "skip_endpoints": false,
  "validate": true,
  "export_csv": false,
  "therapeutic_area": "diabetes"
}
```

### Python API

```python
from extraction.execution import ExtractionConfig, load_config

# Load from file
config = load_config("execution_config.json")

# Or create programmatically
config = ExtractionConfig(
    model="gemini-2.5-pro",
    therapeutic_area="oncology",
    validate=True,
)
```

## Caching

The module includes caching for performance optimization:

```python
from extraction.execution import ExecutionCache, get_cache, cached

# Get global cache
cache = get_cache()
print(cache.get_stats())

# Use decorator for automatic caching
@cached(key_prefix="my_extraction", ttl_seconds=3600)
def my_extraction_function():
    ...

# Manual cache management
cache = ExecutionCache(cache_dir="./cache", ttl_seconds=86400)
cache.set("key", {"data": "value"})
result = cache.get("key")
```

## Export Formats

### CSV Export

```bash
python extract_execution_model.py protocol.pdf --output-dir output/ --export-csv
```

Creates 8 CSV files:
- `execution_model_time_anchors.csv`
- `execution_model_repetitions.csv`
- `execution_model_execution_types.csv`
- `execution_model_traversal.csv`
- `execution_model_footnotes.csv`
- `execution_model_endpoints.csv`
- `execution_model_derived_variables.csv`
- `execution_model_state_machine.csv`

### Markdown Report

```bash
python extract_execution_model.py protocol.pdf --output-dir output/ --report --validate
```

Generates a comprehensive Markdown report with:
- Summary statistics
- Component details
- Validation results

## Troubleshooting

**No anchors detected:**
- Check if protocol has clear Day 1 / First Dose definitions
- Try `--use-llm` for enhanced detection

**Low confidence scores:**
- Protocol text may be ambiguous
- Review source_text fields in output

**Import errors:**
- Ensure you're running from project root
- Check Python path includes project directory
