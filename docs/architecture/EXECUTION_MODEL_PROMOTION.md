# Execution Model Promotion Architecture

## Feedback Validation Summary

| Issue | Valid? | Root Cause |
|-------|--------|------------|
| Auto-anchors are ScheduledActivityInstances without encounters | ✅ Yes | `execution_model_promoter.py:417-439` creates placeholder instances |
| Execution model trapped in JSON valueString | ✅ Yes | All `x-executionModel-*` extensions use `valueString` serialization |
| Visit windows only in Timing, not encounters | ✅ Yes | Windows stored as extension, not denormalized to encounters |
| Dosing logic not fully promoted | ⚠️ Partial | Promotion exists but linkage to schedule is incomplete |

---

## Architectural Changes Required

### 1. Anchor Classification System

**Problem**: Pure timing anchors (e.g., "First Dose", "Randomization") are currently modeled as `ScheduledActivityInstance` with empty `activityIds` and no `encounterId`. This is semantically weak.

**Solution**: Introduce explicit anchor classification:

```
┌─────────────────────────────────────────────────────────────┐
│                    TimeAnchor                               │
├─────────────────────────────────────────────────────────────┤
│ anchorType: VISIT | EVENT | CONCEPTUAL                     │
│                                                             │
│ VISIT      → Must resolve to an existing encounter         │
│ EVENT      → Links to activity (e.g., first dose)          │
│ CONCEPTUAL → Pure timing reference (no visit/activity)     │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**:
1. Add `anchorType` field to `TimeAnchor` schema
2. In promoter, only create `ScheduledActivityInstance` for `VISIT` anchors
3. Store `CONCEPTUAL` anchors in a dedicated `timingReferences` structure (not instances)
4. `EVENT` anchors attach to existing activities via `scheduledActivityInstanceId`

**Files to modify**:
- `extraction/execution/schema.py` - Add `AnchorType` enum with classification
- `extraction/execution/time_anchor_extractor.py` - Classify during extraction
- `extraction/execution/execution_model_promoter.py` - Route by anchor type

---

### 2. Execution Model Type System

**Problem**: All execution model data is serialized as JSON strings in `valueString`, making it:
- Not type-safe
- Not schema-validatable
- Brittle for versioning

**Solution**: Define a structured execution model schema that can be validated.

**Option A: Typed Extension Schema**
```python
# core/execution_schema.py
@dataclass
class ExecutionModelExtension:
    """Typed execution model that can be validated."""
    timeAnchors: List[TimeAnchor]
    repetitions: List[Repetition]
    visitWindows: List[VisitWindow]
    dosingRegimens: List[DosingRegimen]
    traversalConstraints: Optional[TraversalConstraints]
    stateMachine: Optional[StateMachine]
    
    def to_usdm_extension(self) -> Dict[str, Any]:
        """Serialize to single USDM extension with typed structure."""
        return {
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/executionModel",
            "instanceType": "ExtensionAttribute",
            "valueObject": {
                "schemaVersion": "1.0",
                "timeAnchors": [a.to_dict() for a in self.timeAnchors],
                "repetitions": [r.to_dict() for r in self.repetitions],
                # ... etc
            }
        }
```

**Option B: Promote to Core USDM (Preferred for key entities)**
```
TimeAnchor → Timing.relativeFromScheduledInstanceId + description
VisitWindow → Encounter.scheduledAtTimingId + windowLower/windowUpper
DosingRegimen → Administration (already partially done)
```

**Implementation**:
1. Create `core/execution_schema.py` with typed dataclasses
2. Add JSON Schema validation for execution model
3. Replace multiple `x-executionModel-*` extensions with single structured extension
4. Promote key entities to native USDM where possible

---

### 3. Window Propagation to Encounters

**Problem**: Visit windows exist in `Timing` objects but encounters don't expose their effective windows, forcing generators to traverse timing graphs.

**Solution**: Add post-processing step to denormalize windows to encounters.

```python
def propagate_windows_to_encounters(design: Dict[str, Any]) -> None:
    """
    Denormalize timing windows to encounters for easy downstream access.
    
    After this, each encounter has:
      - scheduledDay: int (nominal day)
      - windowLower: int (days before, negative)
      - windowUpper: int (days after, positive)
    """
    timings = get_all_timings(design)
    timing_map = {t['id']: t for t in timings}
    
    for encounter in design.get('encounters', []):
        timing_id = encounter.get('scheduledAtTimingId')
        if timing_id and timing_id in timing_map:
            timing = timing_map[timing_id]
            # Propagate window bounds
            if 'windowLower' in timing:
                encounter['effectiveWindowLower'] = timing['windowLower']
            if 'windowUpper' in timing:
                encounter['effectiveWindowUpper'] = timing['windowUpper']
            # Propagate scheduled day
            if 'value' in timing:
                encounter['scheduledDay'] = timing['value']
```

**Files to modify**:
- `extraction/execution/pipeline_integration.py` - Add propagation step after execution model
- `core/reconciliation/encounter_reconciler.py` - Ensure windows survive reconciliation

---

### 4. Enhanced Reconciliation for Dosing Linkage

**Problem**: Dosing regimens are extracted but not fully wired to the schedule.

**Solution**: Reconciliation layer should:
1. Link dosing regimens to specific encounters (administration windows)
2. Promote titration rules to structured timing constraints
3. Create dose-at-encounter relationships

```
┌─────────────────────────────────────────────────────────────┐
│              Dosing → Schedule Linkage                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  DosingRegimen                                              │
│    ├── treatmentName: "ALXN1840"                           │
│    ├── dose: "30 mg"                                       │
│    ├── frequency: "QD"                                     │
│    └── administrationWindowIds: [enc_day1, enc_day2, ...]  │
│                                                             │
│  Maps to:                                                   │
│    Administration (USDM native)                            │
│      ├── dose                                              │
│      ├── doseFrequency                                     │
│      └── linkedToEncounterIds (new extension)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Flow Changes

### Current Flow
```
SoA Extraction → Expansion Phases → Execution Model → Extensions (JSON strings)
```

### Proposed Flow
```
SoA Extraction
    ↓
Expansion Phases
    ↓
Execution Model Extraction
    ↓
┌─────────────────────────────────────────┐
│ NEW: Execution Model Classification     │
│   - Classify anchors (VISIT/EVENT/CONCEPTUAL)
│   - Validate execution entities         │
│   - Build typed ExecutionModelExtension │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ NEW: Execution Model Promotion          │
│   - Promote VISIT anchors to encounters │
│   - Promote dosing to Administrations   │
│   - Link regimens to encounters         │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ NEW: Window Propagation                 │
│   - Denormalize timing windows          │
│   - Add effectiveWindow* to encounters  │
└─────────────────────────────────────────┘
    ↓
Reconciliation → Final USDM
```

---

## Implementation Priority

| Change | Impact | Effort | Priority | Status |
|--------|--------|--------|----------|--------|
| Anchor classification | High | Medium | P1 | ✅ DONE |
| Window propagation | High | Low | P1 | ✅ DONE |
| Typed execution schema | Medium | High | P2 | ✅ DONE |
| Dosing linkage | Medium | Medium | P2 | 📋 Planned |

---

## Implementation Status

### ✅ Completed (Jan 2026)

#### 1. Anchor Classification System

**Files modified:**
- `extraction/execution/schema.py` - Added `AnchorClassification` enum and `_classify_anchor()` function
- `extraction/execution/execution_model_promoter.py` - Added classification-based anchor handling

**Changes:**
```python
class AnchorClassification(Enum):
    VISIT = "Visit"          # Creates ScheduledActivityInstance with encounter
    EVENT = "Event"          # Links to existing activity instance
    CONCEPTUAL = "Conceptual"  # Pure timing reference (no instance)
```

**Behavior:**
- VISIT anchors (Day 1, Baseline, Screening) → Create `ScheduledActivityInstance` with `encounterId`
- EVENT anchors (First Dose, Randomization) → Attach to existing activity or store as conceptual
- CONCEPTUAL anchors (Cycle, Period) → Store in `x-executionModel-conceptualAnchors` extension

#### 2. Window Propagation to Encounters

**Files modified:**
- `extraction/execution/pipeline_integration.py` - Added `propagate_windows_to_encounters()` function

**Changes:**
Each encounter now has (when timing data available):
- `effectiveWindowLower`: int (days before nominal, typically negative)
- `effectiveWindowUpper`: int (days after nominal, typically positive)  
- `scheduledDay`: int (nominal study day)

**Benefits:**
- Downstream generators no longer need to traverse timing graphs
- Visit windows are directly accessible on encounters
- Consistent day values derived from multiple sources

#### 3. Typed Execution Model Schema

**Files modified:**
- `extraction/execution/schema.py` - Added `ExecutionModelExtension` class and `get_execution_model_json_schema()`
- `extraction/execution/pipeline_integration.py` - Added unified typed extension output

**Changes:**
```python
@dataclass
class ExecutionModelExtension:
    """Unified typed extension for execution model data."""
    schemaVersion: str = "1.0.0"
    extractionTimestamp: Optional[str] = None
    data: Optional[ExecutionModelData] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    integrityIssues: List[Dict[str, Any]] = field(default_factory=list)
    promotionResult: Optional[Dict[str, Any]] = None
```

**Key features:**
- Uses `valueObject` instead of `valueString` for typed data
- Includes JSON Schema via `get_execution_model_json_schema()`
- Outputs alongside existing `x-executionModel-*` for backward compatibility
- Schema version for future migrations

**Example USDM output:**
```json
{
  "id": "ext_execution_model_...",
  "url": "https://protocol2usdm.io/extensions/x-executionModel",
  "instanceType": "ExtensionAttribute",
  "valueObject": {
    "schemaVersion": "1.0.0",
    "extractionTimestamp": "2026-01-23T01:50:00Z",
    "executionModel": {
      "timeAnchors": [...],
      "repetitions": [...],
      "visitWindows": [...]
    }
  }
}
```

---

### 📋 Planned (Future)

#### 4. Dosing → Schedule Linkage

**Goal:** Link dosing regimens to specific encounters.

**Approach:**
- Add `administrationWindowIds` to `DosingRegimen`
- Create dose-at-encounter relationships
- Promote titration rules to structured timing constraints

---

## Migration Strategy

1. **Phase 1**: Anchor classification + window propagation (non-breaking) ✅ DONE
2. **Phase 2**: Introduce typed ExecutionModelExtension alongside existing extensions
3. **Phase 3**: Deprecate individual `x-executionModel-*` extensions
4. **Phase 4**: Full promotion of key entities to native USDM

