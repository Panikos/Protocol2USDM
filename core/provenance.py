"""
Provenance Tracking - Consolidated provenance management for SoA extraction.

This module provides a unified approach to tracking the source of extracted data,
replacing scattered provenance logic across:
- soa_postprocess_consolidated.py
- reconcile_soa_llm.py
- fix_provenance_keys.py

Design Principle:
- Provenance is stored in a SEPARATE file (not embedded in USDM JSON)
- This keeps the main USDM output pure and schema-compliant
- Downstream systems can ignore provenance if not needed

Usage:
    from core.provenance import ProvenanceTracker, ProvenanceSource
    
    tracker = ProvenanceTracker()
    tracker.tag_entity('activities', 'act_1', ProvenanceSource.TEXT)
    tracker.tag_cell('act_1', 'pt_1', ProvenanceSource.VISION)
    tracker.save('output/soa_provenance.json')
"""

import json
from enum import Enum
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass, field
from pathlib import Path


class ProvenanceSource(Enum):
    """Source of extracted data."""
    TEXT = "text"           # From text extraction
    VISION = "vision"       # From vision extraction  
    BOTH = "both"          # Confirmed by both sources
    NEEDS_REVIEW = "needs_review"  # Ambiguous - possible hallucination or vision-only (needs human review)
    LLM_INFERRED = "llm_inferred"  # Inferred by LLM (e.g., activity groups)
    HEADER = "header"       # From header structure analysis
    DEFAULT = "default"     # Default value added by post-processing


@dataclass
class ProvenanceTracker:
    """
    Track provenance of extracted SoA entities and cells.
    
    Maintains separate tracking for:
    - Entity-level provenance (activities, timepoints, encounters, etc.)
    - Cell-level provenance (activity-timepoint matrix)
    
    Attributes:
        entities: Dict mapping entity_type -> entity_id -> source
        cells: Dict mapping "activityId|timepointId" -> source
        metadata: Additional metadata about the extraction
    """
    entities: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'activities': {},
        'plannedTimepoints': {},
        'encounters': {},
        'epochs': {},
        'activityGroups': {},
    })
    cells: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def tag_entity(
        self, 
        entity_type: str, 
        entity_id: str, 
        source: ProvenanceSource
    ) -> None:
        """
        Tag an entity with its provenance source.
        
        Args:
            entity_type: Type of entity ('activities', 'plannedTimepoints', etc.)
            entity_id: Unique ID of the entity
            source: Source that provided this entity
        """
        if entity_type not in self.entities:
            self.entities[entity_type] = {}
        
        existing = self.entities[entity_type].get(entity_id)
        
        # If entity already tagged from different source, mark as 'both'
        if existing and existing != source.value:
            self.entities[entity_type][entity_id] = ProvenanceSource.BOTH.value
        else:
            self.entities[entity_type][entity_id] = source.value
    
    def tag_entities(
        self,
        entity_type: str,
        entities: list,
        source: ProvenanceSource
    ) -> None:
        """
        Tag multiple entities at once.
        
        Args:
            entity_type: Type of entities
            entities: List of entity dicts (must have 'id' field)
            source: Source for all entities
        """
        for entity in entities:
            if isinstance(entity, dict) and entity.get('id'):
                self.tag_entity(entity_type, entity['id'], source)
    
    def tag_cell(
        self,
        activity_id: str,
        timepoint_id: str,
        source: ProvenanceSource
    ) -> None:
        """
        Tag an activity-timepoint cell with its provenance.
        
        Args:
            activity_id: Activity ID
            timepoint_id: PlannedTimepoint ID
            source: Source that provided this tick
        """
        key = f"{activity_id}|{timepoint_id}"
        existing = self.cells.get(key)
        
        if existing and existing != source.value:
            self.cells[key] = ProvenanceSource.BOTH.value
        else:
            self.cells[key] = source.value
    
    def tag_cells_from_timepoints(
        self,
        activity_timepoints: list,
        source: ProvenanceSource
    ) -> None:
        """
        Tag cells from an activityTimepoints/scheduledActivityInstances list.
        
        Args:
            activity_timepoints: List of {activityId, plannedTimepointId/encounterId} dicts
            source: Source for all cells
        """
        for at in activity_timepoints:
            if isinstance(at, dict):
                act_id = at.get('activityId')
                # Handle both legacy (plannedTimepointId) and USDM v4.0 (encounterId) formats
                tp_id = at.get('plannedTimepointId') or at.get('timepointId') or at.get('encounterId')
                if act_id and tp_id:
                    self.tag_cell(act_id, tp_id, source)
    
    def get_entity_source(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> Optional[str]:
        """Get the provenance source for an entity."""
        return self.entities.get(entity_type, {}).get(entity_id)
    
    def get_cell_source(
        self,
        activity_id: str,
        timepoint_id: str
    ) -> Optional[str]:
        """Get the provenance source for a cell."""
        key = f"{activity_id}|{timepoint_id}"
        return self.cells.get(key)
    
    def get_entities_by_source(
        self,
        entity_type: str,
        source: ProvenanceSource
    ) -> Set[str]:
        """Get all entity IDs from a specific source."""
        return {
            eid for eid, src in self.entities.get(entity_type, {}).items()
            if src == source.value
        }
    
    def merge(self, other: 'ProvenanceTracker') -> None:
        """
        Merge another tracker's data into this one.
        
        Used when combining provenance from multiple extraction steps.
        Entities/cells present in both are marked as 'both'.
        """
        # Merge entities
        for entity_type, entities in other.entities.items():
            for entity_id, source in entities.items():
                existing = self.entities.get(entity_type, {}).get(entity_id)
                if existing and existing != source:
                    self.tag_entity(
                        entity_type, 
                        entity_id, 
                        ProvenanceSource.BOTH
                    )
                else:
                    self.tag_entity(
                        entity_type,
                        entity_id,
                        ProvenanceSource(source)
                    )
        
        # Merge cells
        for key, source in other.cells.items():
            existing = self.cells.get(key)
            if existing and existing != source:
                self.cells[key] = ProvenanceSource.BOTH.value
            else:
                self.cells[key] = source
        
        # Merge metadata (other takes precedence)
        self.metadata.update(other.metadata)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'entities': self.entities,
            'cells': self.cells,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProvenanceTracker':
        """Create tracker from dictionary (e.g., loaded from JSON)."""
        tracker = cls()
        tracker.entities = data.get('entities', tracker.entities)
        tracker.cells = data.get('cells', {})
        tracker.metadata = data.get('metadata', {})
        return tracker
    
    def save(self, path: str) -> None:
        """
        Save provenance to a JSON file.
        
        Args:
            path: Output file path
        """
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: str) -> 'ProvenanceTracker':
        """
        Load provenance from a JSON file.
        
        Args:
            path: Input file path
            
        Returns:
            Loaded ProvenanceTracker
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked provenance."""
        stats = {
            'entities': {},
            'cells': {
                'total': len(self.cells),
                'by_source': {}
            }
        }
        
        # Entity stats
        for entity_type, entities in self.entities.items():
            by_source = {}
            for source in entities.values():
                by_source[source] = by_source.get(source, 0) + 1
            stats['entities'][entity_type] = {
                'total': len(entities),
                'by_source': by_source
            }
        
        # Cell stats
        for source in self.cells.values():
            stats['cells']['by_source'][source] = \
                stats['cells']['by_source'].get(source, 0) + 1
        
        return stats


def get_provenance_path(soa_path: str) -> str:
    """
    Get the provenance file path for a given SoA file.
    
    Convention: <soa_file>_provenance.json
    
    Example:
        >>> get_provenance_path('output/9_reconciled_soa.json')
        'output/9_reconciled_soa_provenance.json'
    """
    path = Path(soa_path)
    return str(path.parent / f"{path.stem}_provenance.json")


def load_provenance_if_exists(soa_path: str) -> Optional[ProvenanceTracker]:
    """
    Load provenance for a SoA file if it exists.
    
    Args:
        soa_path: Path to SoA JSON file
        
    Returns:
        ProvenanceTracker or None if no provenance file
    """
    prov_path = get_provenance_path(soa_path)
    if Path(prov_path).exists():
        return ProvenanceTracker.load(prov_path)
    return None
