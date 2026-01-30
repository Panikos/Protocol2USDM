# Protocol2USDM Architecture

## Overview

Protocol2USDM extracts Schedule of Activities (SoA) and other structured data from clinical trial protocols and converts it to USDM v4.0 compliant JSON.

## Schema-Driven Architecture

As of v6.0, the pipeline uses a **schema-driven architecture** where all types, prompts, and validation are derived from the official CDISC dataStructure.yml schema.

### Source of Truth

```
https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
```

This YAML file contains:
- 86+ USDM entity definitions
- NCI C-codes for entities and attributes
- Official definitions
- Cardinality constraints (required vs optional)
- Relationship types

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   dataStructure.yml                              │
│                 (Official CDISC Schema)                          │
│                 Cached: core/schema_cache/                       │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                core/usdm_schema_loader.py                        │
│  - Downloads and caches official schema                          │
│  - Parses YAML → EntityDefinition objects                        │
│  - Provides metadata: NCI codes, definitions, cardinality        │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ usdm_types_   │   │ schema_prompt │   │ validation/   │
│ generated.py  │   │ _generator.py │   │ usdm_*        │
│               │   │               │   │               │
│ Python types  │   │ LLM prompts   │   │ Schema info   │
│ with defaults │   │ with schema   │   │ for fixing    │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     core/usdm_types.py                           │
│  - Single interface for all USDM types                           │
│  - Official types + internal extraction types                    │
│  - Backward compatible exports                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Extraction Pipeline                           │
│  extraction/header_analyzer.py → extraction/text_extractor.py   │
│                            ↓                                     │
│              main_v3.py (phase registry) or main_v2.py (legacy)  │
│                            ↓                                     │
│               enrichment/terminology.py (NCI EVS)                │
│                  ↓ (uses core/evs_client.py)                     │
│                validation/cdisc_conformance.py                   │
│                            ↓                                     │
│                   protocol_usdm.json (compliant)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase Registry Architecture (v7.1+)

The `main_v3.py` entry point uses a **phase registry pattern** that provides modular, extensible, and parallelizable extraction phases.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       main_v3.py                                 │
│  - CLI argument parsing                                          │
│  - Default --complete mode when no phases specified              │
│  - Orchestrates SoA + expansion phases                           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  pipeline/orchestrator.py                        │
│  - PipelineOrchestrator class                                    │
│  - run_phases() - sequential execution                           │
│  - run_phases_parallel() - concurrent execution                  │
│  - combine_to_full_usdm() - merge all results                    │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  pipeline/phase_registry.py                      │
│  - PhaseRegistry singleton                                       │
│  - register_phase() decorator                                    │
│  - get_all(), get(name), get_by_order()                         │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Eligibility  │   │   Metadata    │   │  Objectives   │
│    Phase      │   │    Phase      │   │    Phase      │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ extract()     │   │ extract()     │   │ extract()     │
│ combine()     │   │ combine()     │   │ combine()     │
│ save_result() │   │ save_result() │   │ save_result() │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  pipeline/base_phase.py                          │
│  - BasePhase abstract class                                      │
│  - PhaseConfig dataclass (name, output_filename, etc.)           │
│  - PhaseResult dataclass (success, data, error)                  │
│  - Default save_result() implementation                          │
└─────────────────────────────────────────────────────────────────┘
```

### Phase Interface

Each phase implements `BasePhase` with three key methods:

```python
class MyPhase(BasePhase):
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="MyPhase",
            display_name="My Extraction Phase",
            phase_number=10,
            output_filename="my_output.json",
        )
    
    def extract(self, pdf_path, model, output_dir, context, **kwargs) -> PhaseResult:
        """Run the extraction logic."""
        # ... extraction code ...
        return PhaseResult(success=True, data=result_data)
    
    def combine(self, result, study_version, study_design, combined, previous_extractions):
        """Merge extracted data into final USDM structure."""
        if result.success and result.data:
            study_design['myEntities'] = result.data.to_dict()['entities']
```

### Registered Phases

| Phase | Name | Output File | Dependencies |
|-------|------|-------------|--------------|
| 1 | Eligibility | `3_eligibility_criteria.json` | None |
| 2 | Metadata | `2_study_metadata.json` | None |
| 3 | Objectives | `4_objectives_endpoints.json` | Metadata |
| 4 | StudyDesign | `5_study_design.json` | None |
| 5 | Interventions | `6_interventions.json` | StudyDesign |
| 7 | Narrative | `7_narrative_structure.json` | None |
| 8 | Advanced | `8_advanced_entities.json` | None |
| 10 | Procedures | `9_procedures_devices.json` | None |
| 11 | Scheduling | `10_scheduling_logic.json` | None |
| 12 | DocStructure | `13_document_structure.json` | None |
| 13 | AmendmentDetails | `14_amendment_details.json` | Advanced |
| 14 | Execution | `11_execution_model.json` | All above |

### Parallel Execution

Independent phases can run concurrently using `--parallel`:

```bash
python main_v3.py protocol.pdf --parallel --max-workers 4
```

The orchestrator builds a dependency graph and groups phases into "waves":

```
Wave 1 (parallel): Eligibility, Metadata, StudyDesign, Narrative, Advanced, Procedures, Scheduling, DocStructure
Wave 2 (parallel): Objectives, Interventions, AmendmentDetails
Wave 3 (sequential): Execution (depends on all)
```

### Default `--complete` Mode

When no specific phases are requested, `main_v3.py` defaults to `--complete`:

```python
# In main_v3.py
if not any_phase_specified:
    args.complete = True  # Full extraction + post-processing
```

This behavior differs from `main_v2.py` which defaults to SoA-only extraction.

---

## SoA Extraction Model Fallback (v6.9+)

Certain models have issues with the complex JSON output format required for SoA text extraction. The pipeline automatically falls back to a more reliable model for this specific step.

### Fallback Configuration

```python
# In extraction/pipeline.py
SOA_FALLBACK_MODELS = {
    'gemini-3-flash-preview': 'gemini-2.5-pro',
    'gemini-3-flash': 'gemini-2.5-pro',
}
```

### How It Works

```
Main Model: gemini-3-flash-preview
                    │
Step 1: Header Analysis ────► gemini-3-flash-preview (works fine)
                    │
Step 2: Text Extraction ───► gemini-2.5-pro (automatic fallback)
                    │
Step 3-6: Continue ─────────► gemini-3-flash-preview
```

**Why?** Gemini 3 Flash models have issues complying with the specific flat JSON structure required:
```json
{
  "activities": [...],
  "activityTimepoints": [...]
}
```
Instead, they often return nested USDM-like structures with `study.studyDesigns.activityGroups`, which breaks extraction.

### Response Validation & Retry

The `extract_soa_from_text()` function now includes validation and retry logic:

```python
# In extraction/text_extractor.py
def validate_extraction_response(data: dict, min_activities: int = 1) -> tuple[bool, str]:
    """Validate LLM response structure for SoA extraction."""
    # Check for required root key
    if 'activities' not in data:
        return False, "Missing 'activities' key at root"
    
    # Detect wrong nested structure
    if 'study' in data or 'studyDesigns' in data:
        return False, "Wrong format: nested USDM structure instead of flat JSON"
    
    # Ensure minimum activities
    activities = data.get('activities', [])
    if len(activities) < min_activities:
        return False, f"Too few activities: {len(activities)} < {min_activities}"
    
    return True, ""
```

On validation failure, retry up to 2 times with correction prompt:
```
Your previous response had an invalid format: {error}
REMINDER: Return FLAT JSON with only "activities" and "activityTimepoints" at root
```

### Vertex AI Endpoint Isolation

Fixed environment pollution issue where Gemini 3's global endpoint setting affected fallback models:

```python
# Before (problematic):
os.environ['GOOGLE_CLOUD_LOCATION'] = 'global'  # Pollutes env

# After (fixed):
self._genai_client = genai_new.Client(
    vertexai=True,
    project=project,
    location='global',  # Explicit, doesn't pollute env
)
```

---

## Core Modules

### `core/usdm_schema_loader.py`

Loads and parses the official CDISC dataStructure.yml schema.

```python
from core.usdm_schema_loader import get_schema_loader, get_entity_definition

# Get schema loader
loader = get_schema_loader()
entities = loader.load()  # Returns Dict[str, EntityDefinition]

# Get specific entity info
activity_def = get_entity_definition("Activity")
print(activity_def.nci_code)  # "C71473"
print(activity_def.required_attributes)  # ['id', 'name', 'instanceType']
```

### `core/usdm_types_generated.py`

Python dataclasses for all 86+ official USDM entities. Generated from schema with:
- **Idempotent UUID generation** - UUIDs generated once on first `to_dict()` call and stored
- Default values for required Code fields
- Intelligent type inference (e.g., Encounter.type from name)

```python
from core.usdm_types_generated import Code, StudyArm, Encounter

# All required fields auto-populated
arm = StudyArm(name="Treatment Arm")
arm_dict = arm.to_dict()
# Includes: id, type, dataOriginType, dataOriginDescription

# ID is idempotent - same UUID returned on every call
assert arm.to_dict()['id'] == arm.to_dict()['id']  # Always True
```

**ID Generation Details:**

All entity classes inherit `_ensure_id()` from `USDMEntity` base class:
- If `self.id` is empty, generates a UUID and stores it in `self.id`
- Subsequent calls return the same UUID
- This ensures consistency between data output and provenance tracking

### `core/usdm_types.py`

Main interface that re-exports from `usdm_types_generated.py` plus internal extraction types.

```python
from core.usdm_types import (
    # Official USDM types
    Activity, Encounter, StudyEpoch, ScheduleTimeline,
    
    # Internal extraction types (not official USDM)
    Timeline, HeaderStructure, PlannedTimepoint, ActivityTimepoint,
)
```

### `core/schema_prompt_generator.py`

Generates LLM prompts directly from the schema.

```python
from core.schema_prompt_generator import SchemaPromptGenerator

generator = SchemaPromptGenerator()

# Generate SoA extraction prompt
prompt = generator.generate_soa_prompt()

# Generate entity groups for reference
groups = generator.generate_entity_groups()

# Save all prompt files
generator.save_prompt("output/1_llm_prompt.txt")
generator.save_entity_groups("output/1_llm_entity_groups.json")
```

## Type Categories

### Official USDM Types (from schema)

These are defined in the CDISC dataStructure.yml and generated into Python dataclasses:

| Category | Types |
|----------|-------|
| **Core** | Code, AliasCode, CommentAnnotation, Range, Quantity, Duration |
| **Study Structure** | Study, StudyVersion, StudyDesign, StudyArm, StudyCell, StudyCohort |
| **Metadata** | StudyTitle, StudyIdentifier, Organization, Indication, Abbreviation |
| **SoA** | Activity, Encounter, StudyEpoch, ScheduleTimeline, ScheduledActivityInstance, Timing |
| **Eligibility** | EligibilityCriterion, EligibilityCriterionItem, StudyDesignPopulation |
| **Objectives** | Objective, Endpoint, Estimand, IntercurrentEvent |
| **Interventions** | StudyIntervention, Administration, AdministrableProduct, Procedure |

### Internal Extraction Types (not official USDM)

These are used only during extraction and convert to official types:

| Type | Purpose | Converts To |
|------|---------|-------------|
| `PlannedTimepoint` | SoA column representation | `Timing` |
| `ActivityTimepoint` | SoA tick/matrix cell | `ScheduledActivityInstance` |
| `ActivityGroup` | Row section header | `Activity` with `childIds` |
| `HeaderStructure` | Vision extraction anchor | Discarded after use |
| `Timeline` | Extraction container | `StudyDesign` |

**ActivityTimepoint Key Fields:**
- `activityId`: Reference to Activity (act_1, act_2, ...)
- `encounterId`: Reference to Encounter (enc_1, enc_2, ...) - **primary field**
- `plannedTimepointId`: Legacy field (pt_1, pt_2, ...) - backward compat only
- `footnoteRefs`: Superscript references (["a", "m"]) for ticks like X^a

### ScheduledActivityInstance Enhancements (v6.7+)

When `ActivityTimepoint` converts to `ScheduledActivityInstance`, additional USDM conformance enhancements are applied:

| Enhancement | Description |
|-------------|-------------|
| **epochId** | Inherited from linked Encounter's `epochId` |
| **name** | Human-readable format: `"Activity Name @ Encounter Name"` |
| **timingId** | Linked to matching Timing entity (when scheduling data available) |

**Conversion Flow:**

```
ActivityTimepoint                      ScheduledActivityInstance
─────────────────                      ─────────────────────────
activityId: "act_1"         ──►        activityIds: ["uuid-for-act_1"]
encounterId: "enc_1"        ──►        encounterId: "uuid-for-enc_1"
                                       epochId: "uuid-for-epoch_1"  (from encounter)
                                       name: "Blood Draw @ Day 1"   (resolved names)
                                       timingId: "uuid-for-timing"  (if matched)
```

**Timing Linking Logic (`link_timing_ids_to_instances`):**

1. Build encounter ID → name lookup from `studyDesign.encounters`
2. Build timing name/valueLabel → ID lookup from `scheduleTimeline.timings`
3. For each instance, match encounter name to timing name/valueLabel
4. Set `timingId` on instances that match

## Required Fields

The schema defines which fields are required. Key ones enforced:

### Code
- `id`, `code`, `codeSystem`, `codeSystemVersion`, `decode`, `instanceType`

### StudyArm
- `id`, `name`, `type`, `dataOriginType`, `dataOriginDescription`, `instanceType`

### Encounter
- `id`, `name`, `type`, `instanceType`

### StudyEpoch
- `id`, `name`, `type`, `instanceType`

### ScheduleTimeline
- `id`, `name`, `entryCondition`, `entryId`, `instanceType`

### AliasCode (blindingSchema)
- `id`, `standardCode`, `instanceType`

## USDM Output Structure (v4.0 Compliant)

The output follows the official CDISC USDM v4.0 structure from `dataStructure.yml`. Entities are placed at their correct hierarchical levels:

### Entity Placement Hierarchy

```
Root Level:
└── studyDefinitionDocument     # Protocol document metadata

Study:
└── versions[]                  # StudyVersion array
    ├── titles[]                # Study titles
    ├── studyIdentifiers[]      # NCT, EudraCT, etc.
    ├── organizations[]         # Sponsor, CRO, etc.
    ├── eligibilityCriterionItems[]  # Actual criterion text
    ├── narrativeContentItems[] # Protocol sections
    ├── abbreviations[]         # Abbreviation definitions
    ├── conditions[]            # Scheduling conditions
    ├── amendments[]            # Protocol amendments
    ├── administrableProducts[] # Drug products
    ├── medicalDevices[]        # Medical devices
    ├── studyInterventions[]    # Interventions
    └── studyDesigns[]          # StudyDesign array
        ├── eligibilityCriteria[]    # Criterion references
        ├── indications[]            # Disease indications
        ├── population               # Study population
        ├── analysisPopulations[]    # SAP populations
        ├── objectives[]             # Study objectives
        ├── endpoints[]              # Study endpoints
        ├── activities[]             # Study activities
        │   └── definedProcedures[]  # Procedures per activity
        ├── encounters[]             # Study visits
        ├── epochs[]                 # Study phases
        ├── arms[]                   # Treatment arms
        ├── studyCells[]             # Arm-epoch intersections
        ├── notes[]                  # Protocol-wide footnotes
        └── scheduleTimelines[]      # Timeline definitions
            ├── timings[]            # Timing constraints
            └── exits[]              # Exit conditions
```

### Key Placement Rules (per dataStructure.yml)

| Entity | Correct Location | NOT at |
|--------|-----------------|--------|
| `eligibilityCriterionItems` | `studyVersion` | ~~studyDesign~~ |
| `organizations` | `studyVersion` | ~~study~~ |
| `narrativeContentItems` | `studyVersion` | ~~root~~ |
| `abbreviations` | `studyVersion` | ~~root~~ |
| `conditions` | `studyVersion` | ~~root~~ |
| `amendments` | `studyVersion` | ~~root~~ |
| `administrableProducts` | `studyVersion` | ~~root~~ |
| `medicalDevices` | `studyVersion` | ~~root~~ |
| `studyInterventions` | `studyVersion` | ~~studyDesign~~ |
| `indications` | `studyDesign` | ~~study~~ |
| `analysisPopulations` | `studyDesign` | ~~root~~ |
| `timings` | `scheduleTimeline` | ~~root~~ |
| `exits` | `scheduleTimeline` | ~~root~~ |
| `definedProcedures` | `activity` | ~~root~~ |

---

## Execution Model Promotion

The pipeline extracts rich execution model data (time anchors, repetitions, dosing regimens) which must be materialized into **core USDM** rather than stored only in extensions. This ensures downstream consumers (synthetic generators) can use core USDM without parsing extensions.

### Architecture

```
PDF → Execution Extractors → Execution Model Data
                                    ↓
                          ExecutionModelPromoter
                                    ↓
                          Core USDM Entities:
                            - ScheduledActivityInstance (anchors)
                            - ScheduledActivityInstance (repetitions)
                            - Administration (dosing regimens)
                            - Timing (with valid references)
```

### Key Contract

**Extensions are OPTIONAL/DEBUG. Core USDM must be self-sufficient.**

### Promotion Steps

| Step | Input | Output |
|------|-------|--------|
| 1. Anchor Promotion | `time_anchors[]` | `ScheduledActivityInstance` with anchor metadata |
| 2. Repetition Expansion | `repetitions[]` | Multiple `ScheduledActivityInstance` per occurrence |
| 3. Dosing Normalization | `dosing_regimens[]` | `Administration` linked to `StudyIntervention` |
| 4. Reference Reconciliation | `Timing.relativeFromScheduledInstanceId` | Fix dangling references |

### Files

- `extraction/execution/execution_model_promoter.py` - Main promotion logic
- `extraction/execution/reconciliation_layer.py` - Entity resolution and issue classification
- `extraction/execution/pipeline_integration.py` - Integration into enrichment flow

### Reference Reconciliation

After UUID conversion, all `relativeFromScheduledInstanceId` references in timings are verified:
1. If reference exists → keep as-is
2. If reference is in anchor map → remap to promoted anchor
3. If reference missing → create missing anchor instance or remap to closest match

---

## Unified Entity Reconciliation Framework

The pipeline reconciles USDM entities (epochs, encounters, activities) from multiple extraction sources into consistent, canonical data for `protocol_usdm.json`.

### Problem

Entities extracted from different sources may have:
- **Footnote markers**: "Screening a", "Physical Exam (b)" (from SoA table headers)
- **Different granularity**: SoA vs detailed procedures vs execution model timing
- **Conflicting names**: Different extractors may name the same entity differently
- **Partial information**: One source has timing, another has conditional logic

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              UNIFIED RECONCILIATION FRAMEWORK                    │
│                  core/reconciliation/                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  BaseReconciler (Abstract)                                       │
│    ├── contribute(source, entities, priority)                    │
│    ├── reconcile() -> List[ReconciledEntity]                    │
│    └── fuzzy_match_names(), _post_reconcile()                   │
│                                                                  │
│  ┌─────────────────┬─────────────────┬─────────────────┐        │
│  │ EpochReconciler │ ActivityRecon.  │ EncounterRecon. │        │
│  │ - main/sub cat  │ - type inference│ - visit windows │        │
│  │ - traversal seq │ - group merging │ - study day     │        │
│  │ - CDISC codes   │ - conditionals  │ - timing labels │        │
│  └─────────────────┴─────────────────┴─────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              ↑
        ┌─────────────────────┼─────────────────────┐
        ↑                     ↑                     ↑
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ SoA Extractor │   │  Procedures   │   │  Execution    │
│ priority=10   │   │  priority=20  │   │  Model p=25   │
│               │   │               │   │               │
│ Base entities │   │ Detailed info │   │ Timing/rules  │
└───────────────┘   └───────────────┘   └───────────────┘
```

### Reconcilers

| Reconciler | Entity | Key Features |
|------------|--------|--------------|
| **EpochReconciler** | StudyEpoch | Main/sub categorization, traversal sequence, CDISC type inference |
| **ActivityReconciler** | Activity | Activity type inference, group merging, conditional logic from footnotes |
| **EncounterReconciler** | Encounter | Visit windows, study day extraction, timing labels |

### Common Features

| Feature | Description |
|---------|-------------|
| **Name cleaning** | Strips footnote markers (a, b, c...) from entity names |
| **Priority-based merging** | Higher priority sources override conflicts |
| **Fuzzy matching** | Merges similar names (but not "Period 1" vs "Period 2") |
| **Extensibility** | Any extractor can contribute via `contribute()` |
| **Source attribution** | Tracks which extractors contributed to each entity |

### Usage

```python
from core.reconciliation import (
    reconcile_epochs_from_pipeline,
    reconcile_activities_from_pipeline,
    reconcile_encounters_from_pipeline,
)

# Epochs: SoA + traversal sequence
reconciled_epochs = reconcile_epochs_from_pipeline(
    soa_epochs=soa_epochs,
    traversal_sequence=["epoch_1", "epoch_3", "epoch_5"],
)

# Activities: SoA + procedures + execution model
reconciled_activities = reconcile_activities_from_pipeline(
    soa_activities=soa_activities,
    procedure_activities=procedures,
    execution_repetitions=repetitions,
    footnote_conditions=footnotes,
)

# Encounters: SoA + visit windows
reconciled_encounters = reconcile_encounters_from_pipeline(
    soa_encounters=soa_encounters,
    visit_windows=visit_windows,
)
```

### Extension Attributes

All reconciled entities include extension attributes for metadata:

```json
{
  "extensionAttributes": [
    { "url": ".../x-entityCategory", "valueString": "main" },
    { "url": ".../x-entityRawName", "valueString": "Screening a" },
    { "url": ".../x-entitySources", "valueString": "soa,execution" }
  ]
}
```

### Priority Defaults

| Source | Priority | Entities |
|--------|----------|----------|
| SoA | 10 | Base entities from table extraction |
| Scheduling | 15 | Timing information |
| Procedures | 20 | Detailed procedure info |
| Traversal | 25 | Main epoch sequence |
| Execution Model | 25 | Visit windows, repetitions |
| Footnotes | 30 | Conditional logic |
| SAP | 30 | Analysis-specific entities |

---

## Provenance Tracking

Provenance tracks the **source** of each extracted entity and cell (text extraction, vision validation, or both), plus **footnote references** for ticks with superscripts.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Extraction Pipeline                          │
│                                                                 │
│   Header Structure (enc_1, enc_2, ...) from vision analysis    │
│           │                                                     │
│           ▼                                                     │
│   text_extractor.py ──► uses encounterId (enc_N) directly      │
│           │                        │                            │
│           ▼                        ▼                            │
│   9_final_soa.json     9_final_soa_provenance.json             │
│   (act_1, enc_1)       (act_1|enc_1 → source)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Validation & UUID Conversion                  │
│                                                                 │
│   convert_ids_to_uuids() ──► id_map {simple → uuid}            │
│           │                        │                            │
│           ▼                        ▼                            │
│   protocol_usdm.json   convert_provenance_to_uuids()           │
│   (UUIDs)              (enc_N → uuid, pt_N → uuid for legacy)  │
│                                    │                            │
│                                    ▼                            │
│                        protocol_usdm_provenance.json            │
│                        (uuid|uuid → source)                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Viewer Display                              │
│                                                                 │
│   protocol_usdm.json + protocol_usdm_provenance.json           │
│                    ↓                                            │
│   Colored tick marks + footnote superscripts                    │
│                                                                 │
│   Colors: 🟢 Both (confirmed)  🔵 Text-only  🟠 Needs review    │
│   Footnotes: X^a, X^m,n displayed as superscripts              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Provenance Files

**Two paired output files:**

| File | IDs | Purpose |
|------|-----|---------|
| `9_final_soa_provenance.json` | Simple (act_1, enc_1) | Original extraction provenance |
| `protocol_usdm_provenance.json` | UUIDs | Viewer consumption (matches protocol_usdm.json) |

**Note:** Extraction now uses `encounterId` (enc_N) directly from header structure instead of `plannedTimepointId` (pt_N). Legacy pt_N format is still supported for backward compatibility.

### Provenance File Format

```json
{
  "entities": {
    "activities": { "<uuid>": "text|vision|both" },
    "encounters": { "<uuid>": "text|vision|both" },
    "epochs": { "<uuid>": "text|vision|both" }
  },
  "cells": {
    "<activity_uuid>|<timepoint_uuid>": "text|vision|both"
  },
  "cellFootnotes": {
    "<activity_uuid>|<timepoint_uuid>": ["a", "m"]
  },
  "metadata": {
    "model": "gemini-2.5-pro",
    "extraction_type": "text"
  }
}
```

### ID Consistency

The `convert_provenance_to_uuids()` function ensures perfect ID alignment:

1. During validation, `convert_ids_to_uuids()` creates `id_map` mapping simple IDs → UUIDs
2. The same `id_map` is used to convert provenance IDs
3. **Critical:** Provenance uses `pt_N` IDs but USDM uses `enc_N` for encounters - the function maps `pt_N` → `enc_N` UUIDs
4. Both `protocol_usdm.json` and `protocol_usdm_provenance.json` use identical encounter UUIDs
5. Viewer loads `id_mapping.json` to build `pt_uuid → enc_uuid` mapping for instance ID resolution

### Footnote Extraction

Footnotes are extracted at two levels:

1. **Protocol-level footnotes**: Stored in `HeaderStructure.footnotes` as `CommentAnnotation` objects
2. **Cell-level footnote refs**: Stored in `cellFootnotes` as `["a", "m"]` arrays per tick

The text extraction prompt captures superscripts like "X^a" or "✓^m,n" and stores them in `ActivityTimepoint.footnoteRefs`.

## Validation & Enrichment Pipeline

1. **Normalization** - Type inference for Encounters, Epochs, Arms
2. **UUID Conversion** - Simple IDs converted to proper UUIDs via `convert_ids_to_uuids()`
3. **Provenance Conversion** - Creates `protocol_usdm_provenance.json` using same `id_map`
4. **Terminology Enrichment** - NCI codes via EVS API (with caching)
5. **Official Validation** - Validate against `usdm` Pydantic package
6. **CDISC CORE Conformance** - Rule-based validation

```python
from validation import validate_usdm_dict
from enrichment.terminology import enrich_terminology

# Enrich with NCI codes
enrich_result = enrich_terminology(json_path, output_dir=output_dir)

# Validate
result = validate_usdm_dict(data)
print(f"Errors: {result.error_count}")
```

### Terminology Codes (`core/terminology_codes.py`)

Single source of truth for all NCI codes. All codes verified against NIH EVS API.

```python
from core.terminology_codes import (
    get_objective_level_code,
    get_endpoint_level_code,
    OBJECTIVE_LEVEL_CODES,
    ENDPOINT_LEVEL_CODES,
)

# Get USDM-compliant Code object
code = get_objective_level_code("primary")
# Returns: {"code": "C85826", "decode": "Trial Primary Objective", ...}
```

**Key Code Categories:**
- **Objective Levels**: C85826 (Primary), C85827 (Secondary), C163559 (Exploratory)
- **Endpoint Levels**: C98772 (Primary), C98781 (Secondary), C98724 (Exploratory)
- **Blinding**: C49659 (Open Label), C28233 (Single), C15228 (Double), C66959 (Triple)
- **Arm Types**: C174266 (Investigational), C174268 (Placebo), C174267 (Active Comparator)

**Verification:** Run `python tests/verify_evs_codes.py` to re-verify against NIH EVS API.

### EVS Client (`core/evs_client.py`)

The EVS client connects to NCI EVS APIs for controlled terminology:

```python
from core.evs_client import get_client, ensure_usdm_codes_cached

# Populate cache with USDM-relevant codes
ensure_usdm_codes_cached()

# Lookup individual codes
client = get_client()
code = client.fetch_ncit_code('C15600')  # Phase I Trial
```

**Features:**
- Connects to EVS REST API (`api-evsrest.nci.nih.gov`)
- Local JSON cache with 30-day TTL (`core/evs_cache/nci_codes.json`)
- Automatic cache population on first run
- Used by `enrichment/terminology.py` to fetch code metadata

## Updating for New USDM Versions

When CDISC releases a new USDM version:

```python
from core.usdm_schema_loader import USDMSchemaLoader

# Force download new schema
loader = USDMSchemaLoader()
loader.ensure_schema_cached(force_download=True)

# Regenerate prompts
from core.schema_prompt_generator import generate_all_prompts
generate_all_prompts()
```

## File Structure

```
core/
├── usdm_schema_loader.py      # Schema parser + USDMEntity base class
├── usdm_types_generated.py    # Official USDM types (86+ entities)
├── usdm_types.py              # Main interface + internal extraction types
├── terminology_codes.py       # Single source of truth for NCI codes (EVS-verified)
├── evs_client.py              # NCI EVS API client with caching
├── provenance.py              # ProvenanceTracker for extraction source tracking
├── schema_prompt_generator.py # Prompt generator from schema
├── schema_cache/              # Cached official schema
│   └── dataStructure.yml
└── evs_cache/                 # Cached NCI terminology (auto-generated)
    └── nci_codes.json

extraction/
├── header_analyzer.py         # Vision-based structure extraction
├── text_extractor.py          # Text-based data extraction
├── validator.py               # Extraction validation
└── */schema.py                # Extraction-specific types (imports from terminology_codes)

enrichment/
└── terminology.py             # NCI EVS enrichment (uses terminology_codes)

validation/
├── __init__.py                # Main validation interface
├── usdm_validator.py          # Official package validation
└── cdisc_conformance.py       # CDISC CORE conformance

tests/
├── verify_evs_codes.py        # Verify NCI codes against NIH EVS API
└── ...                        # Other test files

archive/legacy_pipeline/
├── usdm_types_v4.py           # [ARCHIVED] Manual types
├── soa_entity_mapping.json    # [ARCHIVED] Manual entity mapping
└── generate_soa_llm_prompt.py # [ARCHIVED] Manual prompt generation
```

## Extraction Schema Files

Each extraction module has a local `schema.py` with extraction-specific types:

| Module | Purpose | Key Types |
|--------|---------|-----------|
| `eligibility/schema.py` | Criteria extraction | `EligibilityData`, `CriterionCategory` |
| `metadata/schema.py` | Study metadata | `StudyMetadata`, `TitleType`, `OrganizationType` |
| `objectives/schema.py` | Objectives/endpoints | `ObjectivesData`, `ObjectiveLevel`, `EndpointLevel` |
| `interventions/schema.py` | Drugs/devices | `InterventionsData`, `RouteOfAdministration` |
| `studydesign/schema.py` | Arms/cells | `StudyDesignData`, `ArmType`, `BlindingSchema` |
| `scheduling/schema.py` | Timing/rules | `SchedulingData`, `TimingType` |
| `narrative/schema.py` | Document content | `NarrativeData`, `SectionType` |
| `procedures/schema.py` | Procedures | `ProceduresDevicesData`, `ProcedureType` |
| `amendments/schema.py` | Amendment details | `AmendmentDetailsData`, `ImpactLevel` |
| `advanced/schema.py` | Advanced entities | `AdvancedData`, `AmendmentScope` |
| `document_structure/schema.py` | Doc structure | `DocumentStructureData`, `AnnotationType` |

**Important**: These extraction types are **intermediate representations** used during extraction. They import utilities from `core/usdm_types` and convert to official USDM types when generating output.

## Migration Notes

### From v5.x to v6.0

1. **Types now auto-populate required fields** - No need to manually set `id`, `codeSystem`, etc.
2. **Prompts generated from schema** - More accurate entity definitions
3. **Single source of truth** - All derived from `dataStructure.yml`

### From v6.x to v6.6 (USDM Placement Compliance)

All entities now placed at their correct USDM locations per `dataStructure.yml`:

1. **eligibilityCriterionItems** moved from `studyDesign` → `studyVersion`
2. **organizations** moved from `study` → `studyVersion`
3. **narrativeContentItems** renamed from `narrativeContents` and moved to `studyVersion`
4. **studyInterventions** moved from `studyDesign` → `studyVersion`
5. **administrableProducts** moved from root → `studyVersion`
6. **medicalDevices** moved from root → `studyVersion`
7. **timings** moved from root → `scheduleTimeline.timings`
8. **exits** moved from root → `scheduleTimeline.exits`
9. **conditions** moved from root → `studyVersion.conditions`
10. **procedures** moved from root → `activity.definedProcedures`
11. **indications** moved from `study` → `studyDesign.indications`
12. **analysisPopulations** moved from root → `studyDesign.analysisPopulations`

### Backward Compatibility

All existing imports continue to work:

```python
# These all work
from core.usdm_types import Activity, Encounter, Timeline
from core.usdm_types import PlannedTimepoint  # Internal type
from core.usdm_types import USING_GENERATED_TYPES  # Always True now
```

---

## Reconciliation Layer

The Reconciliation Layer bridges execution model findings with the core USDM graph, ensuring that structural findings (crossover, traversal, dosing) don't just land in extensions but actually shape the core USDM model.

### Architecture

```
PDF → Core Extractors → Initial USDM Core
                              ↓
PDF → Execution Extractors → Execution Data
                              ↓
         ← Reconciliation Layer →
                              ↓
                     Enriched USDM Core
```

### Key File

`extraction/execution/reconciliation_layer.py`

### Responsibilities

1. **Promote structural findings** - Crossover → epochs/cells/arms
2. **Bidirectional entity resolution** - Traversal ↔ epochs  
3. **Consolidate/normalize data** - Dosing, visits
4. **Validate consistency** - Before final output

### Reconciliation Steps

```python
from extraction.execution.reconciliation_layer import ReconciliationLayer

layer = ReconciliationLayer()
enriched_design = layer.reconcile(usdm_design, execution_data)

# Access classified issues
for issue in layer.issues:
    print(f"{issue.severity.value}: {issue.message}")
    print(f"  Path: {issue.affected_path}")
    print(f"  Suggestion: {issue.suggestion}")
```

### Crossover Promotion

When `isCrossover=true`, the layer:
- Creates epochs for each period (+ washout if present)
- Creates study cells per arm×epoch
- Ensures encounters align to epochs
- Validates crossover is consistent with study design

### Design Reconciliation Gate

Before promoting crossover findings, validates consistency:
- Single-arm studies shouldn't have crossover
- Period count should align with epoch count
- Titration studies conflict with crossover

---

## Entity Resolution

LLM-based semantic entity resolution replaces fragile fuzzy string matching. It maps abstract extraction concepts (like "RUN_IN", "BASELINE", "TREATMENT") to actual protocol-specific entities.

### Key File

`extraction/execution/entity_resolver.py`

### Architecture

```
Downstream Extractors → EntityResolver.resolve_epoch_concepts()
                              ↓
                     LLM Semantic Understanding
                              ↓
                     EntityMapping (cached)
                              ↓
                     First-class data for validation
```

### Usage

```python
from extraction.execution.entity_resolver import (
    EntityResolver, 
    EntityResolutionContext,
    create_resolution_context_from_design
)

# Create resolver and context
resolver = EntityResolver(llm_client)
context = create_resolution_context_from_design(usdm_design)

# Resolve abstract concepts to actual epochs
mappings = resolver.resolve_epoch_concepts(
    concepts=["RUN_IN", "BASELINE", "TREATMENT"],
    context=context
)

for concept, mapping in mappings.items():
    if mapping:
        print(f"{concept} → {mapping.resolved_name} ({mapping.confidence:.0%})")
        print(f"  Reasoning: {mapping.reasoning}")
```

### EntityMapping Fields

| Field | Description |
|-------|-------------|
| `abstract_concept` | Source concept (e.g., "RUN_IN") |
| `entity_type` | EPOCH, VISIT, ACTIVITY, ARM, TIMEPOINT |
| `resolved_id` | Actual entity ID from protocol |
| `resolved_name` | Human-readable name |
| `confidence` | 0.0 to 1.0 |
| `reasoning` | LLM explanation for mapping |

### Standard Epoch Concepts

| Concept | Typical Mapping |
|---------|-----------------|
| SCREENING | Initial assessment, eligibility |
| RUN_IN | Washout, stabilization |
| BASELINE | Day 1, pre-treatment |
| TREATMENT | Active intervention |
| MAINTENANCE | Stable dose continuation |
| FOLLOW_UP | Post-treatment monitoring |
| END_OF_STUDY | Final assessments |

---

## Classified Integrity Issues

The reconciliation layer generates classified integrity issues with actionable context.

### Severity Levels

| Severity | Description |
|----------|-------------|
| `BLOCKING` | Prevents downstream use |
| `WARNING` | Degraded but usable |
| `INFO` | Informational only |

### IntegrityIssue Fields

```python
@dataclass
class IntegrityIssue:
    severity: IssueSeverity
    category: str           # e.g., "traversal_resolution"
    message: str
    affected_path: str      # JSONPath to affected object
    affected_ids: List[str]
    suggestion: str         # Actionable fix
```

### Issue Categories

| Category | Description |
|----------|-------------|
| `crossover_design_mismatch` | Crossover detected but study is single-arm |
| `crossover_period_mismatch` | Period count doesn't match epoch count |
| `crossover_titration_conflict` | Titration schedule conflicts with crossover |
| `traversal_resolution` | Traversal step couldn't resolve to epoch |
| `dosing_fragmentation` | Dosing regimens are fragmented |
| `visit_window_overlap` | Visit windows overlap |

### Output Format

Issues are saved to `11_reconciliation_issues.json`:

```json
[
  {
    "severity": "warning",
    "category": "traversal_resolution",
    "message": "Traversal step 'RUN_IN' could not be resolved to an epoch ID",
    "affectedPath": "$.traversalConstraints[].requiredSequence",
    "affectedIds": ["tc_1"],
    "suggestion": "Create epoch for 'RUN_IN' or map to existing epoch"
  }
]
```

---

## Entity Maps

The reconciliation layer builds bidirectional entity maps for downstream use.

### Epoch Alias Map

Maps semantic labels to actual epoch IDs:

```python
{
    "SCREENING": "epoch_uuid_1",
    "BASELINE": "epoch_uuid_2", 
    "TREATMENT": "epoch_uuid_3",
    "PERIOD_1": "epoch_uuid_4",
    "PERIOD_2": "epoch_uuid_5",
    "FOLLOW_UP": "epoch_uuid_6"
}
```

### Visit Alias Map

Maps visit names to encounter IDs:

```python
{
    "VISIT_1": "enc_uuid_1",
    "SCREENING": "enc_uuid_2",
    "DAY_1": "enc_uuid_3"
}
```

### Automatic Alias Generation

The layer automatically generates aliases from:
- Direct name mapping (e.g., "Screening" → SCREENING)
- Semantic content detection (e.g., name contains "screen" → SCREENING)
- Period number extraction (e.g., "Period 1" → PERIOD_1)

---

## Footnotes & Abbreviations Architecture

The pipeline extracts footnotes and abbreviations from multiple sources with clear authority hierarchy.

### Source Hierarchy

| Source | Location | Authority | Content |
|--------|----------|-----------|---------|
| **SoA Footnotes** | `4_header_structure.json` | Authoritative | Vision-extracted footnotes (a-x) from SoA table |
| **Protocol Footnotes** | `13_document_structure.json` | Supplementary | Footnotes from other protocol sections |
| **Abbreviations** | `7_narrative_structure.json` | Authoritative | Abbreviations from front matter + SoA table |

### USDM Storage

| Data | USDM Location | Extension URL |
|------|---------------|---------------|
| **SoA Footnotes** | `studyDesign.extensionAttributes[]` | `x-soaFootnotes` |
| **Footnote Conditions** | `studyDesign.extensionAttributes[]` | `x-footnoteConditions` |
| **Protocol Footnotes** | `studyDesign.notes[]` | N/A (core USDM) |
| **Abbreviations** | `studyVersion.abbreviations[]` | N/A (core USDM) |

### Data Flow

```
Vision Extraction (4_header_structure.json)
    └── footnotes: ["a. Only at screening", "b. If clinically indicated", ...]
                ↓
    main_v2.py: Merge into soa_data before execution phases
                ↓
    Execution Model: extract_footnote_conditions(footnotes=soa_footnotes)
                ↓
    x-footnoteConditions: Structured parsing with appliesToActivityIds
                ↓
    x-soaFootnotes: Raw authoritative list for UI display
```

### Abbreviation Extraction

The narrative extractor finds abbreviations from:
- Front matter "List of Abbreviations" pages
- SoA table "Abbreviations:" line (page 16+)

**Page finder patterns:**
```python
structure_keywords = [
    r'list\s+of\s+abbreviations',
    r'abbreviations\s*:',           # SoA table format
    r'schedule\s+of\s+activities',  # Include SoA pages
]
```

### UI Display (FootnotesView.tsx)

Groups footnotes by source:
1. **Schedule of Activities** - from `x-soaFootnotes`
2. **Other Protocol Sections** - from `commentAnnotations` 
3. **Protocol Abbreviations** - from `studyVersion.abbreviations`

---

## Provenance Entity Name Mappings

Provenance files store entity ID-to-name mappings for UI display.

### Problem

Provenance tracks cells as `activityId|encounterId` (UUIDs), but the UI needs display names.

### Solution

When creating `protocol_usdm_provenance.json`, entity name mappings are populated from the USDM:

```python
converted_provenance['entities']['encounters'] = {
    enc.get('id'): enc.get('name', 'Unknown')
    for enc in sd.get('encounters', [])
}
converted_provenance['entities']['activities'] = {
    act.get('id'): act.get('name') or act.get('label', 'Unknown')
    for act in sd.get('activities', [])
}
```

### Provenance File Format (Updated)

```json
{
  "entities": {
    "activities": { "<uuid>": "Activity Name" },
    "encounters": { "<uuid>": "Day 1" },
    "epochs": { "<uuid>": "Treatment" }
  },
  "cells": {
    "<activity_uuid>|<encounter_uuid>": "text|vision|both"
  },
  "cellFootnotes": {
    "<activity_uuid>|<encounter_uuid>": ["a", "m"]
  }
}
```

### UI Resolution (ProvenanceExplorer.tsx)

```typescript
const encounterName = provenance.entities?.encounters?.[encounterId] || encounterId;
```

---

## UI ID-to-Name Resolution

Multiple UI components resolve entity IDs to display names.

### Components with Resolution

| Component | Resolves | Source |
|-----------|----------|--------|
| **ConditionsPanel** | `appliesToActivityIds` | `studyDesign.activities`, `activityGroups` |
| **ActivitySchedulePanel** | `activityIds`, `encounterId` | `studyDesign.activities`, `encounters` |
| **ProvenanceExplorer** | `visitId` | `provenance.entities.encounters` |
| **TraversalPanel** | `epochId`, `encounterId` | `studyDesign.epochs`, `encounters` |

### Resolution Pattern

```typescript
// Build entity name map
const entityNameMap = useMemo(() => {
  const map: Record<string, string> = {};
  
  // Handle both UUID and sequential ID formats (act_1, grp_2)
  activities.forEach((act, idx) => {
    map[act.id] = act.name || act.label;
    map[`act_${idx + 1}`] = act.name || act.label;
  });
  
  groups.forEach((grp, idx) => {
    map[grp.id] = grp.name;
    map[`grp_${idx + 1}`] = grp.name;
  });
  
  return map;
}, [studyDesign]);

// Resolve ID to name
const resolveEntityName = (id: string): string => {
  return entityNameMap[id] || id;
};
```

### Execution Model Anchor Deduplication

The `CollectionDay` anchor type is deduplicated to avoid UI warnings:

```python
# Only create ONE CollectionDay anchor per protocol
if collection_sources:
    anchors.append(TimeAnchor(
        id="anchor_collection_1",
        definition="24-hour collection period",
        anchor_type=AnchorType.COLLECTION_DAY,
        source_text=collection_sources[0],
    ))
```

---

## Execution Model Promoter (v7.2+)

The `ExecutionModelPromoter` addresses the gap where execution model data was extracted but stored only in extensions. It promotes execution findings into **native USDM entities** so downstream consumers can use core USDM without parsing extensions.

### Key File

`extraction/execution/execution_model_promoter.py`

### Promotion Methods

| Method | Input | Output | USDM Entity |
|--------|-------|--------|-------------|
| `_promote_time_anchors()` | TimeAnchor[] | ScheduledActivityInstance | Creates anchor instances |
| `_promote_repetitions()` | Repetition[] | ScheduledActivityInstance | Expands daily/weekly patterns |
| `_promote_dosing_regimens()` | DosingRegimen[] | Administration | Links to StudyIntervention |
| `_promote_visit_windows()` | VisitWindow[] | Timing | Sets windowLower/windowUpper |
| `_promote_traversals()` | TraversalConstraint[] | StudyEpoch, Encounter | Sets previousId/nextId chains |
| `_promote_conditions()` | FootnoteCondition[] | Condition, ScheduledDecisionInstance | Creates conditional workflows |
| `_promote_state_machine()` | SubjectStateMachine | TransitionRule | Sets transitionStartRule/EndRule |
| `_promote_estimands()` | EndpointAlgorithm[] | Estimand | Links to Endpoint |
| `_promote_elements()` | TitrationSchedule[] | StudyElement | Creates dose escalation steps |

### New USDM Entities (v7.2)

Added to `core/usdm_types_generated.py`:

- **ScheduledDecisionInstance** - Decision node in timeline with conditionAssignments
- **ConditionAssignment** - If/then rule: condition text → conditionTargetId
- **StudyElement** - Building block for titration/dose phases with transition rules

### Updated USDM Entities

- **Encounter** - Added `transitionStartRule`, `transitionEndRule`, `previousId`, `nextId`
- **StudyDesign** - Added `conditions[]`, `estimands[]`, `elements[]`
- **ScheduleTimelineExit** - Added `name`, `exitId`

### Post-Promotion Validation

The `validate_after_promotion()` function checks:
- Condition.appliesToIds referencing nonexistent activities
- Timing.relativeFromScheduledInstanceId pointing to missing instances
- ScheduledDecisionInstance with invalid conditionTargetIds
- Broken epoch/encounter previousId/nextId chains
- Estimand.variableOfInterestId referencing missing endpoints

### Extension Schema

Concepts with no native USDM equivalent are documented in `docs/EXECUTION_MODEL_EXTENSIONS.md`:
- Sampling constraints
- Execution type classifications (WINDOW/EPISODE/SINGLE/RECURRING)
- Endpoint computation formulas
- Derived variable rules
- Analysis windows
- Randomization operational details
