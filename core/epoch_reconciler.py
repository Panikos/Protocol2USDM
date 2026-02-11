"""
Epoch Reconciliation Layer

This module provides a centralized mechanism for reconciling epoch data from
multiple extraction sources (SoA, Study Design, Traversal, SAP, etc.) into
a consistent, canonical set of epochs for protocol_usdm.json.

Architecture:
- Any extractor can contribute epochs via contribute()
- Higher priority sources override lower priority for conflicts
- Reconciliation merges all sources into final canonical epochs
- Supports extensibility for future extraction sources (e.g., SAP)

Usage:
    from core.epoch_reconciler import EpochReconciler, EpochContribution
    
    reconciler = EpochReconciler()
    reconciler.contribute("soa", soa_epochs, priority=10)
    reconciler.contribute("traversal", traversal_epochs, priority=25)
    final_epochs = reconciler.reconcile()
"""

import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class EpochContribution:
    """Single epoch contribution from any extraction source."""
    source: str              # "soa", "study_design", "traversal", "sap"
    epoch_id: str            # Original ID (e.g., "epoch_1" or UUID)
    raw_name: str            # Original name as extracted
    canonical_name: str      # Cleaned name (footnotes stripped)
    epoch_category: str      # "main" | "sub" | "exit" | "analysis"
    sequence_order: Optional[int] = None  # Position in main flow (if known)
    parent_id: Optional[str] = None       # For sub-epochs
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0        # Higher = more authoritative
    cdisc_code: Optional[str] = None      # CDISC epoch type code
    cdisc_decode: Optional[str] = None    # CDISC epoch type decode


@dataclass
class ReconciledEpoch:
    """Final reconciled epoch to be written to protocol_usdm.json."""
    id: str
    name: str                    # Canonical name
    raw_name: str                # Original (for audit)
    epoch_category: str          # main | sub | exit | analysis
    sequence_order: Optional[int]
    parent_id: Optional[str]
    sources: List[str]           # Which extractors contributed
    footnote_refs: List[str]     # Extracted footnote markers
    instance_type: str = "StudyEpoch"
    cdisc_code: Optional[str] = None
    cdisc_decode: Optional[str] = None
    
    def to_usdm_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compliant dictionary for protocol_usdm.json."""
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        
        # Add CDISC type if available
        if self.cdisc_code:
            result["type"] = {
                "id": str(uuid.uuid4()),
                "code": self.cdisc_code,
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": self.cdisc_decode or self.epoch_category.title() + " Epoch",
                "instanceType": "Code"
            }
        
        # Add extension attributes for reconciliation metadata
        extensions = []
        
        # Epoch category
        extensions.append({
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/x-epochCategory",
            "instanceType": "ExtensionAttribute",
            "valueString": self.epoch_category
        })
        
        # Sequence order (if main epoch)
        if self.sequence_order is not None:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-epochSequenceOrder",
                "instanceType": "ExtensionAttribute",
                "valueString": str(self.sequence_order)
            })
        
        # Raw name (for audit)
        if self.raw_name != self.name:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-epochRawName",
                "instanceType": "ExtensionAttribute",
                "valueString": self.raw_name
            })
        
        # Sources attribution
        extensions.append({
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/x-epochSources",
            "instanceType": "ExtensionAttribute",
            "valueString": ",".join(self.sources)
        })
        
        # Footnote refs
        if self.footnote_refs:
            extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-epochFootnoteRefs",
                "instanceType": "ExtensionAttribute",
                "valueString": ",".join(self.footnote_refs)
            })
        
        if extensions:
            result["extensionAttributes"] = extensions
        
        return result


# =============================================================================
# Name Cleaning Utilities
# =============================================================================

# Footnote patterns to strip from epoch names
FOOTNOTE_PATTERNS = [
    r'\s+[a-z]$',           # Single letter suffix: "Screening a"
    r'\s+[a-z]\.$',         # Letter with period: "Screening a."
    r'\s*\([a-z]\)$',       # Letter in parens: "Screening (a)"
    r'\s*\[[a-z]\]$',       # Letter in brackets: "Screening [a]"
    r'\s+\d+$',             # Numeric suffix: "Period 1"
    r'\s*\(\d+\)$',         # Number in parens
]

def extract_footnote_refs(name: str) -> List[str]:
    """Extract footnote reference markers from epoch name."""
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


def clean_epoch_name(raw_name: str) -> str:
    """
    Clean epoch name by removing footnote markers and normalizing.
    
    Examples:
        "Screening a" -> "Screening"
        "C-I b" -> "C-I"
        "EOS or ET e" -> "EOS or ET"
    """
    name = raw_name.strip()
    
    # Apply footnote pattern removal
    for pattern in FOOTNOTE_PATTERNS[:4]:  # Only letter-based patterns
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Normalize whitespace
    name = ' '.join(name.split())
    
    return name


def normalize_for_matching(name: str) -> str:
    """Normalize epoch name for fuzzy matching."""
    # Lowercase
    name = name.lower()
    # Remove special chars
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Normalize whitespace
    name = ' '.join(name.split())
    return name


def fuzzy_match_names(name1: str, name2: str, threshold: float = 0.85) -> bool:
    """Check if two epoch names are fuzzy matches."""
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
        # Both have numbers but different - don't match
        return False
    
    # Don't match if both have different Roman numeral suffixes (e.g., "Period I" vs "Period II")
    # After normalization, Roman numerals become lowercase: i, ii, iii, iv, v, vi, etc.
    # Pattern matches Roman numerals anywhere in the string (not just at end)
    roman_pattern = r'\b(i{1,3}|iv|v|vi{0,3}|ix|x)\b'
    roman1 = re.search(roman_pattern, norm1)
    roman2 = re.search(roman_pattern, norm2)
    if roman1 and roman2 and roman1.group(1) != roman2.group(1):
        # Both have Roman numerals but different - don't match
        return False
    
    # Also check if one has a Roman numeral and the other doesn't - they shouldn't match
    # e.g., "Study Period" should not match "Study Period I"
    if (roman1 and not roman2) or (roman2 and not roman1):
        # Only one has Roman numeral - don't match if base names are similar
        base1 = re.sub(roman_pattern, '', norm1).strip()
        base2 = re.sub(roman_pattern, '', norm2).strip()
        if SequenceMatcher(None, base1, base2).ratio() >= 0.9:
            return False
    
    # Sequence matching with higher threshold
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold


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
    return "C98780", "Treatment Epoch"


def enrich_epoch_names_with_clinical_type(
    epochs: List[Dict[str, Any]], 
    encounters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Enrich epoch names by appending clinical epoch type.
    
    Converts generic "Study Period I/II/III/IV" names to descriptive format:
    - "Study Period I | Screening/Lead-in"
    - "Study Period II (52 Weeks) | Treatment Period"
    - "Study Period III (Variable) | Treatment Period"
    - "Study Period IV | Safety Follow-up"
    
    Args:
        epochs: List of epoch dicts with 'id', 'name', etc.
        encounters: List of encounter dicts for timing inference
        
    Returns:
        Same epochs list with enriched names (modified in-place)
    """
    if not epochs:
        return epochs
    
    # Check if epochs look like numbered study periods
    study_period_pattern = re.compile(r'study\s*period', re.IGNORECASE)
    has_study_periods = any(study_period_pattern.search(e.get('name', '')) for e in epochs)
    
    if not has_study_periods:
        return epochs
    
    # Build epoch -> encounters mapping for inference
    epoch_encounters = {}
    for enc in encounters:
        eid = enc.get('epochId')
        if eid:
            epoch_encounters.setdefault(eid, []).append(enc)
    
    logger.info(f"Enriching {len(epochs)} study period names with clinical types")
    
    for epoch in epochs:
        epoch_id = epoch.get('id')
        epoch_name = epoch.get('name', '')
        epoch_name_lower = epoch_name.lower()
        
        # Skip if already has clinical type indicator
        if '|' in epoch_name:
            continue
        
        # Infer clinical type from epoch name keywords
        clinical_type = None
        
        # Check for explicit keywords in epoch name
        if any(kw in epoch_name_lower for kw in ['safety', 'f/u', 'follow-up', 'followup']):
            clinical_type = 'Safety Follow-up'
        elif any(kw in epoch_name_lower for kw in ['screen', 'lead-in', 'leadin', 'run-in', 'runin']):
            clinical_type = 'Screening/Lead-in'
        else:
            # Infer from encounter names within this epoch
            encs = epoch_encounters.get(epoch_id, [])
            clinical_type = _infer_clinical_type_from_encounters(encs)
        
        # Append clinical type to epoch name
        if clinical_type:
            epoch['name'] = f"{epoch_name} | {clinical_type}"
            logger.debug(f"  Enriched: '{epoch_name}' → '{epoch['name']}'")
    
    return epochs


def _infer_clinical_type_from_encounters(encounters: List[Dict[str, Any]]) -> str:
    """Infer clinical epoch type from encounter names/timing."""
    if not encounters:
        return 'Treatment Period'
    
    # Look for timing patterns in encounter names
    for enc in encounters:
        name = enc.get('name', '').lower()
        
        # Check for screening keywords
        if any(kw in name for kw in ['screen', 'eligibility', 'consent', 'lead-in', 'lead in']):
            return 'Screening/Lead-in'
        
        # Check for follow-up keywords
        if any(kw in name for kw in ['follow', 'f/u', 'safety', 'termination', 'et visit', 'post end']):
            return 'Safety Follow-up'
    
    # Default to treatment period
    return 'Treatment Period'


# =============================================================================
# Epoch Reconciler
# =============================================================================

class EpochReconciler:
    """
    Central reconciliation service for epoch data from multiple sources.
    
    Design decisions:
    - Higher priority sources override lower priority for conflicts
    - If no traversal data, first/last epochs marked as main, others as sub
    - Footnote markers are stripped and stored separately
    - All source attributions preserved for audit
    """
    
    def __init__(self):
        self.contributions: Dict[str, List[EpochContribution]] = {}
        self._epoch_id_map: Dict[str, str] = {}  # Maps source IDs to canonical IDs
    
    def contribute(
        self, 
        source: str, 
        epochs: List[Dict[str, Any]], 
        priority: int = 0,
        is_main_sequence: bool = False
    ) -> None:
        """
        Register epoch contributions from an extraction source.
        
        Args:
            source: Source identifier (e.g., "soa", "traversal", "sap")
            epochs: List of epoch dictionaries with at least 'id' and 'name'
            priority: Higher values take precedence in conflicts
            is_main_sequence: If True, all epochs from this source are main epochs
        """
        if source not in self.contributions:
            self.contributions[source] = []
        
        for i, epoch in enumerate(epochs):
            raw_name = epoch.get('name', epoch.get('label', f'Epoch {i+1}'))
            canonical = clean_epoch_name(raw_name)
            footnotes = extract_footnote_refs(raw_name)
            
            # Determine category
            category = epoch.get('epochCategory', 'sub')
            if is_main_sequence:
                category = 'main'
            
            # Get CDISC type
            cdisc_code = epoch.get('type', {}).get('code') if isinstance(epoch.get('type'), dict) else None
            cdisc_decode = epoch.get('type', {}).get('decode') if isinstance(epoch.get('type'), dict) else None
            
            # If no CDISC code, infer from name
            if not cdisc_code:
                cdisc_code, cdisc_decode = infer_cdisc_epoch_type(canonical)
            
            contribution = EpochContribution(
                source=source,
                epoch_id=epoch.get('id', f'{source}_epoch_{i+1}'),
                raw_name=raw_name,
                canonical_name=canonical,
                epoch_category=category,
                sequence_order=epoch.get('sequenceOrder', i if is_main_sequence else None),
                parent_id=epoch.get('parentId'),
                metadata={
                    'footnoteRefs': footnotes,
                    'originalIndex': i,
                    **{k: v for k, v in epoch.items() if k not in ['id', 'name', 'type']}
                },
                priority=priority,
                cdisc_code=cdisc_code,
                cdisc_decode=cdisc_decode
            )
            
            self.contributions[source].append(contribution)
            logger.debug(f"Epoch contribution from {source}: {canonical} (category={category})")
    
    def contribute_traversal_sequence(
        self, 
        sequence: List[str], 
        all_epochs: List[Dict[str, Any]],
        priority: int = 25
    ) -> None:
        """
        Mark epochs in traversal sequence as main epochs.
        
        Args:
            sequence: List of epoch IDs from traversal constraints (e.g., ["epoch_1", "epoch_3"])
            all_epochs: Full list of epochs to resolve IDs against
            priority: Priority for traversal contributions
        """
        # Build index map: epoch_N -> actual epoch
        epoch_by_index = {f"epoch_{i+1}": ep for i, ep in enumerate(all_epochs)}
        epoch_by_id = {ep.get('id'): ep for ep in all_epochs}
        
        main_epochs = []
        for i, seq_id in enumerate(sequence):
            # Resolve epoch_N format to actual epoch
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
    
    def reconcile(self) -> List[ReconciledEpoch]:
        """
        Reconcile all contributions into final canonical epochs.
        
        Returns:
            List of ReconciledEpoch objects ready for protocol_usdm.json
        """
        if not self.contributions:
            logger.warning("No epoch contributions to reconcile")
            return []
        
        # Collect all unique epochs by canonical name
        epochs_by_canonical: Dict[str, List[EpochContribution]] = {}
        
        for source, contribs in self.contributions.items():
            for contrib in contribs:
                # Find existing match
                matched_key = None
                for key in epochs_by_canonical:
                    if fuzzy_match_names(contrib.canonical_name, key):
                        matched_key = key
                        break
                
                if matched_key:
                    epochs_by_canonical[matched_key].append(contrib)
                else:
                    epochs_by_canonical[contrib.canonical_name] = [contrib]
        
        # Reconcile each epoch
        reconciled = []
        for canonical_name, contribs in epochs_by_canonical.items():
            epoch = self._reconcile_epoch(canonical_name, contribs)
            reconciled.append(epoch)
        
        # Sort by sequence order (main epochs first), then by original order
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
        
        logger.info(f"Reconciled {len(reconciled)} epochs from {len(self.contributions)} sources")
        
        # Apply fallback: if no main epochs, mark first and last as main
        main_epochs = [e for e in reconciled if e.epoch_category == 'main']
        if not main_epochs and reconciled:
            logger.info("No main epochs from traversal, applying fallback (first/last as main)")
            reconciled[0].epoch_category = 'main'
            reconciled[0].sequence_order = 1
            if len(reconciled) > 1:
                reconciled[-1].epoch_category = 'main'
                reconciled[-1].sequence_order = 2
        
        return reconciled
    
    def _reconcile_epoch(
        self, 
        canonical_name: str, 
        contributions: List[EpochContribution]
    ) -> ReconciledEpoch:
        """Reconcile multiple contributions for the same epoch."""
        # Sort by priority (highest first)
        contributions.sort(key=lambda c: -c.priority)
        
        # Highest priority contribution wins for most fields
        primary = contributions[0]
        
        # Collect all sources
        sources = list(set(c.source for c in contributions))
        
        # Collect all footnote refs
        footnote_refs = []
        for c in contributions:
            footnote_refs.extend(c.metadata.get('footnoteRefs', []))
        footnote_refs = list(set(footnote_refs))
        
        # Use primary's ID or generate new one
        epoch_id = primary.epoch_id
        if not epoch_id or epoch_id.startswith(('epoch_', 'soa_', 'traversal_')):
            epoch_id = str(uuid.uuid4())
        
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
            id=epoch_id,
            name=canonical_name,
            raw_name=primary.raw_name,
            epoch_category=category,
            sequence_order=sequence_order,
            parent_id=primary.parent_id,
            sources=sources,
            footnote_refs=footnote_refs,
            cdisc_code=primary.cdisc_code,
            cdisc_decode=primary.cdisc_decode
        )
    
    def get_main_epoch_ids(self) -> List[str]:
        """Get IDs of main flow epochs after reconciliation."""
        # This is a convenience method for other pipeline components
        reconciled = self.reconcile()
        return [e.id for e in reconciled if e.epoch_category == 'main']
    
    def clear(self) -> None:
        """Clear all contributions."""
        self.contributions.clear()
        self._epoch_id_map.clear()


# =============================================================================
# Pipeline Integration Helper
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
        traversal_sequence: Epoch IDs from traversal constraints (e.g., ["epoch_1", "epoch_3"])
        study_design_epochs: Additional epochs from study design extraction
        sap_epochs: Analysis epochs from SAP extraction
    
    Returns:
        List of reconciled epoch dictionaries ready for protocol_usdm.json
    """
    reconciler = EpochReconciler()
    
    # SoA epochs (base priority)
    if soa_epochs:
        reconciler.contribute("soa", soa_epochs, priority=10)
    
    # Study design epochs (can add metadata)
    if study_design_epochs:
        reconciler.contribute("study_design", study_design_epochs, priority=20)
    
    # Traversal sequence (identifies main epochs)
    if traversal_sequence and soa_epochs:
        reconciler.contribute_traversal_sequence(
            traversal_sequence, 
            soa_epochs,  # Resolve against SoA epochs
            priority=25
        )
    
    # SAP epochs (can add analysis-specific epochs)
    if sap_epochs:
        reconciler.contribute("sap", sap_epochs, priority=30)
    
    # Reconcile and convert to dictionaries
    reconciled = reconciler.reconcile()
    return [epoch.to_usdm_dict() for epoch in reconciled]
