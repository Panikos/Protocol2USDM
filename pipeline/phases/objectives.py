"""Objectives & Endpoints extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


# H5: Level-to-purpose defaults for endpoints missing a purpose value
_LEVEL_PURPOSE_DEFAULTS = {
    "primary": "Efficacy",
    "secondary": "Efficacy",
    "exploratory": "Exploratory",
}


def _default_endpoint_purpose(endpoints: list) -> None:
    """Fill empty Endpoint.purpose based on level decode (H5 gap fix)."""
    for ep in endpoints:
        if ep.get("purpose"):
            continue
        level = ep.get("level")
        if isinstance(level, dict):
            decode = (level.get("decode") or "").strip().lower()
        elif isinstance(level, str):
            decode = level.strip().lower()
        else:
            continue
        for key, default in _LEVEL_PURPOSE_DEFAULTS.items():
            if key in decode:
                ep["purpose"] = default
                break


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
            endpoints = [e.to_dict() for e in data.endpoints]
            # H5: Default Endpoint.purpose based on level if empty
            _default_endpoint_purpose(endpoints)
            study_design["endpoints"] = endpoints
            if data.estimands:
                # Filter out incomplete estimands (ICH E9(R1) requires these fields)
                valid_estimands = []
                for e in data.estimands:
                    e_dict = e.to_dict()
                    # Check for required ICH E9(R1) estimand components
                    has_population = bool(e_dict.get('analysisPopulationId') or e_dict.get('populationSummary'))
                    has_variable = bool(e_dict.get('variableOfInterestId'))
                    has_intervention = bool(e_dict.get('interventionIds'))
                    
                    if has_population and has_variable and has_intervention:
                        valid_estimands.append(e_dict)
                    else:
                        # Log incomplete estimand but still include if it has meaningful content
                        if e_dict.get('name') and e_dict.get('populationSummary'):
                            valid_estimands.append(e_dict)
                
                if valid_estimands:
                    study_design["estimands"] = valid_estimands
            objectives_added = True
        
        # Fallback to previously extracted objectives
        if not objectives_added and previous_extractions.get('objectives'):
            prev = previous_extractions['objectives']
            if prev.get('objectives'):
                obj = prev['objectives']
                if obj.get('objectives'):
                    study_design["objectives"] = obj['objectives']
                if obj.get('endpoints'):
                    eps = obj['endpoints']
                    _default_endpoint_purpose(eps)
                    study_design["endpoints"] = eps
                if obj.get('estimands'):
                    study_design["estimands"] = obj['estimands']


# Register the phase
register_phase(ObjectivesPhase())
