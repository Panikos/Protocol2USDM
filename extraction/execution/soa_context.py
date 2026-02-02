"""
SoA Context Helper

Extracts and provides access to existing SoA entities for all execution model extractors.
This ensures extractors can reference actual IDs/names from SoA instead of creating
arbitrary labels that need downstream resolution.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SoAContext:
    """
    Container for all SoA entities that extractors can reference.
    
    Provides a single source of truth for:
    - Epochs (study phases)
    - Encounters (visits)
    - Activities (procedures/assessments)
    - Timepoints
    - Arms
    - Study cells
    - Footnotes (authoritative SoA footnotes from vision extraction)
    """
    epochs: List[Dict[str, Any]] = field(default_factory=list)
    encounters: List[Dict[str, Any]] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    timepoints: List[Dict[str, Any]] = field(default_factory=list)
    arms: List[Dict[str, Any]] = field(default_factory=list)
    study_cells: List[Dict[str, Any]] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)  # Authoritative SoA footnotes
    
    # Lookup maps for quick resolution
    _epoch_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _epoch_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _encounter_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _activity_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Build lookup maps after initialization."""
        self._build_lookup_maps()
    
    def _build_lookup_maps(self):
        """Build lookup maps for quick entity resolution."""
        for epoch in self.epochs:
            epoch_id = epoch.get('id', '')
            epoch_name = epoch.get('name', '')
            if epoch_id:
                self._epoch_by_id[epoch_id] = epoch
            if epoch_name:
                self._epoch_by_name[epoch_name.lower()] = epoch
        
        for enc in self.encounters:
            enc_id = enc.get('id', '')
            if enc_id:
                self._encounter_by_id[enc_id] = enc
        
        for act in self.activities:
            act_id = act.get('id', '')
            if act_id:
                self._activity_by_id[act_id] = act
    
    def get_epoch_ids(self) -> List[str]:
        """Get all epoch IDs."""
        return [e.get('id', '') for e in self.epochs if e.get('id')]
    
    def get_epoch_names(self) -> List[str]:
        """Get all epoch names."""
        return [e.get('name', '') for e in self.epochs if e.get('name')]
    
    def get_encounter_ids(self) -> List[str]:
        """Get all encounter/visit IDs."""
        return [e.get('id', '') for e in self.encounters if e.get('id')]
    
    def get_activity_ids(self) -> List[str]:
        """Get all activity IDs."""
        return [a.get('id', '') for a in self.activities if a.get('id')]
    
    def get_activity_names(self) -> List[str]:
        """Get all activity names."""
        return [a.get('name', '') for a in self.activities if a.get('name')]
    
    def find_epoch_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find epoch by name (case-insensitive)."""
        return self._epoch_by_name.get(name.lower())
    
    def find_epoch_by_id(self, epoch_id: str) -> Optional[Dict[str, Any]]:
        """Find epoch by ID."""
        return self._epoch_by_id.get(epoch_id)
    
    def has_epochs(self) -> bool:
        """Check if epochs are available."""
        return len(self.epochs) > 0
    
    def has_encounters(self) -> bool:
        """Check if encounters are available."""
        return len(self.encounters) > 0
    
    def has_activities(self) -> bool:
        """Check if activities are available."""
        return len(self.activities) > 0
    
    def has_footnotes(self) -> bool:
        """Check if footnotes are available."""
        return len(self.footnotes) > 0
    
    def get_summary(self) -> str:
        """Get a summary of available context."""
        parts = [
            f"{len(self.epochs)} epochs",
            f"{len(self.encounters)} encounters",
            f"{len(self.activities)} activities",
            f"{len(self.timepoints)} timepoints",
        ]
        if self.footnotes:
            parts.append(f"{len(self.footnotes)} footnotes")
        return f"SoA Context: " + ", ".join(parts)


def extract_soa_context(soa_data: Optional[Dict[str, Any]]) -> SoAContext:
    """
    Extract SoA context from USDM output.
    
    Handles various USDM structure formats:
    - Direct keys (epochs, encounters, etc.)
    - Nested under study.versions[].studyDesigns[]
    
    Args:
        soa_data: Raw SoA extraction output (USDM format)
        
    Returns:
        SoAContext with all available entities
    """
    if not soa_data:
        return SoAContext()
    
    # Try direct keys first
    epochs = soa_data.get('epochs', [])
    encounters = soa_data.get('encounters', [])
    activities = soa_data.get('activities', [])
    timepoints = soa_data.get('timepoints', [])
    arms = soa_data.get('arms', [])
    study_cells = soa_data.get('studyCells', [])
    footnotes = soa_data.get('footnotes', [])  # Authoritative SoA footnotes from vision
    
    # Try nested USDM structure: study.versions[].studyDesigns[]
    if not epochs or not encounters:
        study = soa_data.get('study', {})
        versions = study.get('versions', [])
        if versions:
            design = None
            # Get first study design
            for version in versions:
                designs = version.get('studyDesigns', [])
                if designs:
                    design = designs[0]
                    break
            
            if design:
                epochs = epochs or design.get('epochs', [])
                encounters = encounters or design.get('encounters', [])
                activities = activities or design.get('activities', [])
                arms = arms or design.get('arms', [])
                study_cells = study_cells or design.get('studyCells', [])
                
                # Timepoints might be in scheduledActivityInstances
                if not timepoints:
                    for enc in encounters:
                        scheduled = enc.get('scheduledActivities', [])
                        timepoints.extend(scheduled)
    
    context = SoAContext(
        epochs=epochs,
        encounters=encounters,
        activities=activities,
        timepoints=timepoints,
        arms=arms,
        study_cells=study_cells,
        footnotes=footnotes,
    )
    
    if context.epochs or context.encounters or context.activities:
        logger.info(f"Extracted {context.get_summary()}")
    else:
        logger.debug("No SoA context available")
    
    return context
