"""
Extraction phase implementations.

Each phase wraps an existing extractor and implements the BasePhase interface.
"""

from .metadata import MetadataPhase
from .eligibility import EligibilityPhase
from .objectives import ObjectivesPhase
from .studydesign import StudyDesignPhase
from .interventions import InterventionsPhase
from .narrative import NarrativePhase
from .advanced import AdvancedPhase
from .procedures import ProceduresPhase
from .scheduling import SchedulingPhase
from .docstructure import DocStructurePhase
from .amendments import AmendmentDetailsPhase
from .execution import ExecutionPhase
from .sap import SAPPhase
from .sites import SitesPhase

# Import to trigger registration
__all__ = [
    'MetadataPhase',
    'EligibilityPhase',
    'ObjectivesPhase',
    'StudyDesignPhase',
    'InterventionsPhase',
    'NarrativePhase',
    'AdvancedPhase',
    'ProceduresPhase',
    'SchedulingPhase',
    'DocStructurePhase',
    'AmendmentDetailsPhase',
    'ExecutionPhase',
    'SAPPhase',
    'SitesPhase',
]
