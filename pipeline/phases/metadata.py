"""Metadata extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class MetadataPhase(BasePhase):
    """Extract study metadata (titles, identifiers, organizations, phase)."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Metadata",
            display_name="Study Metadata",
            phase_number=2,
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
            if md.indications:
                combined["_temp_indications"] = [i.to_dict() for i in md.indications]
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
                if md.get('indications'):
                    combined["_temp_indications"] = md['indications']


# Register the phase
register_phase(MetadataPhase())
