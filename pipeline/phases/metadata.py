"""Metadata extraction phase."""

from typing import Optional
from core.usdm_types import generate_uuid
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


def _default_geographic_scope() -> dict:
    """Return a default Global geographic scope for GovernanceDate."""
    return {
        "id": generate_uuid(),
        "type": {
            "id": generate_uuid(),
            "code": "C68846",
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "codeSystemVersion": "25.01d",
            "decode": "Global",
            "instanceType": "Code",
        },
        "instanceType": "GeographicScope",
    }


class MetadataPhase(BasePhase):
    """Extract study metadata (titles, identifiers, organizations, phase)."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Metadata",
            display_name="Study Metadata",
            phase_number=1,
            output_filename="2_study_metadata.json",
        )
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.metadata import extract_study_metadata
        
        result = extract_study_metadata(pdf_path, model_name=model)
        
        return PhaseResult(
            success=result.success,
            data=result.metadata if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_metadata_confidence
        if result.data:
            conf = calculate_metadata_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_metadata(result.data)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add metadata to study_version."""
        metadata_added = False
        
        if result.success and result.data:
            md = result.data
            study_version["titles"] = [t.to_dict() for t in md.titles]
            study_version["studyIdentifiers"] = [i.to_dict() for i in md.identifiers]
            study_version["organizations"] = [o.to_dict() for o in md.organizations]
            if md.study_phase:
                study_version["studyPhase"] = md.study_phase.to_dict()
                # H3: Copy studyPhase to study_design (USDM expects it there)
                study_design["studyPhase"] = md.study_phase.to_dict()
            # C1: Map protocolVersion → versionIdentifier
            if md.protocol_version:
                study_version["versionIdentifier"] = md.protocol_version
            # C2: Map study rationale → StudyVersion.rationale
            if md.study_rationale:
                study_version["rationale"] = md.study_rationale
            # H2: Map governance dates → StudyVersion.dateValues
            date_values = []
            if md.protocol_date:
                date_values.append({
                    "id": generate_uuid(),
                    "name": "Protocol Date",
                    "dateValue": md.protocol_date,
                    "type": {
                        "id": generate_uuid(),
                        "code": "C99905x1",
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": "Protocol Date",
                        "instanceType": "Code",
                    },
                    "geographicScopes": [_default_geographic_scope()],
                    "instanceType": "GovernanceDate",
                })
            if md.sponsor_approval_date:
                date_values.append({
                    "id": generate_uuid(),
                    "name": "Sponsor Approval Date",
                    "dateValue": md.sponsor_approval_date,
                    "type": {
                        "id": generate_uuid(),
                        "code": "C99905x2",
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": "Sponsor Approval Date",
                        "instanceType": "Code",
                    },
                    "geographicScopes": [_default_geographic_scope()],
                    "instanceType": "GovernanceDate",
                })
            if md.original_protocol_date:
                date_values.append({
                    "id": generate_uuid(),
                    "name": "Original Protocol Date",
                    "dateValue": md.original_protocol_date,
                    "type": {
                        "id": generate_uuid(),
                        "code": "C99905x3",
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": "Original Protocol Date",
                        "instanceType": "Code",
                    },
                    "geographicScopes": [_default_geographic_scope()],
                    "instanceType": "GovernanceDate",
                })
            if date_values:
                study_version["dateValues"] = date_values
            # G1: Store enrollment number for cross-phase population enrichment
            if md.planned_enrollment_number:
                combined["_temp_planned_enrollment"] = md.planned_enrollment_number
            if md.indications:
                combined["_temp_indications"] = [i.to_dict() for i in md.indications]
                # M1: Map indication names → StudyVersion.businessTherapeuticAreas
                bta = []
                for ind in md.indications:
                    bta.append({
                        "id": f"bta_{ind.id}",
                        "code": "",
                        "codeSystem": "http://www.nlm.nih.gov/mesh",
                        "decode": ind.name,
                        "instanceType": "Code",
                    })
                if bta:
                    study_version["businessTherapeuticAreas"] = bta
            # L1: Map reference identifiers → StudyVersion.referenceIdentifiers
            if md.reference_identifiers:
                # Resolve sponsor org ID for scopeId
                sponsor_org_id = None
                for org in md.organizations:
                    if org.type and org.type.value == "Sponsor":
                        sponsor_org_id = org.id
                        break
                if not sponsor_org_id and md.organizations:
                    sponsor_org_id = md.organizations[0].id
                ref_ids = []
                for i, ref in enumerate(md.reference_identifiers):
                    raw_type = ref.get("type", "Other")
                    ref_entry = {
                        "id": generate_uuid(),
                        "text": ref.get("text", ""),
                        "type": {
                            "id": generate_uuid(),
                            "code": "C99904",
                            "codeSystem": "http://www.cdisc.org",
                            "codeSystemVersion": "2024-09-27",
                            "decode": raw_type,
                            "instanceType": "Code",
                        },
                        "instanceType": "ReferenceIdentifier",
                    }
                    if sponsor_org_id:
                        ref_entry["scopeId"] = sponsor_org_id
                    ref_ids.append(ref_entry)
                if ref_ids:
                    study_version["referenceIdentifiers"] = ref_ids
            if md.study_type:
                combined["_temp_study_type"] = md.study_type
            metadata_added = True
        
        # Fallback to previously extracted metadata
        if not metadata_added and previous_extractions.get('metadata'):
            prev = previous_extractions['metadata']
            if prev.get('metadata'):
                md = prev['metadata']
                if md.get('titles'):
                    study_version["titles"] = md['titles']
                if md.get('identifiers'):
                    study_version["studyIdentifiers"] = md['identifiers']
                if md.get('organizations'):
                    study_version["organizations"] = md['organizations']
                if md.get('studyPhase'):
                    study_version["studyPhase"] = md['studyPhase']
                    # H3: Copy studyPhase to study_design (fallback path)
                    study_design["studyPhase"] = md['studyPhase']
                # C1: Map protocolVersion → versionIdentifier (fallback path)
                if md.get('protocolVersion'):
                    study_version["versionIdentifier"] = md['protocolVersion']
                # C2: Map studyRationale → rationale (fallback path)
                if md.get('studyRationale'):
                    study_version["rationale"] = md['studyRationale']
                # H2: Map governance dates (fallback path)
                if md.get('dateValues'):
                    study_version["dateValues"] = md['dateValues']
                if md.get('indications'):
                    combined["_temp_indications"] = md['indications']
                if md.get('studyType'):
                    combined["_temp_study_type"] = md['studyType']


# Register the phase
register_phase(MetadataPhase())
