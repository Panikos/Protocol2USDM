"""
Procedures & Devices Extractor - Phase 10 of USDM Expansion

Extracts clinical procedures, medical devices, and drug ingredients from protocol.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    ProceduresDevicesData,
    ProceduresDevicesResult,
    Procedure,
    MedicalDevice,
    MedicalDeviceIdentifier,
    Ingredient,
    Strength,
    ProcedureType,
    DeviceType,
)
from .prompts import get_procedures_prompt, get_system_prompt

logger = logging.getLogger(__name__)


def find_procedure_pages(
    pdf_path: str,
    max_pages_to_scan: int = 60,
) -> List[int]:
    """
    Find pages containing procedure and device information using heuristics.
    """
    import fitz
    
    procedure_keywords = [
        r'procedure',
        r'blood\s+draw',
        r'blood\s+sample',
        r'venipuncture',
        r'biopsy',
        r'imaging',
        r'x-ray',
        r'ct\s+scan',
        r'mri',
        r'ultrasound',
        r'ecg',
        r'electrocardiogram',
        r'echocardiogram',
        r'infusion',
        r'injection',
        r'administration\s+of',
        r'specimen\s+collection',
        r'sample\s+collection',
        r'physical\s+examination',
        r'vital\s+signs',
        r'medical\s+device',
        r'drug\s+delivery',
        r'autoinjector',
        r'prefilled\s+syringe',
        r'infusion\s+pump',
        r'inhaler',
        r'nebulizer',
    ]
    
    pattern = re.compile('|'.join(procedure_keywords), re.IGNORECASE)
    
    procedure_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            # Count keyword matches on this page
            matches = len(pattern.findall(text))
            if matches >= 2:  # Require at least 2 keyword matches
                procedure_pages.append(page_num)
                logger.debug(f"Found procedure keywords on page {page_num + 1} ({matches} matches)")
        
        doc.close()
        
        # Limit to most relevant pages
        if len(procedure_pages) > 15:
            procedure_pages = procedure_pages[:15]
        
        logger.info(f"Found {len(procedure_pages)} potential procedure pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        procedure_pages = list(range(min(20, get_page_count(pdf_path))))
    
    return procedure_pages


def parse_procedure_type(type_str: str) -> Optional[ProcedureType]:
    """Parse procedure type string to enum."""
    if not type_str:
        return None
    type_map = {
        'diagnostic': ProcedureType.DIAGNOSTIC,
        'therapeutic': ProcedureType.THERAPEUTIC,
        'surgical': ProcedureType.SURGICAL,
        'sampling': ProcedureType.SAMPLING,
        'sample collection': ProcedureType.SAMPLING,
        'imaging': ProcedureType.IMAGING,
        'monitoring': ProcedureType.MONITORING,
        'assessment': ProcedureType.ASSESSMENT,
    }
    return type_map.get(type_str.lower())


def parse_device_type(type_str: str) -> Optional[DeviceType]:
    """Parse device type string to enum."""
    if not type_str:
        return None
    type_map = {
        'drug delivery device': DeviceType.DRUG_DELIVERY,
        'drug delivery': DeviceType.DRUG_DELIVERY,
        'diagnostic device': DeviceType.DIAGNOSTIC,
        'diagnostic': DeviceType.DIAGNOSTIC,
        'monitoring device': DeviceType.MONITORING,
        'monitoring': DeviceType.MONITORING,
        'implantable device': DeviceType.IMPLANTABLE,
        'implantable': DeviceType.IMPLANTABLE,
        'wearable device': DeviceType.WEARABLE,
        'wearable': DeviceType.WEARABLE,
        'imaging equipment': DeviceType.IMAGING,
        'imaging': DeviceType.IMAGING,
        'laboratory equipment': DeviceType.LABORATORY,
        'laboratory': DeviceType.LABORATORY,
    }
    return type_map.get(type_str.lower())


def extract_procedures_devices(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    output_dir: Optional[str] = None,
) -> ProceduresDevicesResult:
    """
    Extract procedures and devices from protocol PDF.
    """
    logger.info("Starting procedures/devices extraction...")
    
    # Find relevant pages
    pages = find_procedure_pages(pdf_path)
    if not pages:
        logger.warning("No procedure pages found, using first 20 pages")
        pages = list(range(min(20, get_page_count(pdf_path))))
    
    # Extract text from pages
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ProceduresDevicesResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Build prompt and call LLM
    prompt = get_procedures_prompt(text)
    system_prompt = get_system_prompt()
    
    try:
        # Combine system prompt with user prompt
        full_prompt = f"{system_prompt}\n\n{prompt}"
        result = call_llm(
            prompt=full_prompt,
            model_name=model,
            json_mode=True,
            temperature=0.1,
        )
        response = result.get('response', '')
        
        # Parse JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        raw_data = json.loads(json_str)
        
        # Parse procedures
        procedures = []
        for p in raw_data.get('procedures', []):
            proc = Procedure(
                id=p.get('id', f"proc_{len(procedures)+1}"),
                name=p.get('name', ''),
                label=p.get('label'),
                description=p.get('description'),
                procedure_type=parse_procedure_type(p.get('procedureType')),
                code=p.get('code'),
            )
            procedures.append(proc)
        
        # Parse medical devices
        devices = []
        for d in raw_data.get('medicalDevices', []):
            device = MedicalDevice(
                id=d.get('id', f"dev_{len(devices)+1}"),
                name=d.get('name', ''),
                label=d.get('label'),
                description=d.get('description'),
                device_type=parse_device_type(d.get('deviceType')),
                manufacturer=d.get('manufacturer'),
                model_number=d.get('modelNumber'),
            )
            devices.append(device)
        
        # Parse device identifiers
        device_identifiers = []
        for di in raw_data.get('deviceIdentifiers', []):
            identifier = MedicalDeviceIdentifier(
                id=di.get('id', f"dev_id_{len(device_identifiers)+1}"),
                text=di.get('text', ''),
                scope_id=di.get('scopeId'),
            )
            device_identifiers.append(identifier)
        
        # Parse ingredients
        ingredients = []
        for i in raw_data.get('ingredients', []):
            ing = Ingredient(
                id=i.get('id', f"ing_{len(ingredients)+1}"),
                name=i.get('name', ''),
                role=i.get('role', 'Active'),
                substance_id=i.get('substanceId'),
            )
            ingredients.append(ing)
        
        # Parse strengths
        strengths = []
        for s in raw_data.get('strengths', []):
            strength = Strength(
                id=s.get('id', f"str_{len(strengths)+1}"),
                value=s.get('value', 0),
                unit=s.get('unit', ''),
                numerator_value=s.get('numeratorValue'),
                numerator_unit=s.get('numeratorUnit'),
                denominator_value=s.get('denominatorValue'),
                denominator_unit=s.get('denominatorUnit'),
            )
            strengths.append(strength)
        
        data = ProceduresDevicesData(
            procedures=procedures,
            devices=devices,
            device_identifiers=device_identifiers,
            ingredients=ingredients,
            strengths=strengths,
        )
        
        # Calculate confidence
        confidence = 0.0
        if procedures or devices or ingredients:
            confidence = min(1.0, (len(procedures) + len(devices) + len(ingredients)) / 10)
        
        result = ProceduresDevicesResult(
            success=True,
            data=data,
            pages_used=pages,
            model_used=model,
            confidence=confidence,
        )
        
        # Save output if directory specified
        if output_dir:
            output_path = Path(output_dir) / "9_procedures_devices.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved procedures/devices to {output_path}")
        
        logger.info(f"Extracted {len(procedures)} procedures, {len(devices)} devices, {len(ingredients)} ingredients")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return ProceduresDevicesResult(
            success=False,
            error=f"JSON parse error: {e}",
            pages_used=pages,
            model_used=model,
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ProceduresDevicesResult(
            success=False,
            error=str(e),
            pages_used=pages,
            model_used=model,
        )
