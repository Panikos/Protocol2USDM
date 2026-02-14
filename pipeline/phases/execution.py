"""Execution model extraction phase."""

from typing import Optional
import logging
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class ExecutionPhase(BasePhase):
    """Extract execution model (time anchors, repetitions, crossover, etc.)."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Execution",
            display_name="Execution Model",
            phase_number=14,
            output_filename="11_execution_model.json",
            requires_soa=True,
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
        from extraction.execution import extract_execution_model
        
        result = extract_execution_model(
            pdf_path,
            model=model,
            output_dir=output_dir,
            soa_data=soa_data,
            pipeline_context=context,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def run(self, *args, **kwargs) -> PhaseResult:
        """Override run to log detailed counts on success."""
        result = super().run(*args, **kwargs)
        if result.success and result.data:
            data = result.data
            anchors = len(data.time_anchors)
            reps = len(data.repetitions)
            exec_types = len(data.execution_types)
            traversals = len(data.traversal_constraints)
            footnotes = len(data.footnote_conditions)
            visits = len(data.visit_windows)
            dosing = len(data.dosing_regimens)
            crossover = "Yes" if data.crossover_design and data.crossover_design.is_crossover else "No"
            
            logger.info(f"    Anchors: {anchors}, Repetitions: {reps}, Exec Types: {exec_types}")
            logger.info(f"    Traversals: {traversals}, Footnotes: {footnotes}, Crossover: {crossover}")
            logger.info(f"    Visits: {visits}, Dosing: {dosing}")
        return result
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """
        Enrich USDM with execution model.
        
        Note: This is handled specially by the orchestrator since it needs
        to run AFTER study.versions is assembled. The combine here is a no-op.
        """
        # Execution model enrichment is handled by orchestrator
        # because it requires the full combined structure
        pass
    
    def enrich_usdm(self, combined: dict, result: PhaseResult) -> dict:
        """
        Enrich USDM with execution model semantics.
        
        This is called by the orchestrator after combine_to_full_usdm.
        """
        if not (result.success and result.data):
            return combined
        
        from extraction.execution import enrich_usdm_with_execution_model
        return enrich_usdm_with_execution_model(combined, result.data)


# Register the phase
register_phase(ExecutionPhase())
