"""Advanced entities extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class AdvancedPhase(BasePhase):
    """Extract amendments, geographic scope, and countries."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Advanced",
            display_name="Advanced Entities",
            phase_number=8,
            output_filename="8_advanced_entities.json",
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
        from extraction.advanced import extract_advanced_entities
        
        result = extract_advanced_entities(pdf_path, model_name=model)
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_advanced_confidence
        if result.data:
            conf = calculate_advanced_confidence(result.data)
            return conf.overall
        return None
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add advanced entities to study_version and combined."""
        advanced_added = False
        
        if result.success and result.data:
            data = result.data
            if data.amendments:
                study_version["amendments"] = [a.to_dict() for a in data.amendments]
            if data.geographic_scope:
                combined["geographicScope"] = data.geographic_scope.to_dict()
            if data.countries:
                combined["countries"] = [c.to_dict() for c in data.countries]
            advanced_added = True
        
        # Fallback to previously extracted advanced entities
        if not advanced_added and previous_extractions.get('advanced'):
            prev = previous_extractions['advanced']
            if prev.get('advanced'):
                adv = prev['advanced']
                if adv.get('studyAmendments'):
                    study_version["amendments"] = adv['studyAmendments']
                elif adv.get('amendments'):
                    study_version["amendments"] = adv['amendments']
                if adv.get('geographicScope'):
                    combined["geographicScope"] = adv['geographicScope']
                if adv.get('countries'):
                    combined["countries"] = adv['countries']


# Register the phase
register_phase(AdvancedPhase())
