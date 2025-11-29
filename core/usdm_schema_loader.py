"""
USDM Schema Loader - Generates Python types from official CDISC dataStructure.yml

This module parses the official CDISC USDM schema and dynamically generates
Python dataclasses that are always in sync with the USDM specification.

Source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

import yaml
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Type, get_type_hints
from pathlib import Path

logger = logging.getLogger(__name__)

# Schema location
SCHEMA_URL = "https://raw.githubusercontent.com/cdisc-org/DDF-RA/main/Deliverables/UML/dataStructure.yml"
CACHE_DIR = Path(__file__).parent / "schema_cache"
CACHED_SCHEMA = CACHE_DIR / "dataStructure.yml"
VERSION_FILE = CACHE_DIR / "version.json"

# Type mapping from YAML refs to Python types
TYPE_MAP = {
    "#/string": "str",
    "#/integer": "int",
    "#/boolean": "bool",
    "#/number": "float",
}


@dataclass
class AttributeDefinition:
    """Definition of an entity attribute from the schema."""
    name: str
    type_ref: str  # e.g., '#/Code', '#/string'
    cardinality: str  # '1', '0..1', '0..*', '1..*'
    relationship_type: str  # 'Value' or 'Ref'
    nci_code: Optional[str] = None
    preferred_term: Optional[str] = None
    definition: Optional[str] = None
    model_name: Optional[str] = None
    inherited_from: Optional[str] = None
    
    @property
    def is_required(self) -> bool:
        """Check if attribute is required based on cardinality."""
        return self.cardinality in ('1', '1..*')
    
    @property
    def is_list(self) -> bool:
        """Check if attribute is a list based on cardinality."""
        return self.cardinality.endswith('..*')
    
    @property
    def is_reference(self) -> bool:
        """Check if this is a reference (ID) vs embedded value."""
        return self.relationship_type == 'Ref'
    
    @property
    def python_type(self) -> str:
        """Get Python type string for this attribute."""
        # Get base type
        base_type = TYPE_MAP.get(self.type_ref)
        if not base_type:
            # It's a reference to another entity
            base_type = self.type_ref.replace('#/', '')
            if self.is_reference:
                base_type = "str"  # References are stored as IDs
        
        # Handle cardinality
        if self.is_list:
            return f"List['{base_type}']"
        elif not self.is_required:
            return f"Optional['{base_type}']"
        else:
            return f"'{base_type}'"


@dataclass
class EntityDefinition:
    """Definition of a USDM entity from the schema."""
    name: str
    nci_code: Optional[str] = None
    preferred_term: Optional[str] = None
    definition: Optional[str] = None
    modifier: str = "Concrete"  # 'Concrete' or 'Abstract'
    super_classes: List[str] = field(default_factory=list)
    attributes: Dict[str, AttributeDefinition] = field(default_factory=dict)
    
    @property
    def is_abstract(self) -> bool:
        return self.modifier == "Abstract"
    
    @property
    def required_attributes(self) -> List[str]:
        """Get list of required attribute names."""
        return [name for name, attr in self.attributes.items() if attr.is_required]
    
    @property
    def optional_attributes(self) -> List[str]:
        """Get list of optional attribute names."""
        return [name for name, attr in self.attributes.items() if not attr.is_required]


class USDMSchemaLoader:
    """Loads and parses the official USDM dataStructure.yml schema."""
    
    def __init__(self, schema_path: Optional[Path] = None):
        self.schema_path = schema_path or CACHED_SCHEMA
        self._entities: Dict[str, EntityDefinition] = {}
        self._raw_schema: Dict[str, Any] = {}
        self._loaded = False
    
    def ensure_schema_cached(self, force_download: bool = False) -> Path:
        """Ensure schema is downloaded and cached."""
        if self.schema_path.exists() and not force_download:
            return self.schema_path
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            import requests
            logger.info(f"Downloading USDM schema from {SCHEMA_URL}")
            response = requests.get(SCHEMA_URL, timeout=30)
            response.raise_for_status()
            
            with open(self.schema_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            logger.info(f"Schema cached at {self.schema_path}")
            return self.schema_path
            
        except Exception as e:
            logger.warning(f"Failed to download schema: {e}")
            # Try bundled fallback
            bundled = Path(__file__).parent / "dataStructure.yml"
            if bundled.exists():
                return bundled
            raise RuntimeError(f"No schema available: {e}")
    
    def load(self) -> Dict[str, EntityDefinition]:
        """Load and parse the schema."""
        if self._loaded:
            return self._entities
        
        schema_path = self.ensure_schema_cached()
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            self._raw_schema = yaml.safe_load(f)
        
        # Parse each entity
        for entity_name, entity_data in self._raw_schema.items():
            if isinstance(entity_data, dict) and 'Attributes' in entity_data:
                self._entities[entity_name] = self._parse_entity(entity_name, entity_data)
        
        self._loaded = True
        logger.info(f"Loaded {len(self._entities)} USDM entities from schema")
        return self._entities
    
    def _parse_entity(self, name: str, data: Dict) -> EntityDefinition:
        """Parse a single entity definition."""
        # Parse super classes
        super_classes = []
        if 'Super Classes' in data:
            for sc in data['Super Classes']:
                if isinstance(sc, dict) and '$ref' in sc:
                    super_classes.append(sc['$ref'].replace('#/', ''))
        
        # Parse attributes
        attributes = {}
        if 'Attributes' in data:
            for attr_name, attr_data in data['Attributes'].items():
                attributes[attr_name] = self._parse_attribute(attr_name, attr_data)
        
        return EntityDefinition(
            name=name,
            nci_code=data.get('NCI C-Code'),
            preferred_term=data.get('Preferred Term'),
            definition=data.get('Definition'),
            modifier=data.get('Modifier', 'Concrete'),
            super_classes=super_classes,
            attributes=attributes,
        )
    
    def _parse_attribute(self, name: str, data: Dict) -> AttributeDefinition:
        """Parse a single attribute definition."""
        # Get type reference
        type_ref = "#/string"  # default
        if 'Type' in data and isinstance(data['Type'], list):
            for t in data['Type']:
                if isinstance(t, dict) and '$ref' in t:
                    type_ref = t['$ref']
                    break
        
        # Get inherited from
        inherited_from = None
        if 'Inherited From' in data and isinstance(data['Inherited From'], list):
            for t in data['Inherited From']:
                if isinstance(t, dict) and '$ref' in t:
                    inherited_from = t['$ref'].replace('#/', '')
                    break
        
        return AttributeDefinition(
            name=name,
            type_ref=type_ref,
            cardinality=data.get('Cardinality', '0..1'),
            relationship_type=data.get('Relationship Type', 'Value'),
            nci_code=data.get('NCI C-Code'),
            preferred_term=data.get('Preferred Term'),
            definition=data.get('Definition'),
            model_name=data.get('Model Name'),
            inherited_from=inherited_from,
        )
    
    def get_entity(self, name: str) -> Optional[EntityDefinition]:
        """Get entity definition by name."""
        self.load()
        return self._entities.get(name)
    
    def get_all_entities(self) -> Dict[str, EntityDefinition]:
        """Get all entity definitions."""
        self.load()
        return self._entities
    
    def get_entity_names(self) -> List[str]:
        """Get list of all entity names."""
        self.load()
        return list(self._entities.keys())
    
    def get_required_fields(self, entity_name: str) -> List[str]:
        """Get required field names for an entity."""
        entity = self.get_entity(entity_name)
        if not entity:
            return []
        return entity.required_attributes
    
    def get_entity_metadata(self, entity_name: str) -> Dict[str, Any]:
        """Get metadata (NCI code, definition) for an entity."""
        entity = self.get_entity(entity_name)
        if not entity:
            return {}
        return {
            'nci_code': entity.nci_code,
            'preferred_term': entity.preferred_term,
            'definition': entity.definition,
            'required_fields': entity.required_attributes,
            'optional_fields': entity.optional_attributes,
        }


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


# Base class for all generated USDM types
class USDMEntity:
    """Base class for all USDM entity types."""
    
    _schema_loader: Optional[USDMSchemaLoader] = None
    _entity_name: str = ""
    
    def _ensure_id(self) -> str:
        """
        Ensure entity has an ID, generating one if needed.
        
        This method is idempotent - if called multiple times, it returns
        the same ID. This ensures consistency between data and provenance.
        """
        if not getattr(self, 'id', None):
            import uuid
            self.id = str(uuid.uuid4())
        return self.id
    
    @classmethod
    def _get_schema(cls) -> USDMSchemaLoader:
        if cls._schema_loader is None:
            cls._schema_loader = USDMSchemaLoader()
        return cls._schema_loader
    
    @classmethod
    def get_definition(cls) -> Optional[EntityDefinition]:
        """Get schema definition for this entity type."""
        return cls._get_schema().get_entity(cls._entity_name or cls.__name__)
    
    @classmethod
    def get_required_fields(cls) -> List[str]:
        """Get list of required field names."""
        defn = cls.get_definition()
        return defn.required_attributes if defn else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        
        for key, value in self.__dict__.items():
            if value is None:
                continue
            if key.startswith('_'):
                continue
                
            if isinstance(value, list):
                if not value:
                    continue
                result[key] = [
                    v.to_dict() if hasattr(v, 'to_dict') else v 
                    for v in value
                ]
            elif hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            else:
                result[key] = value
        
        # Ensure id is present
        if 'id' not in result:
            result['id'] = generate_uuid()
        
        # Ensure instanceType is present
        if 'instanceType' not in result:
            result['instanceType'] = self.__class__.__name__
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'USDMEntity':
        """Create instance from dictionary."""
        if not data:
            return None
        
        # Get valid field names
        valid_fields = set(cls.__dataclass_fields__.keys()) if hasattr(cls, '__dataclass_fields__') else set()
        
        # Filter to valid fields
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered)
    
    def validate(self) -> List[str]:
        """Validate this entity against schema. Returns list of errors."""
        errors = []
        defn = self.get_definition()
        
        if not defn:
            return errors
        
        for attr_name, attr_def in defn.attributes.items():
            value = getattr(self, attr_name, None)
            
            if attr_def.is_required and value is None:
                errors.append(f"Missing required field: {attr_name}")
            
            if attr_def.is_list and value is not None and not isinstance(value, list):
                errors.append(f"Field {attr_name} should be a list")
        
        return errors


# Global loader instance
_global_loader: Optional[USDMSchemaLoader] = None

def get_schema_loader() -> USDMSchemaLoader:
    """Get the global schema loader instance."""
    global _global_loader
    if _global_loader is None:
        _global_loader = USDMSchemaLoader()
    return _global_loader


def get_entity_definition(name: str) -> Optional[EntityDefinition]:
    """Get entity definition by name."""
    return get_schema_loader().get_entity(name)


def get_all_entity_names() -> List[str]:
    """Get all entity names from schema."""
    return get_schema_loader().get_entity_names()


def get_required_fields(entity_name: str) -> List[str]:
    """Get required fields for an entity."""
    return get_schema_loader().get_required_fields(entity_name)


def get_entity_metadata(entity_name: str) -> Dict[str, Any]:
    """Get metadata for an entity (NCI code, definition, etc.)."""
    return get_schema_loader().get_entity_metadata(entity_name)


if __name__ == "__main__":
    # Test the loader
    logging.basicConfig(level=logging.INFO)
    
    loader = USDMSchemaLoader()
    entities = loader.load()
    
    print(f"\nLoaded {len(entities)} entities")
    print("\nSample entities:")
    
    for name in ['Code', 'Activity', 'Encounter', 'StudyEpoch', 'StudyArm', 'Study']:
        entity = entities.get(name)
        if entity:
            print(f"\n{name}:")
            print(f"  NCI Code: {entity.nci_code}")
            print(f"  Required: {entity.required_attributes}")
            print(f"  Optional: {entity.optional_attributes[:5]}...")
