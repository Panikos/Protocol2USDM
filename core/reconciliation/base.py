"""
Base Entity Reconciliation Framework

This module provides the abstract base class and utilities for reconciling
USDM entities from multiple extraction sources.
"""

import re
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, TypeVar, Generic
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# =============================================================================
# Name Matching Utilities
# =============================================================================

def normalize_for_matching(name: str) -> str:
    """Normalize entity name for fuzzy matching."""
    # Lowercase
    name = name.lower()
    # Remove special chars except spaces and hyphens (preserve hyphens for day ranges like "Day 2-3")
    name = re.sub(r'[^a-z0-9\s\-]', '', name)
    # Normalize whitespace
    name = ' '.join(name.split())
    return name


def fuzzy_match_names(name1: str, name2: str, threshold: float = 0.85) -> bool:
    """
    Check if two entity names are fuzzy matches.
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        threshold: Minimum similarity ratio (0-1)
    
    Returns:
        True if names match above threshold
    """
    norm1 = normalize_for_matching(name1)
    norm2 = normalize_for_matching(name2)
    
    # Exact match
    if norm1 == norm2:
        return True
    
    # Don't match if both have different numeric suffixes (e.g., "Period 1" vs "Period 2")
    num_pattern = r'(\d+)\s*$'
    match1 = re.search(num_pattern, norm1)
    match2 = re.search(num_pattern, norm2)
    if match1 and match2 and match1.group(1) != match2.group(1):
        return False
    
    # Sequence matching
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold


# =============================================================================
# Footnote/Reference Utilities
# =============================================================================

FOOTNOTE_PATTERNS = [
    r'\s+[a-z]$',           # Single letter suffix: "Screening a"
    r'\s+[a-z]\.$',         # Letter with period: "Screening a."
    r'\s*\([a-z]\)$',       # Letter in parens: "Screening (a)"
    r'\s*\[[a-z]\]$',       # Letter in brackets: "Screening [a]"
]


def extract_footnote_refs(name: str) -> List[str]:
    """Extract footnote reference markers from entity name."""
    refs = []
    
    # Match single letter suffixes
    match = re.search(r'\s+([a-z])\.?$', name)
    if match:
        refs.append(match.group(1))
    
    # Match letter in parens
    match = re.search(r'\(([a-z])\)$', name)
    if match:
        refs.append(match.group(1))
    
    return refs


def clean_entity_name(raw_name: str) -> str:
    """
    Clean entity name by removing footnote markers and normalizing.
    
    Examples:
        "Screening a" -> "Screening"
        "Physical Exam (b)" -> "Physical Exam"
    """
    name = raw_name.strip()
    
    # Apply footnote pattern removal
    for pattern in FOOTNOTE_PATTERNS:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Normalize whitespace
    name = ' '.join(name.split())
    
    return name


# =============================================================================
# Base Data Models
# =============================================================================

@dataclass
class EntityContribution:
    """Base class for entity contributions from extraction sources."""
    source: str              # "soa", "procedures", "execution", etc.
    entity_id: str           # Original ID
    raw_name: str            # Original name as extracted
    canonical_name: str      # Cleaned name
    priority: int = 0        # Higher = more authoritative
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.canonical_name:
            self.canonical_name = clean_entity_name(self.raw_name)


@dataclass
class ReconciledEntity:
    """Base class for reconciled entities."""
    id: str
    name: str                    # Canonical name
    raw_name: str                # Original (for audit)
    sources: List[str]           # Which extractors contributed
    footnote_refs: List[str]     # Extracted footnote markers
    instance_type: str = "Entity"
    
    @abstractmethod
    def to_usdm_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compliant dictionary."""
        pass
    
    def _base_usdm_dict(self) -> Dict[str, Any]:
        """Base USDM dictionary structure."""
        return {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
    
    def _add_extension_attributes(
        self, 
        result: Dict[str, Any],
        category: Optional[str] = None,
        sequence_order: Optional[int] = None,
        extra_extensions: Optional[List[Dict]] = None
    ) -> None:
        """Add standard extension attributes to result dict."""
        extensions = []
        
        # Raw name (for audit)
        if self.raw_name != self.name:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": f"https://protocol2usdm.io/extensions/x-{self.instance_type.lower()}RawName",
                "instanceType": "ExtensionAttribute",
                "valueString": self.raw_name
            })
        
        # Sources attribution
        extensions.append({
            "id": str(uuid.uuid4()),
            "url": f"https://protocol2usdm.io/extensions/x-{self.instance_type.lower()}Sources",
            "instanceType": "ExtensionAttribute",
            "valueString": ",".join(self.sources)
        })
        
        # Footnote refs
        if self.footnote_refs:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": f"https://protocol2usdm.io/extensions/x-{self.instance_type.lower()}FootnoteRefs",
                "instanceType": "ExtensionAttribute",
                "valueString": ",".join(self.footnote_refs)
            })
        
        # Category
        if category:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": f"https://protocol2usdm.io/extensions/x-{self.instance_type.lower()}Category",
                "instanceType": "ExtensionAttribute",
                "valueString": category
            })
        
        # Sequence order
        if sequence_order is not None:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": f"https://protocol2usdm.io/extensions/x-{self.instance_type.lower()}SequenceOrder",
                "instanceType": "ExtensionAttribute",
                "valueString": str(sequence_order)
            })
        
        # Extra extensions
        if extra_extensions:
            extensions.extend(extra_extensions)
        
        if extensions:
            result["extensionAttributes"] = extensions


# =============================================================================
# Base Reconciler
# =============================================================================

T = TypeVar('T', bound=EntityContribution)
R = TypeVar('R', bound=ReconciledEntity)


class BaseReconciler(ABC, Generic[T, R]):
    """
    Abstract base class for entity reconciliation.
    
    Subclasses must implement:
    - _create_contribution(): Convert raw dict to typed contribution
    - _reconcile_entity(): Merge contributions into reconciled entity
    """
    
    def __init__(self, match_threshold: float = 0.85):
        self.contributions: Dict[str, List[T]] = {}
        self._entity_id_map: Dict[str, str] = {}
        self.match_threshold = match_threshold
    
    @abstractmethod
    def _create_contribution(
        self, 
        source: str,
        entity: Dict[str, Any],
        index: int,
        priority: int,
        **kwargs
    ) -> T:
        """Create a typed contribution from raw entity dict."""
        pass
    
    @abstractmethod
    def _reconcile_entity(
        self,
        canonical_name: str,
        contributions: List[T]
    ) -> R:
        """Reconcile multiple contributions for same entity."""
        pass
    
    def contribute(
        self,
        source: str,
        entities: List[Dict[str, Any]],
        priority: int = 0,
        **kwargs
    ) -> None:
        """
        Register entity contributions from an extraction source.
        
        Args:
            source: Source identifier (e.g., "soa", "procedures")
            entities: List of entity dictionaries
            priority: Higher values take precedence in conflicts
            **kwargs: Additional arguments passed to _create_contribution
        """
        if source not in self.contributions:
            self.contributions[source] = []
        
        for i, entity in enumerate(entities):
            contribution = self._create_contribution(
                source=source,
                entity=entity,
                index=i,
                priority=priority,
                **kwargs
            )
            self.contributions[source].append(contribution)
            logger.debug(f"Contribution from {source}: {contribution.canonical_name}")
    
    def _find_matching_key(
        self, 
        name: str, 
        existing_keys: Dict[str, List[T]]
    ) -> Optional[str]:
        """Find existing key that fuzzy-matches the given name."""
        for key in existing_keys:
            if fuzzy_match_names(name, key, self.match_threshold):
                return key
        return None
    
    def reconcile(self) -> List[R]:
        """
        Reconcile all contributions into final canonical entities.
        
        Returns:
            List of reconciled entity objects
        """
        if not self.contributions:
            logger.warning(f"No contributions to reconcile for {self.__class__.__name__}")
            return []
        
        # Collect all unique entities by canonical name
        entities_by_canonical: Dict[str, List[T]] = {}
        
        for source, contribs in self.contributions.items():
            for contrib in contribs:
                matched_key = self._find_matching_key(
                    contrib.canonical_name, 
                    entities_by_canonical
                )
                
                if matched_key:
                    entities_by_canonical[matched_key].append(contrib)
                else:
                    entities_by_canonical[contrib.canonical_name] = [contrib]
        
        # Reconcile each entity
        reconciled = []
        for canonical_name, contribs in entities_by_canonical.items():
            entity = self._reconcile_entity(canonical_name, contribs)
            reconciled.append(entity)
        
        # Post-process (subclasses can override)
        reconciled = self._post_reconcile(reconciled)
        
        logger.info(
            f"Reconciled {len(reconciled)} entities from "
            f"{len(self.contributions)} sources"
        )
        
        return reconciled
    
    def _post_reconcile(self, reconciled: List[R]) -> List[R]:
        """
        Post-processing hook for reconciled entities.
        Subclasses can override to add sorting, fallback logic, etc.
        """
        return reconciled
    
    def _collect_footnotes(self, contributions: List[T]) -> List[str]:
        """Collect unique footnote refs from all contributions."""
        footnotes = []
        for c in contributions:
            footnotes.extend(c.metadata.get('footnoteRefs', []))
        return list(set(footnotes))
    
    def _collect_sources(self, contributions: List[T]) -> List[str]:
        """Collect unique source names from contributions."""
        return list(set(c.source for c in contributions))
    
    def _get_best_id(self, contributions: List[T], prefix: str = "entity") -> str:
        """
        Get best ID from contributions or generate new UUID.
        
        IMPORTANT: Always preserves the original ID from the highest-priority
        contribution to maintain referential integrity with other entities
        (e.g., encounters reference epochs by ID).
        
        Only generates a new UUID if no ID is present.
        """
        # Sort by priority (highest first)
        sorted_contribs = sorted(contributions, key=lambda c: -c.priority)
        primary_id = sorted_contribs[0].entity_id
        
        # Always preserve existing ID to maintain references from other entities
        if primary_id:
            return primary_id
        
        # Only generate new UUID if truly missing
        return str(uuid.uuid4())
    
    def clear(self) -> None:
        """Clear all contributions."""
        self.contributions.clear()
        self._entity_id_map.clear()
