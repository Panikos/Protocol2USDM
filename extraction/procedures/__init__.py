"""
Procedures & Devices Extraction Module - Phase 10

Extracts USDM entities:
- Procedure
- MedicalDevice
- MedicalDeviceIdentifier
- Ingredient
- Strength
"""

from .schema import (
    Procedure,
    MedicalDevice,
    MedicalDeviceIdentifier,
    Ingredient,
    Strength,
    ProceduresDevicesData,
    ProceduresDevicesResult,
    ProcedureType,
    DeviceType,
)
from .extractor import extract_procedures_devices

__all__ = [
    'Procedure',
    'MedicalDevice',
    'MedicalDeviceIdentifier',
    'Ingredient',
    'Strength',
    'ProceduresDevicesData',
    'ProceduresDevicesResult',
    'ProcedureType',
    'DeviceType',
    'extract_procedures_devices',
]
