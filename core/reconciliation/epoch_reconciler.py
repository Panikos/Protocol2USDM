"""
Epoch Reconciliation

Reconciles epoch data from multiple extraction sources (SoA, Study Design, 
Traversal, SAP) into canonical epochs for protocol_usdm.json.
"""

import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .base import (
    BaseReconciler,
    EntityContribution,
    ReconciledEntity,
    clean_entity_name,
    extract_footnote_refs,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CDISC Epoch Type Mapping
# =============================================================================

EPOCH_TYPE_CODES = {
    "screening": ("C48262", "Trial Screening"),
    "treatment": ("C101526", "Treatment Epoch"),
    "follow-up": ("C99158", "Clinical Study Follow-up"),
    "followup": ("C99158", "Clinical Study Follow-up"),
    "washout": ("C48262", "Trial Screening"),  # No dedicated NCI code; closest match
    "wash-out": ("C48262", "Trial Screening"),
    "run-in": ("C98779", "Run-in Period"),
    "runin": ("C98779", "Run-in Period"),
}


def infer_cdisc_epoch_type(name: str) -> tuple:
    """Infer CDISC epoch type code from epoch name."""
    name_lower = name.lower()
    
    for keyword, (code, decode) in EPOCH_TYPE_CODES.items():
        if keyword in name_lower:
            return code, decode
    
    # Default to Treatment Epoch
    return "C101526", "Treatment Epoch"


def enrich_epoch_names_with_clinical_type(
    epochs: List[Dict[str, Any]],
    encounters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Append inferred clinical type labels to generic study-period epoch names.

    Examples:
      - "Study Period I" -> "Study Period I | Screening/Lead-in"
      - "Study Period II" -> "Study Period II | Treatment Period"
    """
    if not epochs:
        return epochs

    study_period_pattern = re.compile(r"study\s*period", re.IGNORECASE)
    has_study_periods = any(study_period_pattern.search(e.get("name", "")) for e in epochs)
    if not has_study_periods:
        return epochs

    # Build epoch -> encounters mapping for inference
    epoch_encounters: Dict[str, List[Dict[str, Any]]] = {}
    for enc in encounters:
        eid = enc.get("epochId")
        if eid:
            epoch_encounters.setdefault(eid, []).append(enc)

    logger.info(f"Enriching {len(epochs)} study period names with clinical types")

    for epoch in epochs:
        epoch_id = epoch.get("id")
        epoch_name = epoch.get("name", "")
        epoch_name_lower = epoch_name.lower()

        # Skip if already enriched.
        if "|" in epoch_name:
            continue

        clinical_type: Optional[str] = None

        if any(kw in epoch_name_lower for kw in ["safety", "f/u", "follow-up", "followup"]):
            clinical_type = "Safety Follow-up"
        elif any(kw in epoch_name_lower for kw in ["screen", "lead-in", "leadin", "run-in", "runin"]):
            clinical_type = "Screening/Lead-in"
        else:
            clinical_type = _infer_clinical_type_from_encounters(epoch_encounters.get(epoch_id, []))

        if clinical_type:
            epoch["name"] = f"{epoch_name} | {clinical_type}"

    return epochs


def _infer_clinical_type_from_encounters(encounters: List[Dict[str, Any]]) -> str:
    """Infer epoch clinical type from encounter names."""
    if not encounters:
        return "Treatment Period"

    for enc in encounters:
        name = enc.get("name", "").lower()
        if any(kw in name for kw in ["screen", "eligibility", "consent", "lead-in", "lead in"]):
            return "Screening/Lead-in"
        if any(kw in name for kw in ["follow", "f/u", "safety", "termination", "et visit", "post end"]):
            return "Safety Follow-up"

    return "Treatment Period"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class EpochContribution(EntityContribution):
    """Epoch contribution from an extraction source."""
    epoch_category: str = "sub"      # "main" | "sub" | "exit" | "analysis"
    sequence_order: Optional[int] = None
    parent_id: Optional[str] = None
    cdisc_code: Optional[str] = None
    cdisc_decode: Optional[str] = None


@dataclass
class ReconciledEpoch(ReconciledEntity):
    """Reconciled epoch for protocol_usdm.json."""
    epoch_category: str = "sub"
    sequence_order: Optional[int] = None
    parent_id: Optional[str] = None
    cdisc_code: Optional[str] = None
    cdisc_decode: Optional[str] = None
    instance_type: str = "StudyEpoch"
    
    def to_usdm_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compliant dictionary."""
        result = self._base_usdm_dict()
        
        # Add CDISC type
        if self.cdisc_code:
            result["type"] = {
                "id": str(uuid.uuid4()),
                "code": self.cdisc_code,
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": self.cdisc_decode or f"{self.epoch_category.title()} Epoch",
                "instanceType": "Code"
            }
        
        # Add extension attributes
        extra_extensions = []
        if self.epoch_category:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-epochCategory",
                "instanceType": "ExtensionAttribute",
                "valueString": self.epoch_category
            })
        
        if self.sequence_order is not None:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-epochSequenceOrder",
                "instanceType": "ExtensionAttribute",
                "valueString": str(self.sequence_order)
            })
        
        self._add_extension_attributes(result, extra_extensions=extra_extensions)
        
        return result


# =============================================================================
# Epoch Reconciler
# =============================================================================

class EpochReconciler(BaseReconciler[EpochContribution, ReconciledEpoch]):
    """
    Reconciler for epoch data from multiple sources.
    
    Priority order (default):
    - SoA: 10 (base epochs)
    - Study Design: 20 (additional metadata)
    - Traversal: 25 (main flow identification)
    - SAP: 30 (analysis epochs)
    """
    
    def _create_contribution(
        self,
        source: str,
        entity: Dict[str, Any],
        index: int,
        priority: int,
        is_main_sequence: bool = False,
        **kwargs
    ) -> EpochContribution:
        """Create epoch contribution from raw dict."""
        raw_name = entity.get('name', entity.get('label', f'Epoch {index+1}'))
        canonical = clean_entity_name(raw_name)
        footnotes = extract_footnote_refs(raw_name)
        
        # Determine category
        category = entity.get('epochCategory', 'sub')
        if is_main_sequence:
            category = 'main'
        
        # Get CDISC type
        cdisc_code = None
        cdisc_decode = None
        if isinstance(entity.get('type'), dict):
            cdisc_code = entity['type'].get('code')
            cdisc_decode = entity['type'].get('decode')
        
        if not cdisc_code:
            cdisc_code, cdisc_decode = infer_cdisc_epoch_type(canonical)
        
        return EpochContribution(
            source=source,
            entity_id=entity.get('id', f'{source}_epoch_{index+1}'),
            raw_name=raw_name,
            canonical_name=canonical,
            priority=priority,
            metadata={
                'footnoteRefs': footnotes,
                'originalIndex': index,
                **{k: v for k, v in entity.items() if k not in ['id', 'name', 'type']}
            },
            epoch_category=category,
            sequence_order=entity.get('sequenceOrder', index if is_main_sequence else None),
            parent_id=entity.get('parentId'),
            cdisc_code=cdisc_code,
            cdisc_decode=cdisc_decode,
        )
    
    def _reconcile_entity(
        self,
        canonical_name: str,
        contributions: List[EpochContribution]
    ) -> ReconciledEpoch:
        """Reconcile multiple epoch contributions."""
        # Sort by priority (highest first)
        contributions.sort(key=lambda c: -c.priority)
        primary = contributions[0]
        
        # Determine category - if any source says main, it's main
        category = primary.epoch_category
        for c in contributions:
            if c.epoch_category == 'main':
                category = 'main'
                break
        
        # Get best sequence order
        sequence_order = None
        for c in contributions:
            if c.sequence_order is not None:
                sequence_order = c.sequence_order
                break
        
        return ReconciledEpoch(
            id=self._get_best_id(contributions, "epoch"),
            name=canonical_name,
            raw_name=primary.raw_name,
            sources=self._collect_sources(contributions),
            footnote_refs=self._collect_footnotes(contributions),
            epoch_category=category,
            sequence_order=sequence_order,
            parent_id=primary.parent_id,
            cdisc_code=primary.cdisc_code,
            cdisc_decode=primary.cdisc_decode,
        )
    
    def _post_reconcile(self, reconciled: List[ReconciledEpoch]) -> List[ReconciledEpoch]:
        """Sort epochs and apply fallback logic."""
        # Sort: main epochs first by sequence, then sub epochs
        reconciled.sort(key=lambda e: (
            0 if e.epoch_category == 'main' else 1,
            e.sequence_order if e.sequence_order is not None else 999,
        ))
        
        # Assign sequence numbers to main epochs if not set
        main_count = 0
        for epoch in reconciled:
            if epoch.epoch_category == 'main' and epoch.sequence_order is None:
                main_count += 1
                epoch.sequence_order = main_count
        
        # Fallback: if no main epochs, mark first and last as main
        main_epochs = [e for e in reconciled if e.epoch_category == 'main']
        if not main_epochs and reconciled:
            logger.info("No main epochs from traversal, applying fallback (first/last as main)")
            reconciled[0].epoch_category = 'main'
            reconciled[0].sequence_order = 1
            if len(reconciled) > 1:
                reconciled[-1].epoch_category = 'main'
                reconciled[-1].sequence_order = 2
        
        return reconciled
    
    def contribute_traversal_sequence(
        self,
        sequence: List[str],
        all_epochs: List[Dict[str, Any]],
        priority: int = 25
    ) -> None:
        """
        Mark epochs in traversal sequence as main epochs.
        
        Args:
            sequence: List of epoch IDs (e.g., ["epoch_1", "epoch_3"])
            all_epochs: Full list of epochs to resolve IDs against
            priority: Priority for traversal contributions
        """
        # Build index map
        epoch_by_index = {f"epoch_{i+1}": ep for i, ep in enumerate(all_epochs)}
        epoch_by_id = {ep.get('id'): ep for ep in all_epochs}
        
        main_epochs = []
        for i, seq_id in enumerate(sequence):
            epoch = epoch_by_index.get(seq_id) or epoch_by_id.get(seq_id)
            if epoch:
                main_epochs.append({
                    **epoch,
                    'epochCategory': 'main',
                    'sequenceOrder': i + 1
                })
        
        if main_epochs:
            self.contribute("traversal", main_epochs, priority=priority, is_main_sequence=True)
            logger.info(f"Traversal sequence: {len(main_epochs)} main epochs identified")
    
    def get_main_epoch_ids(self) -> List[str]:
        """Get IDs of main flow epochs after reconciliation."""
        reconciled = self.reconcile()
        return [e.id for e in reconciled if e.epoch_category == 'main']


# =============================================================================
# Pipeline Integration
# =============================================================================

def reconcile_epochs_from_pipeline(
    soa_epochs: List[Dict[str, Any]],
    traversal_sequence: Optional[List[str]] = None,
    study_design_epochs: Optional[List[Dict[str, Any]]] = None,
    sap_epochs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function for pipeline integration.
    
    Args:
        soa_epochs: Epochs from SoA extraction
        traversal_sequence: Epoch IDs from traversal constraints
        study_design_epochs: Additional epochs from study design
        sap_epochs: Analysis epochs from SAP
    
    Returns:
        List of reconciled epoch dictionaries
    """
    reconciler = EpochReconciler()
    
    if soa_epochs:
        reconciler.contribute("soa", soa_epochs, priority=10)
    
    if study_design_epochs:
        reconciler.contribute("study_design", study_design_epochs, priority=20)
    
    if traversal_sequence and soa_epochs:
        reconciler.contribute_traversal_sequence(traversal_sequence, soa_epochs, priority=25)
    
    if sap_epochs:
        reconciler.contribute("sap", sap_epochs, priority=30)
    
    reconciled = reconciler.reconcile()
    return [epoch.to_usdm_dict() for epoch in reconciled]
