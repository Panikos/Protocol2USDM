# Execution Model Extension Schema

This document defines the structured extension schema for execution model concepts. As of v7.2, many concepts are **promoted to native USDM entities** by the `ExecutionModelPromoter`. Extensions are retained for backward compatibility and to carry additional detail not representable in core USDM.

## Extension Namespace

All Protocol2USDM extensions use the namespace: `https://protocol2usdm.io/extensions/`

## Concepts Requiring Extensions

The following extensions are written to `extensionAttributes` on appropriate USDM entities:

| Concept | Extension URL | Attached To | Promoted in v7.2? |
|---------|---------------|-------------|--------------------|
| Time Anchors | `x-executionModel-timeAnchors` | StudyDesign | Partially (→ ScheduledActivityInstance) |
| Repetitions | `x-executionModel-repetitions` | StudyDesign | Partially (→ ScheduledActivityInstance expansion) |
| Sampling Constraints | `x-executionModel-samplingConstraints` | Activity, ScheduleTimeline | No |
| Execution Type Classifications | `x-executionModel-executionType` | Activity | No |
| Crossover Design | `x-executionModel-crossoverDesign` | StudyDesign | Partially (periods → Epoch) |
| Traversal Constraints | `x-executionModel-traversalConstraints` | StudyDesign | Yes (→ Epoch.previousId/nextId) |
| Visit Windows | `x-executionModel-visitWindows` | StudyDesign | Yes (→ Timing.windowLower/Upper) |
| Dosing Regimens | `x-executionModel-dosingRegimens` | StudyDesign | Yes (→ Administration entities) |
| State Machine | `x-executionModel-stateMachine` | StudyDesign | Yes (→ TransitionRule on Encounter) |
| Endpoint Algorithms | `x-executionModel-endpointAlgorithms` | StudyDesign | Partially (→ Estimand) |
| Derived Variable Rules | `x-executionModel-derivedVariables` | StudyDesign | No |
| Analysis Windows | `x-executionModel-analysisWindows` | StudyDesign | No |
| Randomization Details | `x-executionModel-randomizationScheme` | StudyDesign | No |
| Conceptual Time Anchors | `x-executionModel-conceptualAnchors` | ScheduleTimeline | No |
| Titration Schedules | `x-executionModel-titrationSchedules` | StudyDesign | Yes (→ StudyElement + TransitionRule) |
| Activity Bindings | `x-executionModel-activityBindings` | StudyDesign | No |
| Instance Bindings | `x-executionModel-instanceBindings` | StudyDesign | No |
| Entity Mappings | `x-executionModel-entityMappings` | StudyDesign | No (debug/transparency) |
| Entity Maps | `x-executionModel-entityMaps` | StudyDesign | No (debug/transparency) |
| Promotion Issues | `x-executionModel-promotionIssues` | StudyDesign | No (debug/transparency) |
| Classified Issues | `x-executionModel-classifiedIssues` | StudyDesign | No (debug/transparency) |
| Integrity Issues | `x-executionModel-integrityIssues` | StudyDesign | No (debug/transparency) |

---

## Extension Schemas

### 1. Sampling Constraints

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-samplingConstraints`

**Purpose**: Defines observation density rules (e.g., "at least 3 samples within 2 hours post-dose").

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-samplingConstraints",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"activityId\": \"act_123\", \"minSamples\": 3, \"maxSamples\": 5, \"windowDuration\": \"PT2H\", \"relativeTo\": \"FirstDose\"}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface SamplingConstraint {
  activityId: string;           // Reference to Activity
  minSamples?: number;          // Minimum samples required
  maxSamples?: number;          // Maximum samples allowed
  windowDuration?: string;      // ISO 8601 duration
  relativeTo?: string;          // Anchor reference
  notes?: string;               // Additional constraints
}
```

---

### 2. Execution Type Classification

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-executionType`

**Purpose**: Classifies activities as WINDOW, EPISODE, SINGLE, or RECURRING for synthetic data generation.

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-executionType",
  "instanceType": "ExtensionAttribute",
  "valueString": "WINDOW"
}
```

**Valid Values**:
- `WINDOW` - Activity occurs within a visit window (e.g., ±3 days)
- `EPISODE` - Activity spans a duration (e.g., 14-day treatment period)
- `SINGLE` - Activity occurs once at a specific timepoint
- `RECURRING` - Activity repeats on a schedule (e.g., daily)

---

### 3. Endpoint Algorithm

**URL**: `https://protocol2usdm.io/extensions/x-algorithm`

**Purpose**: Stores the computational formula for endpoint calculation (the "how" that Estimand doesn't capture).

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-algorithm",
  "instanceType": "ExtensionAttribute",
  "valueString": "PG >= 70 OR (PG - nadir) >= 20"
}
```

**Attached to**: `Estimand.extensionAttributes[]`

---

### 4. Derived Variables

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-derivedVariables`

**Purpose**: Defines derivation rules like change-from-baseline, LOCF, MMRM imputation.

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-derivedVariables",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"name\": \"CFB_PG\", \"type\": \"ChangeFromBaseline\", \"sourceVariable\": \"PG\", \"baselineVisit\": \"Day 1\"}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface DerivedVariable {
  id?: string;
  name: string;
  type: "ChangeFromBaseline" | "PercentChange" | "LOCF" | "MMRM" | "AUC" | "Custom";
  sourceVariable: string;
  baselineVisit?: string;       // For CFB calculations
  imputationMethod?: string;    // For missing data handling
  formula?: string;             // For custom derivations
}
```

---

### 5. Analysis Windows

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-analysisWindows`

**Purpose**: Defines temporal analysis phases (baseline period, accumulation phase, steady-state window).

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-analysisWindows",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"name\": \"Baseline\", \"startDay\": -7, \"endDay\": 0}, {\"name\": \"Accumulation\", \"startDay\": 1, \"endDay\": 10}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface AnalysisWindow {
  id?: string;
  name: string;
  startDay: number;
  endDay: number;
  type?: "Baseline" | "Accumulation" | "SteadyState" | "Treatment" | "Washout";
  description?: string;
}
```

---

### 6. Randomization Scheme

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-randomizationScheme`

**Purpose**: Operational randomization details beyond USDM's scope.

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-randomizationScheme",
  "instanceType": "ExtensionAttribute",
  "valueString": "{\"allocationRatio\": \"1:1\", \"blockSize\": [4, 6], \"stratificationFactors\": [\"Site\", \"Disease Severity\"], \"method\": \"IWRS\"}"
}
```

**Schema for valueString (JSON object)**:
```typescript
interface RandomizationScheme {
  allocationRatio: string;              // e.g., "1:1", "2:1"
  blockSize?: number | number[];        // Fixed or variable block sizes
  stratificationFactors?: string[];     // Stratification variables
  method?: "IWRS" | "IXRS" | "Central" | "Site";
  seed?: number;                        // For reproducibility
}
```

---

### 7. Conceptual Time Anchors

**URL**: `https://protocol2usdm.io/extensions/x-executionModel-conceptualAnchors`

**Purpose**: Pure timing references that don't create visit or activity instances.

```json
{
  "id": "string (UUID)",
  "url": "https://protocol2usdm.io/extensions/x-executionModel-conceptualAnchors",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"anchor_cycle\", \"name\": \"CycleStart\", \"classification\": \"Conceptual\", \"note\": \"Pure timing reference\"}]"
}
```

---

## Usage Guidelines

1. **Attach to appropriate entity**: Extensions should be attached to the most semantically relevant USDM entity.

2. **Use JSON for complex data**: The `valueString` field contains JSON-serialized data. Parse with standard JSON libraries.

3. **Version compatibility**: Extensions are versioned with the Protocol2USDM output. Check `generator` field for version.

4. **Discoverability**: The `url` field provides a stable identifier. Consumers can filter by URL to find specific extensions.

5. **Fallback behavior**: Consumers that don't understand an extension should ignore it gracefully.

---

## Promoted Concepts (v7.2)

The following concepts are now promoted to **native USDM entities** by the `ExecutionModelPromoter` (`extraction/execution/execution_model_promoter.py`). Extensions are retained for backward compatibility and additional detail.

| Concept | USDM Entity | Notes |
|---------|-------------|-------|
| Footnote Conditions | `Condition`, `ScheduledDecisionInstance` | `appliesToIds` links to activities |
| Visit Windows | `Timing.windowLower/Upper` | ISO 8601 duration bounds |
| State Machine | `TransitionRule` on `Encounter` | `transitionStartRule`, `transitionEndRule` |
| Traversal Constraints | `StudyEpoch.previousId/nextId` | Epoch sequence chain |
| Endpoint Algorithms | `Estimand` | Algorithm formula kept in extension |
| Titration Schedules | `StudyElement` | With `transitionStartRule` |
| Dosing Regimens | `Administration` | Linked to `StudyIntervention` |
| Time Anchors | `ScheduledActivityInstance` | Anchor metadata in instance |
| Repetitions | `ScheduledActivityInstance` (expanded) | Multiple instances per occurrence |
| Crossover Periods | `StudyEpoch` | Periods and washouts as first-class epochs |

**Key principle:** Core USDM output (`protocol_usdm.json`) is self-sufficient without parsing extensions. Extensions provide additional detail and debug transparency.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-30 | Initial schema based on USDM v4.0 gap analysis |
