"""
Unified Entity Reconciliation Framework

This package provides a centralized mechanism for reconciling USDM entities from
multiple extraction sources into consistent, canonical data for protocol_usdm.json.

Supported entity types:
- Epochs: Study phases/periods
- Activities: Procedures, assessments, data collection
- Encounters: Visits, timepoints

Architecture:
- BaseReconciler: Abstract base with fuzzy matching, priority merging, source tracking
- Entity-specific reconcilers extend base with custom logic
- Any extractor can contribute via contribute()
- Higher priority sources override lower priority for conflicts

Usage:
    from core.reconciliation import EpochReconciler, ActivityReconciler, EncounterReconciler
    
    reconciler = EpochReconciler()
    reconciler.contribute("soa", soa_epochs, priority=10)
    reconciler.contribute("traversal", traversal_epochs, priority=25)
    final_epochs = reconciler.reconcile()
"""

from .base import (
    BaseReconciler,
    EntityContribution,
    ReconciledEntity,
    fuzzy_match_names,
    normalize_for_matching,
)
from .epoch_reconciler import (
    EpochReconciler,
    EpochContribution,
    ReconciledEpoch,
    reconcile_epochs_from_pipeline,
)
from .activity_reconciler import (
    ActivityReconciler,
    ActivityContribution,
    ReconciledActivity,
    reconcile_activities_from_pipeline,
)
from .encounter_reconciler import (
    EncounterReconciler,
    EncounterContribution,
    ReconciledEncounter,
    reconcile_encounters_from_pipeline,
)

__all__ = [
    # Base
    "BaseReconciler",
    "EntityContribution",
    "ReconciledEntity",
    "fuzzy_match_names",
    "normalize_for_matching",
    # Epochs
    "EpochReconciler",
    "EpochContribution",
    "ReconciledEpoch",
    "reconcile_epochs_from_pipeline",
    # Activities
    "ActivityReconciler",
    "ActivityContribution",
    "ReconciledActivity",
    "reconcile_activities_from_pipeline",
    # Encounters
    "EncounterReconciler",
    "EncounterContribution",
    "ReconciledEncounter",
    "reconcile_encounters_from_pipeline",
]
