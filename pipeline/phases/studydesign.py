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
                    study_design["blindingSchema"] = self._build_alias_code(
                        sd.study_design.blinding_schema.value, "blindingSchema"
                    )
                if sd.study_design.randomization_type and sd.study_design.randomization_type.value:
                    from core.terminology_codes import RANDOMIZATION_CODES
                    rand_val = sd.study_design.randomization_type.value.lower()
                    rand_code_info = RANDOMIZATION_CODES.get(rand_val, RANDOMIZATION_CODES.get('non-randomized', {}))
                    rand_code = {
                        "id": str(uuid.uuid4()),
                        "code": rand_code_info.get('code', ''),
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": rand_code_info.get('decode', sd.study_design.randomization_type.value),
                        "instanceType": "Code",
                    }
                    study_design.setdefault("subTypes", []).append(rand_code)
                # C3: Design rationale
                if sd.study_design.rationale:
                    study_design["rationale"] = sd.study_design.rationale
                # H4: Design characteristics
                if sd.study_design.characteristics:
                    sd_dict = sd.study_design.to_dict()
                    if sd_dict.get("characteristics"):
                        study_design["characteristics"] = sd_dict["characteristics"]
            study_design["arms"] = [a.to_dict() for a in sd.arms]
            study_design["studyCohorts"] = [c.to_dict() for c in sd.cohorts]
            study_design["studyCells"] = [c.to_dict() for c in sd.cells]
            study_design["studyElements"] = [e.to_dict() for e in sd.elements]
            
            # Masking entities are now derived from blindingSchema in the UI;
            # USDM v4.0 places Masking on StudyRole, not StudyDesign
            studydesign_added = True
        
        # Fallback to previously extracted study design
        if not studydesign_added and previous_extractions.get('studydesign'):
            prev = previous_extractions['studydesign']
            if prev.get('studyDesign'):
                sd = prev['studyDesign']
                if sd.get('blindingSchema'):
                    bs = sd['blindingSchema']
                    # Wrap flat Code in AliasCode if needed
                    if isinstance(bs, dict) and 'standardCode' not in bs:
                        study_design["blindingSchema"] = self._build_alias_code(
                            bs.get('decode') or bs.get('code', ''), "blindingSchema"
                        )
                    else:
                        study_design["blindingSchema"] = bs
                else:
                    # Infer blinding from rationale text if not explicitly extracted
                    from extraction.studydesign.extractor import _infer_blinding_from_text
                    inferred = _infer_blinding_from_text(sd)
                    if inferred and inferred.value:
                        study_design["blindingSchema"] = self._build_alias_code(
                            inferred.value, "blindingSchema"
                        )
                if sd.get('randomizationType'):
                    from core.terminology_codes import RANDOMIZATION_CODES
                    rt = sd['randomizationType']
                    rand_val = (rt.get('decode') or rt.get('code', '')).lower()
                    rand_code_info = RANDOMIZATION_CODES.get(rand_val, RANDOMIZATION_CODES.get('non-randomized', {}))
                    rand_code = {
                        "id": str(uuid.uuid4()),
                        "code": rand_code_info.get('code', ''),
                        "codeSystem": "http://www.cdisc.org",
                        "codeSystemVersion": "2024-09-27",
                        "decode": rand_code_info.get('decode', rt.get('decode', '')),
                        "instanceType": "Code",
                    }
                    study_design.setdefault("subTypes", []).append(rand_code)
                # C3: Design rationale (fallback path)
                if sd.get('rationale'):
                    study_design["rationale"] = sd['rationale']
                # H4: Design characteristics (fallback path)
                if sd.get('characteristics'):
                    study_design["characteristics"] = sd['characteristics']
                if sd.get('arms'):
                    study_design["arms"] = sd['arms']
                if sd.get('cohorts'):
                    study_design["studyCohorts"] = sd['cohorts']
                if sd.get('cells'):
                    study_design["studyCells"] = sd['cells']
                
                # Create Masking entities from fallback blinding data
                if sd.get('blindingSchema'):
                    bs = sd['blindingSchema']
                    if isinstance(bs, dict) and 'standardCode' not in bs:
                        study_design["blindingSchema"] = self._build_alias_code(
                            bs.get('decode') or bs.get('code', ''), "blindingSchema"
                        )
                    else:
                        study_design["blindingSchema"] = bs
    
    @staticmethod
    def _build_alias_code(decode_value: str, attribute: str = "blindingSchema") -> dict:
        """Build USDM AliasCode structure for blindingSchema.
        
        AliasCode = { id, standardCode: Code, instanceType: 'AliasCode' }
        """
        from core.code_registry import registry as code_registry
        code_obj = code_registry.lookup(attribute, decode_value)
        if code_obj:
            c_code = code_obj.code
        else:
            # Fallback C-code lookup
            _BLINDING_CODES = {
                "open label": "C49659", "single blind": "C28233",
                "double blind": "C15228", "triple blind": "C66959",
            }
            c_code = _BLINDING_CODES.get(decode_value.lower().replace(" study", ""), "")
        
        return {
            "id": f"blind_1",
            "instanceType": "AliasCode",
            "standardCode": {
                "id": f"code_blind_1",
                "code": c_code,
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": decode_value,
                "instanceType": "Code",
            },
        }


# Register the phase
register_phase(StudyDesignPhase())
