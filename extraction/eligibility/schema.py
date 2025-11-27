"""
USDM Schema definitions for Eligibility Criteria entities.

Based on USDM v4.0 specification.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class CriterionCategory(Enum):
    """USDM EligibilityCriterion category codes."""
    INCLUSION = "Inclusion"
    EXCLUSION = "Exclusion"


@dataclass
class EligibilityCriterionItem:
    """
    USDM EligibilityCriterionItem entity.
    
    Represents the reusable text content of a criterion.
    Multiple EligibilityCriterion can reference the same Item.
    """
    id: str
    name: str
    text: str
    dictionary_id: Optional[str] = None  # Reference to SyntaxTemplateDictionary
    instance_type: str = "EligibilityCriterionItem"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "instanceType": self.instance_type,
        }
        if self.dictionary_id:
            result["dictionaryId"] = self.dictionary_id
        return result


@dataclass
class EligibilityCriterion:
    """
    USDM EligibilityCriterion entity.
    
    Represents a single inclusion or exclusion criterion with:
    - Category (Inclusion/Exclusion)
    - Identifier (e.g., "I1", "E1")
    - Link to criterion item text
    - Ordering (previous/next pointers)
    """
    id: str
    identifier: str  # Display ID like "I1", "E3", etc.
    category: CriterionCategory
    criterion_item_id: str  # Reference to EligibilityCriterionItem
    name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    previous_id: Optional[str] = None  # For ordering
    next_id: Optional[str] = None  # For ordering
    context_id: Optional[str] = None  # Reference to study design
    instance_type: str = "EligibilityCriterion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "identifier": self.identifier,
            "category": {
                "code": self.category.value,
                "codeSystem": "USDM",
                "decode": self.category.value,
            },
            "criterionItemId": self.criterion_item_id,
            "instanceType": self.instance_type,
        }
        if self.name:
            result["name"] = self.name
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.previous_id:
            result["previousId"] = self.previous_id
        if self.next_id:
            result["nextId"] = self.next_id
        if self.context_id:
            result["contextId"] = self.context_id
        return result


@dataclass
class StudyDesignPopulation:
    """
    USDM StudyDesignPopulation entity.
    
    Defines the target population for a study design,
    linking to eligibility criteria.
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    includes_healthy_subjects: bool = False
    planned_enrollment_number: Optional[int] = None
    planned_maximum_age: Optional[str] = None  # ISO 8601 duration or description
    planned_minimum_age: Optional[str] = None
    planned_sex: Optional[List[str]] = None  # ["Male", "Female", "Both"]
    criterion_ids: List[str] = field(default_factory=list)  # References to EligibilityCriterion
    instance_type: str = "StudyDesignPopulation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "includesHealthySubjects": self.includes_healthy_subjects,
            "criterionIds": self.criterion_ids,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.planned_enrollment_number:
            result["plannedEnrollmentNumber"] = {
                "maxValue": self.planned_enrollment_number,
                "instanceType": "Range",
            }
        if self.planned_maximum_age:
            result["plannedMaximumAge"] = self.planned_maximum_age
        if self.planned_minimum_age:
            result["plannedMinimumAge"] = self.planned_minimum_age
        if self.planned_sex:
            result["plannedSex"] = [
                {"code": s, "codeSystem": "USDM", "decode": s} for s in self.planned_sex
            ]
        return result


@dataclass
class EligibilityData:
    """
    Aggregated eligibility criteria extraction result.
    
    Contains all Phase 1 entities for a protocol.
    """
    # Criterion items (reusable text)
    criterion_items: List[EligibilityCriterionItem] = field(default_factory=list)
    
    # Criteria with categories
    criteria: List[EligibilityCriterion] = field(default_factory=list)
    
    # Population definition
    population: Optional[StudyDesignPopulation] = None
    
    # Summary counts
    inclusion_count: int = 0
    exclusion_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        result = {
            "eligibilityCriterionItems": [item.to_dict() for item in self.criterion_items],
            "eligibilityCriteria": [c.to_dict() for c in self.criteria],
            "summary": {
                "inclusionCount": self.inclusion_count,
                "exclusionCount": self.exclusion_count,
                "totalCount": len(self.criteria),
            }
        }
        if self.population:
            result["population"] = self.population.to_dict()
        return result
    
    @property
    def inclusion_criteria(self) -> List[EligibilityCriterion]:
        """Get only inclusion criteria."""
        return [c for c in self.criteria if c.category == CriterionCategory.INCLUSION]
    
    @property
    def exclusion_criteria(self) -> List[EligibilityCriterion]:
        """Get only exclusion criteria."""
        return [c for c in self.criteria if c.category == CriterionCategory.EXCLUSION]
