"""
Study Metadata Extractor - Phase 2 of USDM Expansion

Extracts study identity and metadata from protocol title page and synopsis.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from core.llm_client import call_llm, call_llm_with_image
from .schema import (
    StudyMetadata,
    StudyTitle,
    StudyIdentifier,
    Organization,
    StudyRole,
    Indication,
    StudyPhase,
    TitleType,
    OrganizationType,
    StudyRoleCode,
)
from .prompts import (
    METADATA_EXTRACTION_PROMPT,
    build_metadata_extraction_prompt,
    build_vision_extraction_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class MetadataExtractionResult:
    """Result of metadata extraction."""
    success: bool
    metadata: Optional[StudyMetadata] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def extract_study_metadata(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    title_page_images: Optional[List[str]] = None,
    protocol_text: Optional[str] = None,
    pages: Optional[List[int]] = None,
) -> MetadataExtractionResult:
    """
    Extract study metadata from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model_name: LLM model to use
        title_page_images: Optional pre-rendered images of title pages
        protocol_text: Optional pre-extracted text from title/synopsis pages
        pages: Specific pages to use (0-indexed), defaults to [0, 1, 2]
        
    Returns:
        MetadataExtractionResult with extracted metadata
    """
    result = MetadataExtractionResult(success=False, model_used=model_name)
    
    try:
        # Default to first 3 pages if not specified
        target_pages = pages or [0, 1, 2]
        result.pages_used = target_pages
        
        # Strategy 1: Vision extraction from title page images
        if title_page_images:
            logger.info(f"Extracting metadata from {len(title_page_images)} title page images...")
            vision_result = _extract_with_vision(title_page_images, model_name)
            if vision_result:
                result.raw_response = vision_result
        
        # Strategy 2: Text extraction if we have protocol text
        if protocol_text and not result.raw_response:
            logger.info("Extracting metadata from protocol text...")
            text_result = _extract_with_text(protocol_text, model_name)
            if text_result:
                result.raw_response = text_result
        
        # Strategy 3: Extract text from PDF pages directly
        if not result.raw_response:
            logger.info(f"Extracting text from PDF pages {target_pages}...")
            from core.pdf_utils import extract_text_from_pages
            extracted_text = extract_text_from_pages(pdf_path, target_pages)
            if extracted_text:
                text_result = _extract_with_text(extracted_text, model_name)
                if text_result:
                    result.raw_response = text_result
        
        # Parse the raw response into structured metadata
        if result.raw_response:
            result.metadata = _parse_metadata_response(result.raw_response)
            result.success = result.metadata is not None
            
        if not result.success:
            result.error = "Failed to extract metadata from protocol"
            
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        result.error = str(e)
        
    return result


def _extract_with_vision(
    image_paths: List[str],
    model_name: str,
) -> Optional[Dict[str, Any]]:
    """Extract metadata using vision model on title page images."""
    try:
        prompt = build_vision_extraction_prompt()
        
        # Use first image (title page) for vision extraction
        response = call_llm_with_image(
            prompt=prompt,
            image_path=image_paths[0],
            model_name=model_name,
        )
        
        if response and 'response' in response:
            return _parse_json_response(response['response'])
            
    except Exception as e:
        logger.warning(f"Vision extraction failed: {e}")
        
    return None


def _extract_with_text(
    protocol_text: str,
    model_name: str,
) -> Optional[Dict[str, Any]]:
    """Extract metadata using text-based LLM call."""
    try:
        prompt = build_metadata_extraction_prompt(protocol_text)
        
        response = call_llm(
            prompt=prompt,
            model_name=model_name,
        )
        
        if response and 'response' in response:
            return _parse_json_response(response['response'])
            
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        
    return None


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    # Clean up common issues
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _parse_metadata_response(raw: Dict[str, Any]) -> Optional[StudyMetadata]:
    """Parse raw LLM response into StudyMetadata object."""
    try:
        # Extract titles
        titles = []
        for i, title_data in enumerate(raw.get('titles', [])):
            if isinstance(title_data, dict) and title_data.get('text'):
                title_type = _map_title_type(title_data.get('type', 'Official Study Title'))
                titles.append(StudyTitle(
                    id=f"title_{i+1}",
                    text=title_data['text'],
                    type=title_type,
                ))
        
        # Extract organizations
        organizations = []
        org_id_map = {}  # Map org name to ID for reference
        for i, org_data in enumerate(raw.get('organizations', [])):
            if isinstance(org_data, dict) and org_data.get('name'):
                org_id = f"org_{i+1}"
                org_type = _map_org_type(org_data.get('type', 'Pharmaceutical Company'))
                organizations.append(Organization(
                    id=org_id,
                    name=org_data['name'],
                    type=org_type,
                ))
                org_id_map[org_data['name']] = org_id
        
        # Extract identifiers
        identifiers = []
        for i, id_data in enumerate(raw.get('identifiers', [])):
            if isinstance(id_data, dict) and id_data.get('value'):
                # Find scope organization
                registry = id_data.get('registry', 'Unknown')
                scope_id = _find_scope_org(registry, org_id_map, organizations)
                
                identifiers.append(StudyIdentifier(
                    id=f"id_{i+1}",
                    text=id_data['value'],
                    scope_id=scope_id,
                ))
        
        # Extract roles from organizations
        roles = []
        for i, org_data in enumerate(raw.get('organizations', [])):
            if isinstance(org_data, dict) and org_data.get('role'):
                role_code = _map_role_code(org_data['role'])
                org_id = org_id_map.get(org_data.get('name', ''), f"org_{i+1}")
                roles.append(StudyRole(
                    id=f"role_{i+1}",
                    name=org_data['role'],
                    code=role_code,
                    organization_ids=[org_id],
                ))
        
        # Extract indication
        indications = []
        indication_data = raw.get('indication')
        if isinstance(indication_data, dict) and indication_data.get('name'):
            indications.append(Indication(
                id="indication_1",
                name=indication_data['name'],
                description=indication_data.get('description'),
                is_rare_disease=indication_data.get('isRareDisease', False),
            ))
        
        # Extract study phase
        study_phase = None
        phase_data = raw.get('studyPhase')
        if phase_data:
            # Handle both string and dict formats
            if isinstance(phase_data, str) and phase_data.lower() != 'null':
                study_phase = StudyPhase(phase=phase_data)
            elif isinstance(phase_data, dict):
                phase_str = phase_data.get('phase') or phase_data.get('code') or phase_data.get('decode')
                if phase_str:
                    study_phase = StudyPhase(phase=str(phase_str))
        
        # Extract protocol version
        version_data = raw.get('protocolVersion', {})
        protocol_version = version_data.get('version') if isinstance(version_data, dict) else None
        protocol_date = version_data.get('date') if isinstance(version_data, dict) else None
        amendment = version_data.get('amendment') if isinstance(version_data, dict) else None
        
        # Build study name from official title
        study_name = "Unknown Study"
        for title in titles:
            if title.type == TitleType.OFFICIAL:
                study_name = title.text[:100]  # Truncate for name
                break
        if study_name == "Unknown Study" and titles:
            study_name = titles[0].text[:100]
        
        return StudyMetadata(
            study_name=study_name,
            titles=titles,
            identifiers=identifiers,
            organizations=organizations,
            roles=roles,
            indications=indications,
            study_phase=study_phase,
            study_type=raw.get('studyType'),
            protocol_version=protocol_version,
            protocol_date=protocol_date,
            amendment_number=amendment,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse metadata response: {e}")
        return None


def _map_title_type(type_str: str) -> TitleType:
    """Map string to TitleType enum."""
    if not type_str:
        return TitleType.OFFICIAL
    type_lower = str(type_str).lower()
    if 'brief' in type_lower or 'short' in type_lower:
        return TitleType.BRIEF
    elif 'acronym' in type_lower:
        return TitleType.ACRONYM
    elif 'scientific' in type_lower:
        return TitleType.SCIENTIFIC
    elif 'public' in type_lower:
        return TitleType.PUBLIC
    return TitleType.OFFICIAL


def _map_org_type(type_str: str) -> OrganizationType:
    """Map string to OrganizationType enum."""
    if not type_str:
        return OrganizationType.PHARMACEUTICAL_COMPANY
    type_lower = str(type_str).lower()
    if 'cro' in type_lower or 'contract' in type_lower:
        return OrganizationType.CRO
    elif 'academ' in type_lower or 'university' in type_lower:
        return OrganizationType.ACADEMIC
    elif 'regulator' in type_lower or 'fda' in type_lower or 'ema' in type_lower:
        return OrganizationType.REGULATORY_AGENCY
    elif 'hospital' in type_lower or 'healthcare' in type_lower or 'clinic' in type_lower:
        return OrganizationType.HEALTHCARE
    elif 'government' in type_lower:
        return OrganizationType.GOVERNMENT
    elif 'lab' in type_lower:
        return OrganizationType.LABORATORY
    elif 'registry' in type_lower:
        return OrganizationType.REGISTRY
    elif 'device' in type_lower:
        return OrganizationType.MEDICAL_DEVICE
    return OrganizationType.PHARMACEUTICAL_COMPANY


def _map_role_code(role_str: str) -> StudyRoleCode:
    """Map string to StudyRoleCode enum."""
    if not role_str:
        return StudyRoleCode.SPONSOR
    role_lower = str(role_str).lower()
    if 'co-sponsor' in role_lower or 'cosponsor' in role_lower:
        return StudyRoleCode.CO_SPONSOR
    elif 'local sponsor' in role_lower:
        return StudyRoleCode.LOCAL_SPONSOR
    elif 'sponsor' in role_lower:
        return StudyRoleCode.SPONSOR
    elif 'cro' in role_lower or 'contract' in role_lower:
        return StudyRoleCode.CRO
    elif 'principal' in role_lower or 'pi' in role_lower:
        return StudyRoleCode.PRINCIPAL_INVESTIGATOR
    elif 'investigator' in role_lower:
        return StudyRoleCode.INVESTIGATOR
    elif 'regulator' in role_lower:
        return StudyRoleCode.REGULATORY
    elif 'manufacturer' in role_lower:
        return StudyRoleCode.MANUFACTURER
    elif 'statistic' in role_lower:
        return StudyRoleCode.STATISTICIAN
    elif 'medical' in role_lower:
        return StudyRoleCode.MEDICAL_EXPERT
    elif 'project' in role_lower:
        return StudyRoleCode.PROJECT_MANAGER
    elif 'site' in role_lower:
        return StudyRoleCode.STUDY_SITE
    return StudyRoleCode.SPONSOR


def _find_scope_org(
    registry: str,
    org_id_map: Dict[str, str],
    organizations: List[Organization],
) -> str:
    """Find the organization ID for an identifier's scope."""
    registry_lower = registry.lower()
    
    # Check if registry matches an existing org
    for org_name, org_id in org_id_map.items():
        if org_name.lower() in registry_lower or registry_lower in org_name.lower():
            return org_id
    
    # Common registries
    if 'clinicaltrials' in registry_lower or 'nct' in registry_lower:
        return "org_ct_gov"
    elif 'eudract' in registry_lower:
        return "org_eudract"
    elif 'sponsor' in registry_lower and organizations:
        # Use first org (usually sponsor)
        return organizations[0].id
        
    return "org_unknown"


def save_metadata_result(
    result: MetadataExtractionResult,
    output_path: str,
) -> None:
    """Save metadata extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.metadata:
        output["metadata"] = result.metadata.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved metadata to {output_path}")
