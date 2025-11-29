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
│                      main_v2.py                                  │
│                            ↓                                     │
│               enrichment/terminology.py (NCI EVS)                │
│                  ↓ (uses core/evs_client.py)                     │
│                validation/cdisc_conformance.py                   │
│                            ↓                                     │
│                   protocol_usdm.json (compliant)                 │
└─────────────────────────────────────────────────────────────────┘
```

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

## Provenance Tracking

Provenance tracks the **source** of each extracted entity and cell (text extraction, vision validation, or both).

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Extraction Pipeline                          │
│                                                                 │
│   text_extractor.py ──► entities + provenance (same IDs)       │
│           │                        │                            │
│           ▼                        ▼                            │
│   9_final_soa.json     9_final_soa_provenance.json             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Validation & Combine                          │
│                                                                 │
│   normalize_usdm_data() ──► ID conversion ──► protocol_usdm.json│
│                                    │                            │
│                    sync_provenance_with_data()                  │
│                                    │                            │
│                         9_final_soa_provenance.json (updated)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Viewer Display                              │
│                                                                 │
│   protocol_usdm.json + provenance ──► colored tick marks       │
│                                                                 │
│   Colors: 🟢 Both (confirmed)  🟡 Text-only  🔴 Needs review    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

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
  "metadata": {
    "model": "gemini-2.5-pro",
    "extraction_type": "text"
  }
}
```

### ID Consistency

The **idempotent ID generation** in `_ensure_id()` ensures:
1. When `to_dict()` is called for provenance tagging, UUIDs are generated and stored
2. When `to_dict()` is called again for JSON output, **same UUIDs** are returned
3. Provenance and data always have matching IDs

For legacy runs with mismatched IDs, `sync_provenance_with_data()` matches entities by **name** as fallback.

## Validation & Enrichment Pipeline

1. **Normalization** - Type inference for Encounters, Epochs, Arms
2. **UUID Conversion** - Simple IDs converted to proper UUIDs
3. **Provenance Sync** - Provenance IDs updated to match final data
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
- Connects to EVS CT API (`evs.nci.nih.gov/ctapi/v1`)
- Local JSON cache with 30-day TTL
- Pre-defined 33 USDM-relevant NCI codes
- Automatic cache population on first run

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
└── */schema.py                # Extraction-specific types (see below)

enrichment/
└── terminology.py             # NCI EVS terminology enrichment

validation/
├── __init__.py                # Main validation interface
├── usdm_validator.py          # Official package validation
└── cdisc_conformance.py       # CDISC CORE conformance

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

### Backward Compatibility

All existing imports continue to work:

```python
# These all work
from core.usdm_types import Activity, Encounter, Timeline
from core.usdm_types import PlannedTimepoint  # Internal type
from core.usdm_types import USING_GENERATED_TYPES  # Always True now
```
