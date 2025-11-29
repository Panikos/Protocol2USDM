# USDM Schema Migration Plan

## Objective
Replace the manually maintained `core/usdm_types_v4.py` with auto-generated types from the official CDISC `dataStructure.yml` schema. This ensures:
- **Schema accuracy**: Always aligned with official USDM spec
- **Future-proofing**: Easy updates when new USDM versions release
- **Rich metadata**: NCI codes, definitions available for prompts and validation
- **Backward compatibility**: Existing code continues to work

## Source of Truth
- **URL**: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
- **Raw**: https://raw.githubusercontent.com/cdisc-org/DDF-RA/main/Deliverables/UML/dataStructure.yml
- **Version**: USDM 4.0.0

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   dataStructure.yml                          │
│                 (Official CDISC Schema)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              core/usdm_schema_loader.py                      │
│  - Download/cache schema                                     │
│  - Parse YAML → EntityDefinition objects                     │
│  - Generate Python dataclasses dynamically                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              core/usdm_types.py (Updated)                    │
│  - Import generated types                                    │
│  - Add backward compatibility aliases                        │
│  - Add custom helper methods (to_study_design(), etc.)       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Pipeline Code                              │
│  - extraction/*, main_v2.py, etc.                           │
│  - No changes needed (imports work the same)                 │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### Phase 1: Schema Loader (`core/usdm_schema_loader.py`)

```python
@dataclass
class AttributeDefinition:
    name: str
    type: str  # Reference like '#/Code' or '#/string'
    cardinality: str  # '1', '0..1', '0..*', '1..*'
    relationship_type: str  # 'Value' or 'Ref'
    nci_code: Optional[str]
    definition: Optional[str]
    is_required: bool  # Derived from cardinality

@dataclass  
class EntityDefinition:
    name: str
    nci_code: Optional[str]
    preferred_term: Optional[str]
    definition: Optional[str]
    modifier: str  # 'Concrete' or 'Abstract'
    super_classes: List[str]
    attributes: Dict[str, AttributeDefinition]

class USDMSchemaLoader:
    def load_schema(url_or_path: str) -> Dict[str, EntityDefinition]
    def generate_dataclass(entity: EntityDefinition) -> type
    def get_required_fields(entity_name: str) -> List[str]
    def get_entity_metadata(entity_name: str) -> Dict
```

### Phase 2: Dynamic Type Generation

For each entity in dataStructure.yml, generate:
```python
@dataclass
class Activity(USDMEntity):
    """
    NCI Code: C71473
    Definition: An action, undertaking, or event...
    """
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    notes: List['CommentAnnotation'] = field(default_factory=list)
    definedProcedures: List['Procedure'] = field(default_factory=list)
    biomedicalConceptIds: List[str] = field(default_factory=list)
    nextId: Optional[str] = None
    timelineId: Optional[str] = None
    instanceType: str = "Activity"
```

### Phase 3: Backward Compatibility

```python
# core/usdm_types.py
from .usdm_schema_loader import get_all_types

# Import all generated types
globals().update(get_all_types())

# Backward compatibility aliases
Epoch = StudyEpoch
ActivityTimepoint = ScheduledActivityInstance

# Keep custom helpers
class Timeline:
    """Legacy type - converts to StudyDesign"""
    def to_study_design(self) -> StudyDesign: ...
```

### Phase 4: Schema Version Management

```python
# core/usdm_schema_cache.py
SCHEMA_URL = "https://raw.githubusercontent.com/cdisc-org/DDF-RA/main/Deliverables/UML/dataStructure.yml"
CACHE_PATH = Path(__file__).parent / "schema_cache" / "dataStructure.yml"
VERSION_FILE = Path(__file__).parent / "schema_cache" / "version.json"

def ensure_schema_cached(version: str = "4.0.0") -> Path:
    """Download and cache schema if not present or outdated."""
    
def get_schema_version() -> str:
    """Return cached schema version."""
    
def update_schema(version: str) -> None:
    """Force update to specific version."""
```

## Benefits

1. **Single Source of Truth**: Schema comes from official CDISC repo
2. **Automatic Updates**: Run `update_schema("4.1.0")` when new version releases
3. **Rich Metadata**: NCI codes and definitions available for:
   - LLM prompts (better context)
   - Validation messages (human-readable errors)
   - Documentation generation
4. **Validation**: Cardinality constraints enforced automatically
5. **Type Safety**: IDE autocomplete works with generated types

## Migration Checklist

- [ ] Create `core/usdm_schema_loader.py`
- [ ] Create `core/usdm_schema_cache.py`  
- [ ] Generate types from `dataStructure.yml`
- [ ] Update `core/usdm_types.py` to use generated types
- [ ] Add backward compatibility aliases
- [ ] Update `validation/usdm_examples.py` to use schema metadata
- [ ] Update extraction prompts with NCI codes/definitions
- [ ] Test with existing protocols
- [ ] Archive `core/usdm_types_v4.py`

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing code | Keep all current imports working via aliases |
| Schema URL changes | Cache locally, fallback to cached version |
| Missing custom helpers | Keep Timeline, HeaderStructure as custom classes |
| Performance (runtime generation) | Generate once at import, cache compiled types |

## Timeline

- **Phase 1** (Schema Loader): 1-2 hours
- **Phase 2** (Type Generation): 2-3 hours  
- **Phase 3** (Backward Compat): 1 hour
- **Phase 4** (Testing): 1-2 hours

**Total**: ~6-8 hours of development
