"""
Conditional Source Extraction Modules

These modules extract USDM entities from additional source documents
beyond the main protocol PDF:

- SAP (Statistical Analysis Plan): AnalysisPopulation, Characteristic
- Sites (Site List): StudySite, StudyRole, AssignedPerson
- eCOA (eCOA Specification): ResponseCode, ParameterMap

Usage:
    python main_v2.py protocol.pdf --full-protocol --sap sap.pdf --sites sites.xlsx
"""

from .sap_extractor import extract_from_sap, SAPExtractionResult
from .sites_extractor import extract_from_sites, SitesExtractionResult

__all__ = [
    'extract_from_sap',
    'SAPExtractionResult',
    'extract_from_sites',
    'SitesExtractionResult',
]
