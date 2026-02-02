"""Study Design extraction phase."""

from typing import Optional
import uuid
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class StudyDesignPhase(BasePhase):
    """Extract study design structure (arms, cohorts, cells, elements, blinding)."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="StudyDesign",
            display_name="Study Design",
            phase_number=4,
            output_filename="5_study_design.json",
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.has_epochs():
            params['existing_epochs'] = context.epochs
        if context.has_arms():
            params['existing_arms'] = context.arms
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        existing_epochs: Optional[list] = None,
        existing_arms: Optional[list] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.studydesign import extract_study_design
        
        result = extract_study_design(
            pdf_path,
            model_name=model,
            existing_epochs=existing_epochs,
            existing_arms=existing_arms,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_studydesign_confidence
        if result.data:
            conf = calculate_studydesign_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_studydesign(result.data)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add study design structure to study_design."""
        studydesign_added = False
        
        if result.success and result.data:
            sd = result.data
            if sd.study_design:
                if sd.study_design.blinding_schema:
                    study_design["blindingSchema"] = {"code": sd.study_design.blinding_schema.value}
                if sd.study_design.randomization_type:
                    study_design["randomizationType"] = {"code": sd.study_design.randomization_type.value}
            study_design["arms"] = [a.to_dict() for a in sd.arms]
            study_design["studyCohorts"] = [c.to_dict() for c in sd.cohorts]
            study_design["studyCells"] = [c.to_dict() for c in sd.cells]
            study_design["studyElements"] = [e.to_dict() for e in sd.elements]
            
            # Create Masking entities from blinding data
            if sd.study_design and sd.study_design.blinding_schema:
                masking_entities = self._create_masking_entities(
                    sd.study_design.blinding_schema.value,
                    sd.study_design.masked_roles if sd.study_design.masked_roles else []
                )
                study_design["maskingRoles"] = masking_entities
            studydesign_added = True
        
        # Fallback to previously extracted study design
        if not studydesign_added and previous_extractions.get('studydesign'):
            prev = previous_extractions['studydesign']
            if prev.get('studyDesign'):
                sd = prev['studyDesign']
                if sd.get('blindingSchema'):
                    study_design["blindingSchema"] = sd['blindingSchema']
                if sd.get('randomizationType'):
                    study_design["randomizationType"] = sd['randomizationType']
                if sd.get('arms'):
                    study_design["arms"] = sd['arms']
                if sd.get('cohorts'):
                    study_design["studyCohorts"] = sd['cohorts']
                if sd.get('cells'):
                    study_design["studyCells"] = sd['cells']
                
                # Create Masking entities from fallback blinding data
                if sd.get('blindingSchema'):
                    blinding_code = sd['blindingSchema'].get('code', '')
                    masked_roles = sd.get('maskedRoles', [])
                    masking_entities = self._create_masking_entities(blinding_code, masked_roles)
                    study_design["maskingRoles"] = masking_entities
    
    def _create_masking_entities(self, blinding_value: str, masked_roles: list) -> list:
        """Create Masking entities from blinding schema."""
        masking_entities = []
        is_masked = blinding_value and 'Open' not in blinding_value
        
        if masked_roles:
            for i, role in enumerate(masked_roles):
                masking_entities.append({
                    "id": f"mask_{i+1}",
                    "text": f"{role} is masked in this {blinding_value} study",
                    "isMasked": True,
                    "instanceType": "Masking"
                })
        elif is_masked:
            masking_entities.append({
                "id": "mask_1",
                "text": f"This is a {blinding_value} study",
                "isMasked": True,
                "instanceType": "Masking"
            })
        else:
            masking_entities.append({
                "id": "mask_1",
                "text": "This is an Open Label study with no masking",
                "isMasked": False,
                "instanceType": "Masking"
            })
        
        return masking_entities


# Register the phase
register_phase(StudyDesignPhase())
