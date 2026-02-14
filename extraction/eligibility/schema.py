"""
Eligibility Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
For schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml

Based on USDM v4.0 specification.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

# Import utilities from central types module
from core.usdm_types import generate_uuid, Code


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


def _build_participant_quantity(value: int) -> Dict[str, Any]:
    """Build a USDM-compliant Quantity object for participant counts.
    
    USDM v4.0 Quantity requires: id (string), value (float), 
    unit (AliasCode, optional), instanceType = "Quantity".
    """
    return {
        "id": generate_uuid(),
        "value": float(value),
        "unit": {
            "id": generate_uuid(),
            "standardCode": {
                "code": "C25463",
                "codeSystem": "http://www.cdisc.org",
                "decode": "Count",
                "instanceType": "Code",
            },
            "standardCodeAliases": [],
            "instanceType": "AliasCode",
        },
        "instanceType": "Quantity",
    }


@dataclass
class StudyDesignPopulation:
    """
    USDM StudyDesignPopulation entity.
    
    Defines the target population for a study design,
    linking to eligibility criteria.
    
    USDM v4.0 field mapping:
      plannedAge           -> Range (minValue / maxValue)
      plannedEnrollmentNumber -> QuantityRange (maxValue + unit)
      plannedCompletionNumber -> QuantityRange (maxValue + unit)
      plannedSex           -> Code[] (up to 2)
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    includes_healthy_subjects: bool = False
    # --- Demographics (USDM v4.0 names) ---
    planned_enrollment_number: Optional[int] = None
    planned_completion_number: Optional[int] = None
    planned_age_min: Optional[int] = None       # e.g. 18
    planned_age_max: Optional[int] = None       # e.g. 75
    planned_age_unit: str = "Years"              # ISO 8601 unit label
    planned_sex: Optional[List[str]] = None     # ["Male", "Female"]
    criterion_ids: List[str] = field(default_factory=list)
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
        # USDM v4.0: plannedEnrollmentNumber is a Quantity (subclass of QuantityRange)
        if self.planned_enrollment_number:
            result["plannedEnrollmentNumber"] = _build_participant_quantity(self.planned_enrollment_number)
        # USDM v4.0: plannedCompletionNumber is a Quantity (subclass of QuantityRange)
        if self.planned_completion_number:
            result["plannedCompletionNumber"] = _build_participant_quantity(self.planned_completion_number)
        # USDM v4.0: plannedAge is a Range with minValue/maxValue as Quantity objects
        # Both minValue and maxValue are required on Range — default to 0/99 if missing
        if self.planned_age_min is not None or self.planned_age_max is not None:
            unit_code = {
                "id": generate_uuid(),
                "standardCode": {"code": "C29848", "codeSystem": "http://www.cdisc.org", "decode": self.planned_age_unit, "instanceType": "Code"},
                "standardCodeAliases": [],
                "instanceType": "AliasCode",
            }
            effective_min = self.planned_age_min if self.planned_age_min is not None else 0
            effective_max = self.planned_age_max if self.planned_age_max is not None else 99
            age_range: Dict[str, Any] = {"id": generate_uuid(), "instanceType": "Range", "isApproximate": False}
            age_range["minValue"] = {
                "id": generate_uuid(),
                "value": effective_min,
                "unit": unit_code,
                "instanceType": "Quantity",
            }
            age_range["maxValue"] = {
                "id": generate_uuid(),
                "value": effective_max,
                "unit": unit_code,
                "instanceType": "Quantity",
            }
            result["plannedAge"] = age_range
        # USDM v4.0: plannedSex is Code[] (up to 2)
        if self.planned_sex:
            result["plannedSex"] = [
                {
                    "id": generate_uuid(),
                    "code": s,
                    "codeSystem": "http://www.cdisc.org/USDM/sex",
                    "codeSystemVersion": "2024-09-27",
                    "decode": s,
                    "instanceType": "Code",
                }
                for s in self.planned_sex
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
