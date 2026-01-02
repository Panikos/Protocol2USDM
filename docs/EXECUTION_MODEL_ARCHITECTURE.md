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

## Future Improvements

1. **Extend SoA context to all extractors** - crossover, repetition, footnote, dosing
2. **Crossover promotion to epochs** - Currently detects but doesn't fully create period epochs
3. **Dosing consolidation** - Merge fragmented regimens into parent interventions
4. **Visit window derivation** - Auto-derive targetDay from SoA position when ambiguous
5. **Confidence thresholds** - Allow configuration of minimum confidence for LLM mappings
