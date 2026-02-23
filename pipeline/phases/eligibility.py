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
            phase_number=2,
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
            item_dicts = [item.to_dict() for item in data.criterion_items]
            criteria_dicts = [c.to_dict() for c in data.criteria]
            
            # Nest each criterion inside its parent item (USDM v4.0)
            self._nest_criteria_in_items(item_dicts, criteria_dicts)
            
            if item_dicts:
                study_version["eligibilityCriterionItems"] = item_dicts
            study_design["eligibilityCriteria"] = criteria_dicts
            if data.population:
                study_design["population"] = data.population.to_dict()
            eligibility_added = True
        
        # Fallback to previously extracted eligibility
        if not eligibility_added and previous_extractions.get('eligibility'):
            prev = previous_extractions['eligibility']
            if prev.get('eligibility'):
                elig = prev['eligibility']
                item_dicts = elig.get('eligibilityCriterionItems') or elig.get('criterionItems') or []
                criteria_dicts = elig.get('eligibilityCriteria') or elig.get('criteria') or []
                
                # Nest criteria in items if not already nested
                self._nest_criteria_in_items(item_dicts, criteria_dicts)
                
                if item_dicts:
                    study_version["eligibilityCriterionItems"] = item_dicts
                if criteria_dicts:
                    study_design["eligibilityCriteria"] = criteria_dicts
                if elig.get('population'):
                    study_design["population"] = elig['population']
    
    @staticmethod
    def _nest_criteria_in_items(items: list, criteria: list) -> None:
        """Nest each EligibilityCriterion inside its parent EligibilityCriterionItem.
        
        USDM v4.0: EligibilityCriterionItem.criterion should contain the
        EligibilityCriterion with category (C25532 Inclusion / C25370 Exclusion).
        """
        if not items or not criteria:
            return
        
        # Build criterion lookup by criterionItemId
        crit_by_item_id = {}
        for c in criteria:
            item_id = c.get('criterionItemId')
            if item_id:
                crit_by_item_id[item_id] = c
        
        for item in items:
            if item.get('criterion'):
                continue  # Already nested
            crit = crit_by_item_id.get(item.get('id'))
            if crit:
                item['criterion'] = crit


# Register the phase
register_phase(EligibilityPhase())
