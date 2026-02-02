"""Eligibility criteria extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class EligibilityPhase(BasePhase):
    """Extract eligibility criteria (inclusion/exclusion)."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Eligibility",
            display_name="Eligibility Criteria",
            phase_number=1,
            output_filename="3_eligibility_criteria.json",
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
        from extraction.eligibility import extract_eligibility_criteria
        
        result = extract_eligibility_criteria(
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
        from extraction.confidence import calculate_eligibility_confidence
        if result.data:
            conf = calculate_eligibility_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_eligibility(result.data)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add eligibility criteria to study_version and study_design."""
        eligibility_added = False
        
        if result.success and result.data:
            data = result.data
            if data.criterion_items:
                study_version["eligibilityCriterionItems"] = [
                    item.to_dict() for item in data.criterion_items
                ]
            study_design["eligibilityCriteria"] = [c.to_dict() for c in data.criteria]
            if data.population:
                study_design["population"] = data.population.to_dict()
            eligibility_added = True
        
        # Fallback to previously extracted eligibility
        if not eligibility_added and previous_extractions.get('eligibility'):
            prev = previous_extractions['eligibility']
            if prev.get('eligibility'):
                elig = prev['eligibility']
                if elig.get('criterionItems'):
                    study_version["eligibilityCriterionItems"] = elig['criterionItems']
                if elig.get('criteria'):
                    study_design["eligibilityCriteria"] = elig['criteria']
                if elig.get('population'):
                    study_design["population"] = elig['population']


# Register the phase
register_phase(EligibilityPhase())
