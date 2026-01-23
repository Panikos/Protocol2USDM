"""
LLM-Based Entity Resolution for USDM Pipeline.

This module replaces fragile fuzzy string matching with semantic LLM-based
entity resolution. It maps abstract extraction concepts (like "RUN_IN", 
"BASELINE", "TREATMENT") to actual protocol-specific entities.

Architecture:
1. Downstream extractors request mappings via EntityResolver
2. EntityResolver uses LLM to semantically understand entity relationships
3. Mappings are cached and stored as first-class data for validation
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities that can be resolved."""
    EPOCH = "epoch"
    VISIT = "visit"
    ACTIVITY = "activity"
    ARM = "arm"
    TIMEPOINT = "timepoint"


@dataclass
class EntityMapping:
    """A resolved mapping from abstract concept to protocol entity."""
    abstract_concept: str  # e.g., "RUN_IN", "BASELINE", "TREATMENT"
    entity_type: EntityType
    resolved_id: str  # Actual entity ID from protocol
    resolved_name: str  # Human-readable name
    confidence: float  # 0.0 to 1.0
    reasoning: str  # LLM's explanation for the mapping
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "abstractConcept": self.abstract_concept,
            "entityType": self.entity_type.value,
            "resolvedId": self.resolved_id,
            "resolvedName": self.resolved_name,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass
class EntityResolutionContext:
    """Context passed to resolver containing available entities."""
    epochs: List[Dict[str, Any]] = field(default_factory=list)
    visits: List[Dict[str, Any]] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    arms: List[Dict[str, Any]] = field(default_factory=list)
    timepoints: List[Dict[str, Any]] = field(default_factory=list)
    protocol_text: str = ""  # Relevant protocol text for context
    
    def get_epoch_summary(self) -> str:
        """Get formatted summary of available epochs."""
        if not self.epochs:
            return "No epochs available"
        lines = []
        for i, e in enumerate(self.epochs):
            lines.append(f"{i+1}. ID: {e.get('id', 'N/A')}, Name: {e.get('name', 'N/A')}")
        return "\n".join(lines)
    
    def get_visit_summary(self) -> str:
        """Get formatted summary of available visits/encounters."""
        if not self.visits:
            return "No visits available"
        lines = []
        for i, v in enumerate(self.visits):
            lines.append(f"{i+1}. ID: {v.get('id', 'N/A')}, Name: {v.get('name', 'N/A')}")
        return "\n".join(lines)


class EntityResolver:
    """
    LLM-based entity resolver that maps abstract concepts to protocol entities.
    
    Usage:
        resolver = EntityResolver(llm_client)
        context = EntityResolutionContext(epochs=design['epochs'], ...)
        
        # Resolve traversal concepts to actual epochs
        mappings = resolver.resolve_epoch_concepts(
            concepts=["RUN_IN", "BASELINE", "TREATMENT"],
            context=context
        )
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize resolver with optional LLM client.
        
        Args:
            llm_client: LLM client for semantic resolution. If None, uses default.
        """
        self._llm_client = llm_client
        self._cache: Dict[str, EntityMapping] = {}
        self._all_mappings: List[EntityMapping] = []
    
    def resolve_epoch_concepts(
        self,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """
        Resolve abstract epoch concepts to actual protocol epochs.
        
        Args:
            concepts: List of abstract concepts like ["RUN_IN", "BASELINE", "TREATMENT"]
            context: Available protocol entities
            
        Returns:
            Dict mapping concept -> EntityMapping (or None if unresolvable)
        """
        if not context.epochs:
            logger.warning("No epochs provided for resolution")
            return {c: None for c in concepts}
        
        # Check cache first
        uncached = [c for c in concepts if c not in self._cache]
        
        if uncached:
            # Use LLM to resolve uncached concepts
            new_mappings = self._llm_resolve_epochs(uncached, context)
            for concept, mapping in new_mappings.items():
                if mapping:
                    self._cache[concept] = mapping
                    self._all_mappings.append(mapping)
        
        return {c: self._cache.get(c) for c in concepts}
    
    def _llm_resolve_epochs(
        self,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """Use LLM to semantically resolve epoch concepts."""
        from core.llm_client import call_llm
        
        # Combine system prompt with user prompt (call_llm doesn't support system_prompt)
        full_prompt = f"{EPOCH_RESOLUTION_SYSTEM_PROMPT}\n\n{self._build_epoch_resolution_prompt(concepts, context)}"
        
        try:
            result = call_llm(
                full_prompt,
                json_mode=True,
                extractor_name="entity_resolver",  # Uses semantic task config
            )
            response = result.get('response', '')
            if result.get('error'):
                logger.error(f"LLM epoch resolution error: {result.get('error')}")
                return {c: None for c in concepts}
            return self._parse_epoch_resolution_response(response, concepts, context)
        except Exception as e:
            logger.error(f"LLM epoch resolution failed: {e}")
            return {c: None for c in concepts}
    
    def _build_epoch_resolution_prompt(
        self,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> str:
        """Build prompt for epoch resolution."""
        return f"""Map the following abstract study phase concepts to the actual protocol epochs.

## Available Protocol Epochs:
{context.get_epoch_summary()}

## Abstract Concepts to Map:
{', '.join(concepts)}

## Protocol Context:
{context.protocol_text[:2000] if context.protocol_text else "No additional context"}

## Instructions:
For each abstract concept, identify which protocol epoch (if any) best represents that phase.
Consider:
- SCREENING: Initial assessment, eligibility determination
- RUN_IN: Washout, stabilization period before treatment
- BASELINE: Day 1 or pre-treatment assessments
- TREATMENT: Active intervention period
- MAINTENANCE: Stable dose continuation
- FOLLOW_UP: Post-treatment monitoring
- END_OF_STUDY: Final assessments

Return JSON array with mappings:
```json
[
  {{
    "concept": "RUN_IN",
    "epochId": "actual_epoch_id_or_null",
    "epochName": "actual_epoch_name_or_null", 
    "confidence": 0.9,
    "reasoning": "Brief explanation"
  }}
]
```

If a concept has no matching epoch, set epochId and epochName to null."""
    
    def _parse_epoch_resolution_response(
        self,
        response: str,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """Parse LLM response into EntityMappings."""
        import re
        
        # Extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            logger.warning("No JSON found in epoch resolution response")
            return {c: None for c in concepts}
        
        try:
            mappings_data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse epoch resolution JSON: {e}")
            return {c: None for c in concepts}
        
        # Build epoch lookup for validation
        epoch_ids = {e.get('id') for e in context.epochs}
        
        result = {}
        for item in mappings_data:
            concept = item.get('concept', '')
            epoch_id = item.get('epochId')
            epoch_name = item.get('epochName')
            confidence = item.get('confidence', 0.5)
            reasoning = item.get('reasoning', '')
            
            if epoch_id and epoch_id in epoch_ids:
                result[concept] = EntityMapping(
                    abstract_concept=concept,
                    entity_type=EntityType.EPOCH,
                    resolved_id=epoch_id,
                    resolved_name=epoch_name or '',
                    confidence=confidence,
                    reasoning=reasoning
                )
            else:
                result[concept] = None
        
        # Fill in any concepts not in response
        for c in concepts:
            if c not in result:
                result[c] = None
        
        return result
    
    def resolve_visit_concepts(
        self,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """Resolve abstract visit concepts to actual protocol visits."""
        # Similar implementation for visits
        if not context.visits:
            return {c: None for c in concepts}
        
        uncached_key = lambda c: f"visit_{c}"
        uncached = [c for c in concepts if uncached_key(c) not in self._cache]
        
        if uncached:
            new_mappings = self._llm_resolve_visits(uncached, context)
            for concept, mapping in new_mappings.items():
                if mapping:
                    self._cache[uncached_key(concept)] = mapping
                    self._all_mappings.append(mapping)
        
        return {c: self._cache.get(uncached_key(c)) for c in concepts}
    
    def _llm_resolve_visits(
        self,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """Use LLM to resolve visit concepts."""
        from core.llm_client import call_llm
        
        prompt = f"""Map the following abstract visit concepts to actual protocol visits/encounters.

## Available Protocol Visits:
{context.get_visit_summary()}

## Abstract Concepts to Map:
{', '.join(concepts)}

Return JSON array with mappings (same format as epoch resolution)."""
        
        try:
            result = call_llm(prompt, json_mode=True, extractor_name="entity_resolver")
            response = result.get('response', '')
            if result.get('error'):
                logger.error(f"LLM visit resolution error: {result.get('error')}")
                return {c: None for c in concepts}
            return self._parse_visit_resolution_response(response, concepts, context)
        except Exception as e:
            logger.error(f"LLM visit resolution failed: {e}")
            return {c: None for c in concepts}
    
    def _parse_visit_resolution_response(
        self,
        response: str,
        concepts: List[str],
        context: EntityResolutionContext
    ) -> Dict[str, Optional[EntityMapping]]:
        """Parse visit resolution response."""
        import re
        
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            return {c: None for c in concepts}
        
        try:
            mappings_data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {c: None for c in concepts}
        
        visit_ids = {v.get('id') for v in context.visits}
        
        result = {}
        for item in mappings_data:
            concept = item.get('concept', '')
            visit_id = item.get('visitId') or item.get('epochId')
            visit_name = item.get('visitName') or item.get('epochName')
            confidence = item.get('confidence', 0.5)
            reasoning = item.get('reasoning', '')
            
            if visit_id and visit_id in visit_ids:
                result[concept] = EntityMapping(
                    abstract_concept=concept,
                    entity_type=EntityType.VISIT,
                    resolved_id=visit_id,
                    resolved_name=visit_name or '',
                    confidence=confidence,
                    reasoning=reasoning
                )
            else:
                result[concept] = None
        
        for c in concepts:
            if c not in result:
                result[c] = None
        
        return result
    
    def get_all_mappings(self) -> List[EntityMapping]:
        """Get all resolved mappings for debugging/export."""
        return self._all_mappings.copy()
    
    def export_mappings(self) -> List[Dict[str, Any]]:
        """Export all mappings as serializable dicts."""
        return [m.to_dict() for m in self._all_mappings]
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()


# System prompt for epoch resolution
EPOCH_RESOLUTION_SYSTEM_PROMPT = """You are a clinical trial protocol analyst specializing in USDM (Unified Study Definition Model) mapping.

Your task is to map abstract study phase concepts to actual protocol-specific epochs/periods.

Key principles:
1. Use semantic understanding, not string matching
2. Consider the temporal sequence of clinical trials
3. Multiple concepts may map to the same epoch (e.g., both BASELINE and DAY_1 might be "Treatment Period Day 1")
4. Some concepts may have no matching epoch - return null in that case
5. Provide confidence scores based on how certain the mapping is

Common mappings (but vary by protocol):
- SCREENING → Usually the first epoch with eligibility assessments
- RUN_IN → Washout/stabilization period (may not exist)
- BASELINE → Day 1 or the epoch containing baseline assessments
- TREATMENT → Main intervention period(s)
- MAINTENANCE → Extended treatment after initial phase
- FOLLOW_UP → Post-treatment monitoring
- END_OF_STUDY → Final visit/termination epoch"""


def create_resolution_context_from_design(design: Dict[str, Any]) -> EntityResolutionContext:
    """
    Create EntityResolutionContext from a USDM study design.
    
    Args:
        design: USDM study design dict
        
    Returns:
        EntityResolutionContext populated with design entities
    """
    return EntityResolutionContext(
        epochs=design.get('epochs', []),
        visits=design.get('encounters', []),
        activities=design.get('activities', []),
        arms=design.get('arms', []),
        timepoints=design.get('scheduledTimePoints', [])
    )
