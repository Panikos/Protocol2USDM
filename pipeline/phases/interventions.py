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
            interventions_dicts = [i.to_dict() for i in data.interventions]
            admin_dicts = [a.to_dict() for a in data.administrations]
            
            # Nest administrations inside their parent StudyIntervention (USDM v4.0)
            self._nest_administrations(interventions_dicts, admin_dicts)
            
            study_version["studyInterventions"] = interventions_dicts
            study_version["administrableProducts"] = [p.to_dict() for p in data.products]
            # Keep root-level copy for post-processing linkage (H8)
            combined["administrations"] = admin_dicts
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
                    admin_list = intv['administrations']
                    si_list = study_version.get('studyInterventions', [])
                    self._nest_administrations(si_list, admin_list)
                    combined["administrations"] = admin_list
                if intv.get('substances'):
                    combined["substances"] = intv['substances']
                if intv.get('medicalDevices'):
                    study_version["medicalDevices"] = intv['medicalDevices']
    
    @staticmethod
    def _nest_administrations(interventions: list, administrations: list) -> None:
        """Nest Administration entities inside their parent StudyIntervention.
        
        USDM v4.0: StudyIntervention.administrations[] is the correct path.
        Uses administrationIds linkage from the extractor, then falls back to
        name-based matching (intervention name appears in administration name).
        """
        if not interventions or not administrations:
            return
        
        admin_by_id = {a.get('id'): a for a in administrations}
        assigned = set()
        
        # Pass 1: Use administrationIds linkage
        for intv in interventions:
            admin_ids = intv.pop('administrationIds', []) or []
            intv.pop('productIds', None)  # Non-USDM property, remove
            nested = []
            for aid in admin_ids:
                admin = admin_by_id.get(aid)
                if admin:
                    nested.append(admin)
                    assigned.add(aid)
            if nested:
                intv['administrations'] = nested
        
        # Pass 2: Name-based matching for unassigned administrations
        for admin in administrations:
            if admin.get('id') in assigned:
                continue
            admin_name = (admin.get('name') or '').lower()
            for intv in interventions:
                intv_name = (intv.get('name') or '').lower()
                if intv_name and intv_name in admin_name:
                    intv.setdefault('administrations', []).append(admin)
                    assigned.add(admin.get('id'))
                    break
    
    def _fix_dose_form_codes(self, products: list) -> list:
        """Ensure administrableDoseForm is a proper AliasCode per USDM v4.0."""
        fixed = []
        for p in products:
            if isinstance(p, dict):
                dose_form = p.get('administrableDoseForm', {})
                if dose_form and dose_form.get('instanceType') != 'AliasCode':
                    # Legacy Code format → convert to AliasCode
                    if 'code' in dose_form:
                        p = dict(p)
                        p['administrableDoseForm'] = {
                            'id': dose_form.get('id', str(uuid.uuid4())),
                            'standardCode': {
                                'id': str(uuid.uuid4()),
                                'code': dose_form.get('code', ''),
                                'codeSystem': dose_form.get('codeSystem', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl'),
                                'codeSystemVersion': dose_form.get('codeSystemVersion', '25.01d'),
                                'decode': dose_form.get('decode', ''),
                                'instanceType': 'Code',
                            },
                            'instanceType': 'AliasCode',
                        }
            fixed.append(p)
        return fixed


# Register the phase
register_phase(InterventionsPhase())
