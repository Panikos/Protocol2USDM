"""
Objectives Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code
from core.terminology_codes import (
    get_objective_level_code,
    get_endpoint_level_code,
)


class ObjectiveLevel(Enum):
    """USDM Objective level codes."""
    UNKNOWN = ""  # Not extracted from source
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    EXPLORATORY = "Exploratory"
    
    def to_code(self) -> Dict[str, Any]:
        """Return proper NCI Code object for this level."""
        # Use single source of truth from core.terminology_codes
        return get_objective_level_code(self.value)


class EndpointLevel(Enum):
    """USDM Endpoint level codes."""
    UNKNOWN = ""  # Not extracted from source
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    EXPLORATORY = "Exploratory"
    
    def to_code(self) -> Dict[str, Any]:
        """Return proper NCI Code object for this level."""
        # Use single source of truth from core.terminology_codes
        return get_endpoint_level_code(self.value)


class IntercurrentEventStrategy(Enum):
    """ICH E9(R1) strategies for handling intercurrent events."""
    TREATMENT_POLICY = "Treatment Policy"
    COMPOSITE = "Composite"
    HYPOTHETICAL = "Hypothetical"
    PRINCIPAL_STRATUM = "Principal Stratum"
    WHILE_ON_TREATMENT = "While on Treatment"


@dataclass
class Endpoint:
    """
    USDM Endpoint entity.
    
    Represents a measurable outcome variable for an objective.
    """
    id: str
    name: str
    text: str  # Full description of the endpoint
    level: EndpointLevel
    purpose: Optional[str] = None  # e.g., "Efficacy", "Safety", "Pharmacodynamic"
    objective_id: Optional[str] = None  # Link to parent objective
    label: Optional[str] = None
    description: Optional[str] = None
    instance_type: str = "Endpoint"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "level": self.level.to_code(),  # Use correct NCI codes
            "instanceType": self.instance_type,
        }
        if self.purpose:
            result["purpose"] = self.purpose
        if self.objective_id:
            result["objectiveId"] = self.objective_id
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class IntercurrentEvent:
    """
    USDM IntercurrentEvent entity (ICH E9(R1)).
    
    Events occurring after treatment initiation that affect 
    interpretation of clinical outcomes.
    
    USDM 4.0 Required: id, name, text, strategy, instanceType
    """
    id: str
    name: str
    text: str  # Required in USDM 4.0 - structured text representation
    strategy: IntercurrentEventStrategy  # Required - stored as string in USDM
    description: Optional[str] = None
    label: Optional[str] = None
    estimand_id: Optional[str] = None  # Link to parent estimand
    instance_type: str = "IntercurrentEvent"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "text": self.text,  # Required in USDM 4.0
            "strategy": self.strategy.value,  # USDM 4.0: string, not Code object
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        return result


@dataclass
class Estimand:
    """
    USDM Estimand entity (ICH E9(R1)).
    
    Precise description of the treatment effect to be estimated.
    
    USDM 4.0 Required Fields:
    - id, name, populationSummary, analysisPopulationId, variableOfInterestId,
      intercurrentEvents (1..*), interventionIds (1..*), instanceType
    
    ICH E9(R1) Five Attributes (mapped to USDM):
    1. Treatment → interventionIds (references to StudyIntervention)
    2. Population → analysisPopulationId (reference to AnalysisPopulation)
    3. Variable (Endpoint) → variableOfInterestId (reference to Endpoint)
    4. Intercurrent Events → intercurrentEvents (embedded IntercurrentEvent objects)
    5. Population-Level Summary → populationSummary (string describing the summary measure)
    """
    id: str
    name: str
    # USDM 4.0 Required fields
    population_summary: str = "Study population as defined by eligibility criteria"  # Population-level summary
    analysis_population_id: Optional[str] = None  # Reference to AnalysisPopulation
    variable_of_interest_id: Optional[str] = None  # Reference to Endpoint
    intervention_ids: List[str] = field(default_factory=list)  # References to StudyIntervention
    intercurrent_events: List[IntercurrentEvent] = field(default_factory=list)  # At least 1 required
    # USDM 4.0 Optional fields
    label: Optional[str] = None
    description: Optional[str] = None
    # Extension fields for ICH E9(R1) context (stored but may not be in strict USDM output)
    summary_measure: Optional[str] = None  # e.g., "Hazard ratio", "Difference in means"
    treatment: Optional[str] = None  # Textual treatment description for context
    analysis_population: Optional[str] = None  # Textual population description for context
    variable_of_interest: Optional[str] = None  # Textual variable description for context
    endpoint_id: Optional[str] = None  # Alias for variable_of_interest_id
    instance_type: str = "Estimand"
    
    def __post_init__(self):
        # Sync endpoint_id with variable_of_interest_id
        if self.endpoint_id and not self.variable_of_interest_id:
            self.variable_of_interest_id = self.endpoint_id
        elif self.variable_of_interest_id and not self.endpoint_id:
            self.endpoint_id = self.variable_of_interest_id
    
    def to_dict(self) -> Dict[str, Any]:
        # Build population summary incorporating the summary measure if available
        pop_summary = self.population_summary
        if self.summary_measure and self.summary_measure not in pop_summary:
            pop_summary = f"{pop_summary} Summary measure: {self.summary_measure}."
        
        result = {
            "id": self.id,
            "name": self.name,
            "populationSummary": pop_summary,
            "analysisPopulationId": self.analysis_population_id or f"{self.id}_pop",  # Required
            "variableOfInterestId": self.variable_of_interest_id or self.endpoint_id or f"{self.id}_var",  # Required
            "interventionIds": self.intervention_ids if self.intervention_ids else [f"{self.id}_int"],  # At least 1 required
            "intercurrentEvents": [ie.to_dict() for ie in self.intercurrent_events] if self.intercurrent_events else [
                # Provide default intercurrent event if none specified
                {"id": f"{self.id}_ice_1", "name": "Treatment discontinuation", 
                 "text": "Subject discontinues study treatment", "strategy": "Treatment Policy", 
                 "instanceType": "IntercurrentEvent"}
            ],
            "instanceType": self.instance_type,
        }
        # Optional fields
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        # Extension attributes for richer context (viewer can use these)
        if self.treatment:
            result["treatment"] = self.treatment
        if self.analysis_population:
            result["analysisPopulation"] = self.analysis_population
        if self.variable_of_interest:
            result["variableOfInterest"] = self.variable_of_interest
        if self.summary_measure:
            result["summaryMeasure"] = self.summary_measure
        return result


@dataclass
class Objective:
    """
    USDM Objective entity.
    
    Represents a study objective with its associated endpoints.
    """
    id: str
    name: str
    text: str  # Full objective statement
    level: ObjectiveLevel
    endpoint_ids: List[str] = field(default_factory=list)
    label: Optional[str] = None
    description: Optional[str] = None
    instance_type: str = "Objective"
    
    def to_dict(self) -> Dict[str, Any]:
        # USDM requires name to be non-empty; fall back to text or level
        effective_name = self.name
        if not effective_name or not effective_name.strip():
            # Use first 100 chars of text, or level-based name
            if self.text:
                effective_name = self.text[:100] + ("..." if len(self.text) > 100 else "")
            else:
                effective_name = f"{self.level.value} Objective"
        
        result = {
            "id": self.id,
            "name": effective_name,
            "text": self.text,
            "level": self.level.to_code(),  # Use correct NCI codes
            "endpointIds": self.endpoint_ids,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class ObjectivesData:
    """
    Aggregated objectives and endpoints extraction result.
    
    Contains all Phase 3 entities for a protocol.
    """
    objectives: List[Objective] = field(default_factory=list)
    endpoints: List[Endpoint] = field(default_factory=list)
    estimands: List[Estimand] = field(default_factory=list)
    
    # Summary counts
    primary_objectives_count: int = 0
    secondary_objectives_count: int = 0
    exploratory_objectives_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        return {
            "objectives": [o.to_dict() for o in self.objectives],
            "endpoints": [e.to_dict() for e in self.endpoints],
            "estimands": [est.to_dict() for est in self.estimands],
            "summary": {
                "primaryObjectives": self.primary_objectives_count,
                "secondaryObjectives": self.secondary_objectives_count,
                "exploratoryObjectives": self.exploratory_objectives_count,
                "totalEndpoints": len(self.endpoints),
                "totalEstimands": len(self.estimands),
            }
        }
    
    @property
    def primary_objectives(self) -> List[Objective]:
        """Get only primary objectives."""
        return [o for o in self.objectives if o.level == ObjectiveLevel.PRIMARY]
    
    @property
    def secondary_objectives(self) -> List[Objective]:
        """Get only secondary objectives."""
        return [o for o in self.objectives if o.level == ObjectiveLevel.SECONDARY]
    
    @property
    def exploratory_objectives(self) -> List[Objective]:
        """Get only exploratory objectives."""
        return [o for o in self.objectives if o.level == ObjectiveLevel.EXPLORATORY]
