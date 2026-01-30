"""Objectives & Endpoints extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class ObjectivesPhase(BasePhase):
    """Extract objectives, endpoints, and estimands."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Objectives",
            display_name="Objectives & Endpoints",
            phase_number=3,
            output_filename="4_objectives_endpoints.json",
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.indication:
            params['study_indication'] = context.indication
        if context.phase:
            params['study_phase'] = context.phase
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        study_indication: Optional[str] = None,
        study_phase: Optional[str] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.objectives import extract_objectives_endpoints
        
        result = extract_objectives_endpoints(
            pdf_path,
            model_name=model,
            study_indication=study_indication,
            study_phase=study_phase,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_objectives_confidence
        if result.data:
            conf = calculate_objectives_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_objectives(result.data)
    
    def save_result(self, result: PhaseResult, output_path: str) -> None:
        from extraction.objectives.extractor import save_objectives_result
        
        class ResultWrapper:
            def __init__(self, success, data, error=None):
                self.success = success
                self.data = data
                self.error = error
        
        wrapper = ResultWrapper(result.success, result.data, result.error)
        save_objectives_result(wrapper, output_path)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add objectives and endpoints to study_design."""
        objectives_added = False
        
        if result.success and result.data:
            data = result.data
            study_design["objectives"] = [o.to_dict() for o in data.objectives]
            study_design["endpoints"] = [e.to_dict() for e in data.endpoints]
            if data.estimands:
                study_design["estimands"] = [e.to_dict() for e in data.estimands]
            objectives_added = True
        
        # Fallback to previously extracted objectives
        if not objectives_added and previous_extractions.get('objectives'):
            prev = previous_extractions['objectives']
            if prev.get('objectives'):
                obj = prev['objectives']
                if obj.get('objectives'):
                    study_design["objectives"] = obj['objectives']
                if obj.get('endpoints'):
                    study_design["endpoints"] = obj['endpoints']
                if obj.get('estimands'):
                    study_design["estimands"] = obj['estimands']


# Register the phase
register_phase(ObjectivesPhase())
