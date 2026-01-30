"""Narrative structure extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


class NarrativePhase(BasePhase):
    """Extract narrative structure, sections, and abbreviations."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Narrative",
            display_name="Narrative Structure",
            phase_number=7,
            output_filename="7_narrative_structure.json",
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
        from extraction.narrative import extract_narrative_structure
        
        result = extract_narrative_structure(pdf_path, model_name=model)
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_narrative_confidence
        if result.data:
            conf = calculate_narrative_confidence(result.data)
            return conf.overall
        return None
    
    def save_result(self, result: PhaseResult, output_path: str) -> None:
        from extraction.narrative.extractor import save_narrative_result
        
        class ResultWrapper:
            def __init__(self, success, data, error=None):
                self.success = success
                self.data = data
                self.error = error
        
        wrapper = ResultWrapper(result.success, result.data, result.error)
        save_narrative_result(wrapper, output_path)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add narrative content to study_version."""
        narrative_added = False
        
        if result.success and result.data:
            data = result.data
            study_version["narrativeContents"] = [s.to_dict() for s in data.sections]
            study_version["narrativeContentItems"] = [i.to_dict() for i in data.items]
            study_version["abbreviations"] = [a.to_dict() for a in data.abbreviations]
            if data.document:
                combined["studyDefinitionDocument"] = data.document.to_dict()
            narrative_added = True
        
        # Fallback to previously extracted narrative
        if not narrative_added and previous_extractions.get('narrative'):
            prev = previous_extractions['narrative']
            if prev.get('narrative'):
                narr = prev['narrative']
                if narr.get('narrativeContents'):
                    study_version["narrativeContents"] = narr['narrativeContents']
                if narr.get('narrativeContentItems'):
                    study_version["narrativeContentItems"] = narr['narrativeContentItems']
                if narr.get('abbreviations'):
                    study_version["abbreviations"] = narr['abbreviations']
                if narr.get('studyDefinitionDocument'):
                    combined["studyDefinitionDocument"] = narr['studyDefinitionDocument']


# Register the phase
register_phase(NarrativePhase())
