# Execution Model Architecture

This document describes the architectural improvements made to the USDM extraction pipeline to ensure execution model findings properly shape the core USDM graph.

## Problem Statement

Previously, execution model findings (crossover design, traversal constraints, dosing regimens, etc.) were extracted but stayed isolated in **extension attributes** instead of shaping the **core USDM model**. This created gaps for downstream synthetic data generation:

1. **Crossover detection** existed but core design still showed single-arm interventional
2. **Traversal constraints** referenced unresolved labels (RUN_IN, BASELINE, etc.)
3. **Dosing regimens** contained fragmented prose instead of consolidated structures
4. **Visit windows** had inconsistent targetDay values

## Solution: ReconciliationLayer

A new **ReconciliationLayer** bridges execution model findings with the core USDM graph:

```
PDF → Core Extractors → Initial USDM Core
                              ↓
PDF → Execution Extractors → Execution Data
                              ↓
         ← ReconciliationLayer →
                              ↓
                     Enriched USDM Core
```

### Key Components

#### 1. ReconciliationLayer (`extraction/execution/reconciliation_layer.py`)

Main orchestrator that:
- **Promotes crossover findings** → Creates epochs/cells/arms for periods & sequences
- **Resolves traversal references** → Maps abstract concepts to actual epoch IDs
- **Consolidates dosing regimens** → Groups fragments into coherent intervention regimens
- **Normalizes visit windows** → Fixes targetDay inconsistencies
- **Classifies integrity issues** → Categorizes as blocking/warning/info

#### 2. EntityResolver (`extraction/execution/entity_resolver.py`)

LLM-based semantic entity resolution that replaces fragile fuzzy string matching:

```python
# Old approach (fragile):
if 'screen' in epoch_name.lower():
    epoch_aliases['SCREENING'] = epoch_id

# New approach (semantic LLM resolution):
resolver = EntityResolver()
context = create_resolution_context_from_design(design)
mappings = resolver.resolve_epoch_concepts(['RUN_IN', 'BASELINE'], context)
# Returns: {'BASELINE': EntityMapping(resolved_id='epoch_2', resolved_name='C-I', confidence=0.6)}
```

## Output Extensions

The reconciliation layer outputs several extension attributes for transparency:

### `x-executionModel-entityMaps`
```json
{
  "epochAliases": {
    "SCREENING": "epoch_1",
    "BASELINE": "epoch_2",
    "TREATMENT": "epoch_3"
  },
  "visitAliases": {...}
}
```

### `x-executionModel-classifiedIssues`
```json
[
  {
    "severity": "blocking",
    "category": "visit_window_conflict",
    "message": "Multiple visits mapped to Day 1",
    "affectedPath": "$.visitWindows[]",
    "affectedIds": ["visit_1", "visit_2"],
    "suggestion": "Re-derive targetDay from visit context"
  }
]
```

### Issue Severity Levels

| Severity | Description | Downstream Impact |
|----------|-------------|-------------------|
| **blocking** | Prevents reliable downstream use | Generator should skip/fail |
| **warning** | Degraded but potentially usable | Generator should proceed with caution |
| **info** | Informational only | No impact |

## Test Results

With the Alexion protocol (NCT04573309):

| Metric | Before | After |
|--------|--------|-------|
| Traversal steps resolved | 1/7 | 5/7 |
| Unresolved issues | 15 | 11 |
| Blocking issues | 1 | 1 |
| LLM semantic mappings | 0 | 4 |

Example LLM resolutions:
- `BASELINE → C-I` (confidence: 0.60)
- `TREATMENT → Inpatient Period 1` (confidence: 0.90)
- `MAINTENANCE → OP` (confidence: 0.40)
- `END_OF_STUDY → EOS or ET` (confidence: 1.00)

## Pipeline Integration

The ReconciliationLayer is called in `enrich_usdm_with_execution_model()` before adding extension attributes:

```python
# In pipeline_integration.py
try:
    reconciled_design, classified_issues, entity_maps = reconcile_usdm_with_execution_model(
        design, execution_data
    )
    design.update(reconciled_design)
    
    # Store entity maps and classified issues for downstream use
    if entity_maps:
        design['extensionAttributes'].append(...)
    if classified_issues:
        design['extensionAttributes'].append(...)
except Exception as e:
    logger.warning(f"Reconciliation layer failed: {e}")
```

## Pipeline Context Architecture

The entire pipeline now uses **PipelineContext** to accumulate extraction results, enabling each subsequent extractor to reference prior data.

```
PDF → SoA Extraction → PipelineContext
                           ↓
PDF → Metadata → adds to context
                           ↓
PDF → Eligibility → references metadata, adds to context
                           ↓
PDF → Objectives → references metadata, adds to context
                           ↓
PDF → Study Design → references all above, adds to context
                           ↓
PDF → Interventions → references design, adds to context
                           ↓
... subsequent extractors reference accumulated context ...
                           ↓
PDF → Execution Model → references ALL prior data
```

### PipelineContext

```python
from extraction.pipeline_context import PipelineContext, create_pipeline_context

# Create context from SoA extraction
pipeline_context = create_pipeline_context(soa_data)

# Each extractor updates context
pipeline_context.update_from_metadata(result.metadata)
pipeline_context.update_from_eligibility(result.data)
pipeline_context.update_from_objectives(result.data)
# ... etc

# Later extractors can reference accumulated data
if pipeline_context.has_epochs():
    traversal_result = extract_traversal_constraints(
        pdf_path=pdf_path,
        existing_epochs=pipeline_context.epochs,
    )
```

### Available Context Data
- **epochs** - Study phases from SoA
- **encounters** - Visits from SoA
- **activities** - Procedures/assessments from SoA
- **arms** - Treatment arms from study design
- **interventions** - Drugs/treatments from interventions
- **objectives/endpoints** - From objectives extraction
- **inclusion/exclusion_criteria** - From eligibility extraction

### Benefits
- Extractors reference actual IDs, not arbitrary labels
- No downstream resolution needed
- Consistent references across entire USDM output
- Better extraction accuracy with rich context

### Test Results
- Before: `Matched traversal to 1 existing SoA epoch IDs`
- After: `All traversal steps resolved to epoch IDs`

## USDM Entity Placement (v6.6)

As of v6.6, all entities are placed at their correct USDM locations per `dataStructure.yml`:

| Entity | Location |
|--------|----------|
| `timings` | `scheduleTimeline.timings[]` |
| `exits` | `scheduleTimeline.exits[]` |
| `conditions` | `studyVersion.conditions[]` |
| `analysisPopulations` | `studyDesign.analysisPopulations[]` |
| `footnote conditions` | `studyDesign.notes[]` (protocol-wide) or `activity.notes[]` (activity-specific) |

## Anchor Taxonomy (v6.7)

Time anchors are now classified into three distinct types to address the "Day 1 overload" problem where multiple anchors share the same day:

### Anchor Classifications

| Classification | Description | USDM Promotion |
|----------------|-------------|----------------|
| **VISIT** | Real encounter/visit (Screening, Day 1, Baseline) | Creates ScheduledActivityInstance with encounterId |
| **EVENT** | Activity occurrence (FirstDose, Randomization, InformedConsent) | Creates ScheduledActivityInstance linked to activity |
| **CONCEPTUAL** | Pure timing reference (CycleStart, CollectionDay) | Timing reference only, no instance created |

### Intra-Day Ordering

Anchors on the same day are now ordered semantically:

```python
INTRA_DAY_ORDER = {
    InformedConsent: 10,   # Must happen first
    Screening: 20,          # After consent
    Enrollment: 30,         # After screening
    Randomization: 40,      # After enrollment
    Baseline: 50,           # After randomization
    FirstDose: 60,          # After baseline assessments
    CycleStart: 70,         # Cycle context after dose
    Day1: 80,               # Generic Day 1 reference
    CollectionDay: 90,      # Collection windows
    Custom: 100,            # Custom anchors last
}
```

This enables synthetic generators to order events within Day 1:
- Consent < Randomization < Baseline < FirstDose < CycleStart

### TimeAnchor Schema

```python
@dataclass
class TimeAnchor:
    id: str
    definition: str
    anchor_type: AnchorType
    classification: AnchorClassification  # VISIT, EVENT, or CONCEPTUAL
    day_value: int = 1
    intra_day_order: int  # Auto-assigned from INTRA_DAY_ORDER
    relative_to_anchor_id: Optional[str] = None  # For explicit ordering chains
    encounter_id: Optional[str] = None  # Resolved for VISIT anchors
    activity_id: Optional[str] = None   # Resolved for EVENT anchors
```

## Visit Window Surfacing (v6.7)

Per feedback: "encounter windows are not surfaced directly" - windows are now surfaced on encounters as extension attributes so downstream consumers don't need to reconstruct them from timing logic.

### Extension Format

```json
{
  "id": "enc_day1",
  "name": "Day 1",
  "extensionAttributes": [
    {
      "url": "http://example.org/usdm/visitWindow",
      "valueJson": {
        "targetDay": 1,
        "windowBefore": 0,
        "windowAfter": 0,
        "windowDescription": "Day 1 (no window)"
      }
    },
    {
      "url": "http://example.org/usdm/scheduledAtTimingId",
      "valueString": "timing_day1"
    }
  ]
}
```

### Benefits

- Direct access to window info without parsing timing logic
- Encounter-centric view for downstream processing
- Timing linkage preserved via `scheduledAtTimingId`

## Future Improvements

1. **Extend SoA context to all extractors** - crossover, repetition, footnote, dosing
2. **Crossover promotion to epochs** - Currently detects but doesn't fully create period epochs
3. **Dosing consolidation** - Merge fragmented regimens into parent interventions
4. ~~**Visit window derivation**~~ - ✅ Implemented in v6.7 (windows surfaced on encounters)
5. **Confidence thresholds** - Allow configuration of minimum confidence for LLM mappings
6. **Structured cycle logic** - Promote dosing schedules into cycle length objects with on/off semantics
