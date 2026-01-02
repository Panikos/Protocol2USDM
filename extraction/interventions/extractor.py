"""
Interventions & Products Extractor - Phase 5 of USDM Expansion

Extracts study interventions and products from protocol.
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
    InterventionsData,
    StudyIntervention,
    AdministrableProduct,
    Administration,
    MedicalDevice,
    Substance,
    RouteOfAdministration,
    DoseForm,
    InterventionRole,
)
from .prompts import build_interventions_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class InterventionsExtractionResult:
    """Result of interventions extraction."""
    success: bool
    data: Optional[InterventionsData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_intervention_pages(
    pdf_path: str,
    max_pages_to_scan: int = 50,
) -> List[int]:
    """
    Find pages containing intervention/product information using heuristics.
    """
    import fitz
    
    intervention_keywords = [
        r'investigational\s+product',
        r'study\s+drug',
        r'study\s+treatment',
        r'study\s+intervention',
        r'study\s+medication',
        r'dose\s+and\s+administration',
        r'dosing\s+regimen',
        r'route\s+of\s+administration',
        r'formulation',
        r'pharmaceutical\s+form',
        r'active\s+ingredient',
        r'placebo',
        r'comparator',
    ]
    
    pattern = re.compile('|'.join(intervention_keywords), re.IGNORECASE)
    
    intervention_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            if pattern.search(text):
                intervention_pages.append(page_num)
                logger.debug(f"Found intervention keywords on page {page_num + 1}")
        
        doc.close()
        
        # Include adjacent pages for context
        if intervention_pages:
            expanded = set()
            for p in intervention_pages:
                expanded.add(p)
                if p > 0:
                    expanded.add(p - 1)
                if p < total_pages - 1:
                    expanded.add(p + 1)
            intervention_pages = sorted(expanded)
        
        logger.info(f"Found {len(intervention_pages)} potential intervention pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        
    return intervention_pages


def extract_interventions(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    existing_arms: Optional[List[Dict[str, Any]]] = None,
    study_indication: Optional[str] = None,
) -> InterventionsExtractionResult:
    """
    Extract interventions and products from a protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model_name: LLM model to use
        pages: Specific pages to use
        protocol_text: Optional pre-extracted text
        existing_arms: Treatment arms from study design for reference
        study_indication: Indication from metadata for context
    """
    result = InterventionsExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect intervention pages if not specified
        if pages is None:
            pages = find_intervention_pages(pdf_path)
            if not pages:
                logger.warning("No intervention pages detected, scanning first 30 pages")
                pages = list(range(min(30, get_page_count(pdf_path))))
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Call LLM for extraction
        logger.info("Extracting interventions with LLM...")
        
        # Build context hints from prior extractions
        context_hints = ""
        if existing_arms:
            arm_names = [a.get('name', '') for a in existing_arms if a.get('name')]
            if arm_names:
                context_hints += f"\nKnown treatment arms: {', '.join(arm_names)}"
        if study_indication:
            context_hints += f"\nStudy indication: {study_indication}"
        
        prompt = build_interventions_extraction_prompt(protocol_text, context_hints=context_hints)
        
        response = call_llm(
            prompt=prompt,
            model_name=model_name,
            json_mode=True,
        )
        
        if 'error' in response:
            result.error = response['error']
            return result
        
        # Parse response
        raw_response = _parse_json_response(response.get('response', ''))
        if not raw_response:
            result.error = "Failed to parse LLM response as JSON"
            return result
        
        result.raw_response = raw_response
        
        # Convert to structured data
        result.data = _parse_interventions_response(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {len(result.data.interventions)} interventions, "
                f"{len(result.data.products)} products, "
                f"{len(result.data.administrations)} administration regimens"
            )
        
    except Exception as e:
        logger.error(f"Interventions extraction failed: {e}")
        result.error = str(e)
        
    return result


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _parse_interventions_response(raw: Dict[str, Any]) -> Optional[InterventionsData]:
    """Parse raw LLM response into InterventionsData object.
    
    Handles both legacy format and new USDM-compliant format with ids.
    """
    try:
        interventions = []
        products = []
        administrations = []
        substances = []
        devices = []
        
        # Process interventions - accept both 'interventions' and 'studyInterventions' keys
        int_list = raw.get('interventions', []) or raw.get('studyInterventions', [])
        for i, int_data in enumerate(int_list):
            if not isinstance(int_data, dict):
                continue
            
            role = _map_intervention_role(int_data.get('role', 'Investigational Product'))
            
            interventions.append(StudyIntervention(
                id=int_data.get('id', f"int_{i+1}"),
                name=int_data.get('name', f'Intervention {i+1}'),
                description=int_data.get('description'),
                role=role,
            ))
        
        # Process products - accept both 'products' and 'administrableProducts' keys
        prod_list = raw.get('products', []) or raw.get('administrableProducts', [])
        for i, prod_data in enumerate(prod_list):
            if not isinstance(prod_data, dict):
                continue
            
            dose_form = _map_dose_form(prod_data.get('doseForm', ''))
            
            products.append(AdministrableProduct(
                id=prod_data.get('id', f"prod_{i+1}"),
                name=prod_data.get('name', f'Product {i+1}'),
                description=prod_data.get('description'),
                dose_form=dose_form,
                strength=prod_data.get('strength'),
                manufacturer=prod_data.get('manufacturer'),
            ))
        
        # Process administrations
        for i, admin_data in enumerate(raw.get('administrations', [])):
            if not isinstance(admin_data, dict):
                continue
            
            route = _map_route(admin_data.get('route', ''))
            
            administrations.append(Administration(
                id=admin_data.get('id', f"admin_{i+1}"),
                name=admin_data.get('name', f'Administration {i+1}'),
                dose=admin_data.get('dose'),
                dose_frequency=admin_data.get('frequency') or admin_data.get('doseFrequency'),
                route=route,
                duration=admin_data.get('duration'),
                description=admin_data.get('description'),
            ))
        
        # Process substances
        for i, sub_data in enumerate(raw.get('substances', [])):
            if not isinstance(sub_data, dict):
                continue
            
            substances.append(Substance(
                id=sub_data.get('id', f"sub_{i+1}"),
                name=sub_data.get('name', f'Substance {i+1}'),
                description=sub_data.get('description'),
            ))
        
        # Process devices - accept both 'devices' and 'medicalDevices' keys
        dev_list = raw.get('devices', []) or raw.get('medicalDevices', [])
        for i, dev_data in enumerate(dev_list):
            if not isinstance(dev_data, dict):
                continue
            
            devices.append(MedicalDevice(
                id=dev_data.get('id', f"dev_{i+1}"),
                name=dev_data.get('name', f'Device {i+1}'),
                description=dev_data.get('description'),
                manufacturer=dev_data.get('manufacturer'),
            ))
        
        # Link products to interventions
        for i, intervention in enumerate(interventions):
            if i < len(products):
                intervention.product_ids.append(products[i].id)
            if i < len(administrations):
                intervention.administration_ids.append(administrations[i].id)
        
        # Link substances to products
        for i, product in enumerate(products):
            if i < len(substances):
                product.substance_ids.append(substances[i].id)
        
        return InterventionsData(
            interventions=interventions,
            products=products,
            administrations=administrations,
            substances=substances,
            devices=devices,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse interventions response: {e}")
        return None


def _map_intervention_role(role_str: str) -> InterventionRole:
    """Map string to InterventionRole enum."""
    role_lower = role_str.lower()
    if 'placebo' in role_lower:
        return InterventionRole.PLACEBO
    elif 'comparator' in role_lower:
        return InterventionRole.COMPARATOR
    elif 'rescue' in role_lower:
        return InterventionRole.RESCUE
    elif 'concomitant' in role_lower:
        return InterventionRole.CONCOMITANT
    elif 'background' in role_lower:
        return InterventionRole.BACKGROUND
    return InterventionRole.INVESTIGATIONAL


def _map_dose_form(form_str: str) -> Optional[DoseForm]:
    """Map string to DoseForm enum."""
    if not form_str:
        return None
    form_lower = form_str.lower()
    if 'tablet' in form_lower:
        return DoseForm.TABLET
    elif 'capsule' in form_lower:
        return DoseForm.CAPSULE
    elif 'solution' in form_lower:
        return DoseForm.SOLUTION
    elif 'suspension' in form_lower:
        return DoseForm.SUSPENSION
    elif 'injection' in form_lower:
        return DoseForm.INJECTION
    elif 'cream' in form_lower:
        return DoseForm.CREAM
    elif 'ointment' in form_lower:
        return DoseForm.OINTMENT
    elif 'gel' in form_lower:
        return DoseForm.GEL
    elif 'patch' in form_lower:
        return DoseForm.PATCH
    elif 'powder' in form_lower:
        return DoseForm.POWDER
    elif 'spray' in form_lower:
        return DoseForm.SPRAY
    elif 'inhaler' in form_lower:
        return DoseForm.INHALER
    return DoseForm.OTHER


def _map_route(route_str: str) -> Optional[RouteOfAdministration]:
    """Map string to RouteOfAdministration enum."""
    if not route_str:
        return None
    route_lower = route_str.lower()
    if 'oral' in route_lower:
        return RouteOfAdministration.ORAL
    elif 'intravenous' in route_lower or route_lower == 'iv':
        return RouteOfAdministration.INTRAVENOUS
    elif 'subcutaneous' in route_lower or route_lower == 'sc':
        return RouteOfAdministration.SUBCUTANEOUS
    elif 'intramuscular' in route_lower or route_lower == 'im':
        return RouteOfAdministration.INTRAMUSCULAR
    elif 'topical' in route_lower:
        return RouteOfAdministration.TOPICAL
    elif 'inhalation' in route_lower:
        return RouteOfAdministration.INHALATION
    elif 'intranasal' in route_lower:
        return RouteOfAdministration.INTRANASAL
    elif 'ophthalmic' in route_lower:
        return RouteOfAdministration.OPHTHALMIC
    elif 'transdermal' in route_lower:
        return RouteOfAdministration.TRANSDERMAL
    elif 'rectal' in route_lower:
        return RouteOfAdministration.RECTAL
    elif 'sublingual' in route_lower:
        return RouteOfAdministration.SUBLINGUAL
    return RouteOfAdministration.OTHER


def save_interventions_result(
    result: InterventionsExtractionResult,
    output_path: str,
) -> None:
    """Save interventions extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["interventions"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved interventions to {output_path}")
