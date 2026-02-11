"""
Sites List Extractor

Extracts USDM entities from site list documents (CSV/Excel):
- StudySite
- StudyRole
- AssignedPerson
- PersonName
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class PersonName:
    """USDM PersonName entity."""
    id: str
    given_name: str
    family_name: str
    title: Optional[str] = None
    instance_type: str = "PersonName"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "givenName": self.given_name,
            "familyName": self.family_name,
            "instanceType": self.instance_type,
        }
        if self.title:
            result["title"] = self.title
        return result


@dataclass
class AssignedPerson:
    """USDM AssignedPerson entity."""
    id: str
    name_id: str
    role: str
    organization_id: Optional[str] = None
    instance_type: str = "AssignedPerson"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "nameId": self.name_id,
            "role": self.role,
            "instanceType": self.instance_type,
        }
        if self.organization_id:
            result["organizationId"] = self.organization_id
        return result


@dataclass
class StudyRole:
    """USDM StudyRole entity."""
    id: str
    role_code: str  # PI, Sub-I, Coordinator, etc.
    organization_id: str
    person_id: Optional[str] = None
    instance_type: str = "StudyRole"
    
    def to_dict(self) -> Dict[str, Any]:
        # Map role codes to USDM-compliant name and code
        role_names = {
            "PI": ("Principal Investigator", "C19924"),
            "Sub-I": ("Sub-Investigator", "C25936"),
            "Coordinator": ("Study Coordinator", "C25936"),
            "CRA": ("Clinical Research Associate", "C25936"),
            "Sponsor": ("Sponsor", "C70793"),
        }
        name, code = role_names.get(self.role_code, (self.role_code, "C25936"))
        
        result = {
            "id": self.id,
            "name": name,  # Required by USDM
            "code": {  # Required by USDM - Code object
                "id": f"code_{self.id}",
                "code": code,
                "codeSystem": "http://www.cdisc.org",
                "decode": name,
                "instanceType": "Code"
            },
            "organizationId": self.organization_id,
            "instanceType": self.instance_type,
        }
        if self.person_id:
            result["personId"] = self.person_id
        return result


@dataclass
class Organization:
    """USDM Organization entity - required for StudyRole references."""
    id: str
    name: str
    type_code: str = "C21541"  # Healthcare Facility (USDM CT C188724)
    identifier: str = ""  # Will be set from site_number
    instance_type: str = "Organization"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "identifierScheme": "SITE_NUMBER",  # Required by USDM
            "identifier": self.identifier or self.id,  # Required by USDM
            "type": {
                "id": f"orgtype_{self.id}",
                "code": self.type_code,
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-03-29",
                "decode": "Healthcare Facility",
                "instanceType": "Code"
            },
            "instanceType": self.instance_type,
        }


@dataclass
class StudySite:
    """USDM StudySite entity."""
    id: str
    name: str
    site_number: Optional[str] = None
    organization_id: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    country: Optional[str] = None
    status: str = "Active"  # Active, Inactive, Closed
    instance_type: str = "StudySite"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "instanceType": self.instance_type,
        }
        if self.site_number:
            result["siteNumber"] = self.site_number
        if self.organization_id:
            result["organizationId"] = self.organization_id
        if self.address:
            result["address"] = self.address
        if self.country:
            result["country"] = self.country
        return result


@dataclass
class SitesData:
    """Container for sites extraction results."""
    sites: List[StudySite] = field(default_factory=list)
    roles: List[StudyRole] = field(default_factory=list)
    persons: List[AssignedPerson] = field(default_factory=list)
    names: List[PersonName] = field(default_factory=list)
    organizations: List[Organization] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "studySites": [s.to_dict() for s in self.sites],
            "studyRoles": [r.to_dict() for r in self.roles],
            "assignedPersons": [p.to_dict() for p in self.persons],
            "personNames": [n.to_dict() for n in self.names],
            "organizations": [o.to_dict() for o in self.organizations],
            "summary": {
                "siteCount": len(self.sites),
                "roleCount": len(self.roles),
                "personCount": len(self.persons),
                "organizationCount": len(self.organizations),
            }
        }


@dataclass
class SitesExtractionResult:
    """Result container for sites extraction."""
    success: bool
    data: Optional[SitesData] = None
    error: Optional[str] = None
    source_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "sourceFile": self.source_file,
        }
        if self.data:
            result["sitesData"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result


def extract_from_sites(
    sites_path: str,
    output_dir: Optional[str] = None,
) -> SitesExtractionResult:
    """
    Extract site information from site list file (CSV/Excel).
    
    Expected columns:
    - Site Number, Site Name, Country, City, PI Name, Status
    """
    logger.info(f"Extracting from sites list: {sites_path}")
    
    path = Path(sites_path)
    if not path.exists():
        return SitesExtractionResult(
            success=False,
            error=f"Sites file not found: {sites_path}",
            source_file=sites_path,
        )
    
    try:
        import pandas as pd
        
        # Read file based on extension
        if path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(sites_path)
        elif path.suffix.lower() == '.csv':
            df = pd.read_csv(sites_path)
        else:
            return SitesExtractionResult(
                success=False,
                error=f"Unsupported file format: {path.suffix}",
                source_file=sites_path,
            )
        
        # Normalize column names
        df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
        
        sites = []
        roles = []
        persons = []
        names = []
        organizations = []
        
        for idx, row in df.iterrows():
            site_id = f"site_{idx+1}"
            org_id = f"org_{idx+1}"  # Organization ID for this site
            
            site_name = str(row.get('site_name', row.get('name', f'Site {idx+1}')))
            site_number = str(row.get('site_number', row.get('site_id', f'{idx+1}')))
            
            # Create Organization entity (required for StudyRole.organizationId reference)
            org = Organization(
                id=org_id,
                name=site_name,
                identifier=site_number,  # Use site number as identifier
            )
            organizations.append(org)
            
            # Extract site with reference to organization
            site = StudySite(
                id=site_id,
                name=site_name,
                site_number=str(row.get('site_number', row.get('site_id', ''))),
                organization_id=org_id,  # Link to organization
                country=str(row.get('country', '')),
                status=str(row.get('status', 'Active')),
            )
            sites.append(site)
            
            # Extract PI if present
            pi_name = row.get('pi_name', row.get('principal_investigator', row.get('investigator', '')))
            if pi_name and str(pi_name).strip() and str(pi_name) != 'nan':
                name_parts = str(pi_name).strip().split(' ', 1)
                name_id = f"name_{idx+1}"
                person_id = f"person_{idx+1}"
                
                name = PersonName(
                    id=name_id,
                    given_name=name_parts[0] if name_parts else '',
                    family_name=name_parts[1] if len(name_parts) > 1 else '',
                )
                names.append(name)
                
                person = AssignedPerson(
                    id=person_id,
                    name_id=name_id,
                    role="Principal Investigator",
                )
                persons.append(person)
                
                role = StudyRole(
                    id=f"role_{idx+1}",
                    role_code="Principal Investigator",
                    organization_id=org_id,  # Reference organization, not site
                    person_id=person_id,
                )
                roles.append(role)
        
        data = SitesData(
            sites=sites,
            roles=roles,
            persons=persons,
            names=names,
            organizations=organizations,
        )
        
        result = SitesExtractionResult(
            success=True,
            data=data,
            source_file=sites_path,
        )
        
        if output_dir:
            output_path = Path(output_dir) / "12_study_sites.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Extracted {len(sites)} sites, {len(roles)} roles from sites list")
        return result
        
    except ImportError:
        return SitesExtractionResult(
            success=False,
            error="pandas not installed. Run: pip install pandas openpyxl",
            source_file=sites_path,
        )
    except Exception as e:
        logger.error(f"Sites extraction failed: {e}")
        return SitesExtractionResult(
            success=False,
            error=str(e),
            source_file=sites_path,
        )
