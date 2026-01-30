"""Interventions extraction phase."""

from typing import Optional
import uuid
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class InterventionsPhase(BasePhase):
    """Extract interventions, products, administrations, and substances."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Interventions",
            display_name="Interventions",
            phase_number=5,
            output_filename="6_interventions.json",
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.has_arms():
            params['existing_arms'] = context.arms
        if context.indication:
            params['study_indication'] = context.indication
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        existing_arms: Optional[list] = None,
        study_indication: Optional[str] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.interventions import extract_interventions
        
        result = extract_interventions(
            pdf_path,
            model_name=model,
            existing_arms=existing_arms,
            study_indication=study_indication,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_interventions_confidence
        if result.data:
            conf = calculate_interventions_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_interventions(result.data)
    
    def save_result(self, result: PhaseResult, output_path: str) -> None:
        from extraction.interventions.extractor import save_interventions_result
        
        class ResultWrapper:
            def __init__(self, success, data, error=None):
                self.success = success
                self.data = data
                self.error = error
        
        wrapper = ResultWrapper(result.success, result.data, result.error)
        save_interventions_result(wrapper, output_path)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add interventions to study_version and combined."""
        interventions_added = False
        
        if result.success and result.data:
            data = result.data
            study_version["studyInterventions"] = [i.to_dict() for i in data.interventions]
            study_version["administrableProducts"] = [p.to_dict() for p in data.products]
            combined["administrations"] = [a.to_dict() for a in data.administrations]
            combined["substances"] = [s.to_dict() for s in data.substances]
            interventions_added = True
        
        # Fallback to previously extracted interventions
        if not interventions_added and previous_extractions.get('interventions'):
            prev = previous_extractions['interventions']
            if prev.get('interventions'):
                intv = prev['interventions']
                if intv.get('studyInterventions'):
                    study_version["studyInterventions"] = intv['studyInterventions']
                if intv.get('administrableProducts'):
                    # Ensure administrableDoseForm has required standardCode (USDM 4.0)
                    products = self._fix_dose_form_codes(intv['administrableProducts'])
                    study_version["administrableProducts"] = products
                if intv.get('administrations'):
                    combined["administrations"] = intv['administrations']
                if intv.get('substances'):
                    combined["substances"] = intv['substances']
                if intv.get('medicalDevices'):
                    study_version["medicalDevices"] = intv['medicalDevices']
    
    def _fix_dose_form_codes(self, products: list) -> list:
        """Ensure dose form codes have required standardCode field."""
        fixed = []
        for p in products:
            if isinstance(p, dict):
                dose_form = p.get('administrableDoseForm', {})
                if dose_form and 'code' in dose_form and 'standardCode' not in dose_form:
                    p = dict(p)
                    p['administrableDoseForm'] = {
                        **dose_form,
                        'standardCode': {
                            'id': str(uuid.uuid4()),
                            'code': dose_form.get('code', ''),
                            'codeSystem': dose_form.get('codeSystem', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl'),
                            'codeSystemVersion': dose_form.get('codeSystemVersion', '25.01d'),
                            'decode': dose_form.get('decode', ''),
                            'instanceType': 'Code',
                        }
                    }
            fixed.append(p)
        return fixed


# Register the phase
register_phase(InterventionsPhase())
