# Execution Model Fixes - Addressing Reviewer Feedback

## Overview

This document tracks the fixes needed to address the feedback about the USDM execution model output from Protocol2USDMv3. The core issue is that while extensions contain correct execution semantics, they are **loosely coupled** to the base USDM model, causing downstream consumers to behave incorrectly.

---

## Issue A: Base USDM Model Contradicts Crossover Design

### Problem
`studyDesign.model` is set to "Parallel Study" (C82639) based on arm count, even when `x-executionModel-crossoverDesign.isCrossover=true`.

### Location
- `main_v2.py` lines 837-857
- `core/usdm_types_generated.py` lines 395-400

### Fix
In `enrich_usdm_with_execution_model()`, when crossover design is detected, update the base model:

```python
# If crossover detected, override base model
if execution_data.crossover_design and execution_data.crossover_design.is_crossover:
    design['model'] = {
        "id": "code_model_1",
        "code": "C49649",  # CDISC code for Crossover Study
        "codeSystem": "http://www.cdisc.org",
        "codeSystemVersion": "2024-09-27",
        "decode": "Crossover Study",
        "instanceType": "Code"
    }
```

---

## Issue B: Period/Day Semantics Inconsistent

### Problem
Encounters like "Period 2 (Day -1)" are just labels with no machine-readable ordering relationship.

### Fix
Add epoch transition rules with min/max gaps and within-epoch day offsets:

```python
# In traversal_constraints or as separate extension
"epochTransitions": [
    {
        "fromEpoch": "PERIOD_1",
        "toEpoch": "WASHOUT",
        "minGapDays": 0,
        "maxGapDays": 0
    },
    {
        "fromEpoch": "WASHOUT",
        "toEpoch": "PERIOD_2",
        "minGapDays": 3,
        "maxGapDays": 14
    }
]
```

---

## Issue C: Repetitions Not Bound to Activities

### Problem
Repetition patterns exist in `x-executionModel-repetitions` but no linkage like:
- "Plasma Glucose for PD uses rep_interval_9 (PT5M)"
- "PK (Glucagon) uses rep_interval_5 (PT15M)"

### Fix
Create activity-to-execution binding map:

```python
# Add to each ScheduledActivityInstance.extensionAttributes
"x-executionModel-binding": {
    "timeAnchorId": "anchor_treatment_admin",
    "repetitionId": "rep_interval_9",
    "nominalTimepoints": ["PT0M", "PT5M", "PT10M", "PT15M", "PT20M", "PT25M", "PT30M"],
    "offsetFromAnchor": "PT0M"
}
```

Or add a mapping block at studyDesign level:

```python
"x-executionModel-activityBindings": [
    {
        "activityId": "act_plasma_glucose",
        "timeAnchorId": "anchor_treatment_admin",
        "repetitionId": "rep_interval_9",
        "samplingConstraintId": "constraint_pd_glucose"
    },
    {
        "activityId": "act_pk_glucagon",
        "timeAnchorId": "anchor_treatment_admin",
        "repetitionId": "rep_interval_5",
        "samplingConstraintId": "constraint_pk"
    }
]
```

---

## Issue D: Missing PD Glucose Sampling Constraint

### Problem
Only PK sampling constraint exists. PD glucose needs explicit constraint for:
- Nadir window (0-10 min)
- Treatment success window (0-30 min)
- Follow-out window (to 240 min)

### Fix
Add PD sampling constraint in `extract_sampling_density`:

```python
SamplingConstraint(
    id="constraint_pd_glucose_nadir",
    activity_id="act_plasma_glucose",
    domain="PD",
    min_observations=3,
    timepoints=["PT0M", "PT5M", "PT10M"],
    window_start="PT0M",
    window_end="PT10M",
    anchor_id="anchor_treatment_admin",
    rationale="Nadir detection requires observations at 0, 5, 10 min",
    source_text="...",
)

SamplingConstraint(
    id="constraint_pd_glucose_success",
    activity_id="act_plasma_glucose",
    domain="PD",
    min_observations=7,
    timepoints=["PT0M", "PT5M", "PT10M", "PT15M", "PT20M", "PT25M", "PT30M"],
    window_start="PT0M",
    window_end="PT30M",
    anchor_id="anchor_treatment_admin",
    rationale="Treatment success per primary endpoint requires observations through 30 min",
    source_text="...",
)
```

---

## Issue E: Traversal Constraints Reference Non-Existent Epochs

### Problem
Traversal constraints reference `END_OF_STUDY` and `EARLY_TERMINATION` but these don't exist in epochs/encounters.

### Fix
1. Create explicit EOS/ET epochs in the schedule extraction
2. Ensure traversal constraints reference actual epoch IDs from the USDM

```python
# In enrich function, validate traversal references
for constraint in execution_data.traversal_constraints:
    epoch_ids = {e.get('id') for e in design.get('epochs', [])}
    encounter_ids = {e.get('id') for e in design.get('encounters', [])}
    
    # Map abstract names to real IDs or create missing epochs
    resolved_sequence = []
    for step in constraint.required_sequence:
        if step in epoch_ids or step in encounter_ids:
            resolved_sequence.append(step)
        else:
            # Create the missing epoch
            new_epoch = create_epoch(step)
            design['epochs'].append(new_epoch)
            resolved_sequence.append(new_epoch['id'])
    
    constraint.required_sequence = resolved_sequence
```

---

## Implementation Order

1. **Fix A (Critical)**: Set base model correctly - ~30 min
2. **Fix C (Critical)**: Bind timing to activities - ~2 hours
3. **Fix D (Critical)**: Add PD sampling constraints - ~1 hour
4. **Fix E (Medium)**: Resolve traversal constraints - ~1 hour
5. **Fix B (Medium)**: Add epoch transition rules - ~1 hour

---

## Test Cases

1. **Crossover detection**: Verify base model is "Crossover Study" when crossover detected
2. **Activity binding**: Verify PK/PD activities have timeAnchorId, repetitionId refs
3. **PD constraints**: Verify glucose sampling constraint exists with 0-30 min window
4. **Traversal resolution**: Verify all epoch IDs in traversal exist in epochs array
