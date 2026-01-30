"""Amendment details extraction phase."""

from typing import Optional
import logging
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class AmendmentDetailsPhase(BasePhase):
    """Extract amendment details, impacts, and changes."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="AmendmentDetails",
            display_name="Amendment Details",
            phase_number=13,
            output_filename="14_amendment_details.json",
            optional=True,
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
        from extraction.amendments import extract_amendment_details
        
        result = extract_amendment_details(pdf_path, model=model, output_dir=output_dir)
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def run(self, *args, **kwargs) -> PhaseResult:
        """Override run to log counts on success."""
        result = super().run(*args, **kwargs)
        if result.success and result.data:
            summary = result.data.to_dict().get('summary', {})
            impacts = summary.get('impactCount', 0)
            changes = summary.get('changeCount', 0)
            logger.info(f"    Impacts: {impacts}, Changes: {changes}")
        return result
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add amendment details to combined."""
        if not (result.success and result.data):
            return
        
        data_dict = result.data.to_dict()
        
        if data_dict.get('studyAmendmentImpacts'):
            combined["studyAmendmentImpacts"] = data_dict['studyAmendmentImpacts']
        if data_dict.get('studyAmendmentReasons'):
            combined["studyAmendmentReasons"] = data_dict['studyAmendmentReasons']
        if data_dict.get('studyChanges'):
            combined["studyChanges"] = data_dict['studyChanges']


# Register the phase
register_phase(AmendmentDetailsPhase())
