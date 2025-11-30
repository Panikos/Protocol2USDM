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
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    EXPLORATORY = "Exploratory"
    
    def to_code(self) -> Dict[str, Any]:
        """Return proper NCI Code object for this level."""
        # Use single source of truth from core.terminology_codes
        return get_objective_level_code(self.value)


class EndpointLevel(Enum):
    """USDM Endpoint level codes."""
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
    """
    id: str
    name: str
    description: str
    strategy: IntercurrentEventStrategy
    estimand_id: Optional[str] = None  # Link to parent estimand
    instance_type: str = "IntercurrentEvent"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy": {
                "code": self.strategy.value,
                "codeSystem": "ICH E9(R1)",
                "decode": self.strategy.value,
            },
            "instanceType": self.instance_type,
        }


@dataclass
class Estimand:
    """
    USDM Estimand entity (ICH E9(R1)).
    
    Precise description of the treatment effect to be estimated.
    Components: Population, Treatment, Variable, Intercurrent Events, Summary Measure.
    """
    id: str
    name: str
    summary_measure: str  # e.g., "Difference in means", "Hazard ratio"
    analysis_population: Optional[str] = None
    treatment: Optional[str] = None
    variable_of_interest: Optional[str] = None  # The endpoint
    endpoint_id: Optional[str] = None
    intercurrent_events: List[IntercurrentEvent] = field(default_factory=list)
    label: Optional[str] = None
    description: Optional[str] = None
    instance_type: str = "Estimand"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "summaryMeasure": self.summary_measure,
            "instanceType": self.instance_type,
        }
        if self.analysis_population:
            result["analysisPopulation"] = self.analysis_population
        if self.treatment:
            result["treatment"] = self.treatment
        if self.variable_of_interest:
            result["variableOfInterest"] = self.variable_of_interest
        if self.endpoint_id:
            result["endpointId"] = self.endpoint_id
        if self.intercurrent_events:
            result["intercurrentEvents"] = [ie.to_dict() for ie in self.intercurrent_events]
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
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
        result = {
            "id": self.id,
            "name": self.name,
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
