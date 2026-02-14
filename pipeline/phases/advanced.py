"""Advanced entities extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext
import logging

logger = logging.getLogger(__name__)


def _build_advanced_context(
    objectives: list = None,
    endpoints: list = None,
    criteria: list = None,
    interventions: list = None,
) -> str:
    """Build a compact upstream context summary for LLM grounding."""
    parts = []
    if objectives:
        names = []
        for o in objectives:
            text = o.get('text', '') or o.get('description', '') or o.get('name', '')
            level = ''
            if isinstance(o.get('level'), dict):
                level = o['level'].get('decode', '')
            if text:
                names.append(f"  - [{level}] {text[:120]}" if level else f"  - {text[:120]}")
        if names:
            parts.append(f"Objectives:\n" + '\n'.join(names[:10]))
    if endpoints:
        names = []
        for e in endpoints:
            text = e.get('text', '') or e.get('description', '') or e.get('name', '')
            if text:
                names.append(f"  - {text[:100]}")
        if names:
            parts.append(f"Endpoints:\n" + '\n'.join(names[:10]))
    if criteria:
        inc = [c for c in criteria if c.get('category', {}).get('decode', '').lower() == 'inclusion']
        exc = [c for c in criteria if c.get('category', {}).get('decode', '').lower() == 'exclusion']
        if inc:
            parts.append(f"Inclusion Criteria: {len(inc)} criteria extracted")
        if exc:
            parts.append(f"Exclusion Criteria: {len(exc)} criteria extracted")
    if interventions:
        names = []
        for i in interventions:
            name = i.get('name', '') or i.get('label', '')
            if name:
                names.append(f"  - {name}")
        if names:
            parts.append(f"Interventions:\n" + '\n'.join(names[:10]))
    return '\n'.join(parts) if parts else ''


class AdvancedPhase(BasePhase):
    """Extract amendments, geographic scope, and countries."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Advanced",
            display_name="Advanced Entities",
            phase_number=8,
            output_filename="8_advanced_entities.json",
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.objectives:
            params['existing_objectives'] = context.objectives
        if context.endpoints:
            params['existing_endpoints'] = context.endpoints
        if context.inclusion_criteria or context.exclusion_criteria:
            params['existing_criteria'] = (
                context.inclusion_criteria + context.exclusion_criteria
            )
        if context.interventions:
            params['existing_interventions'] = context.interventions
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        existing_objectives: Optional[list] = None,
        existing_endpoints: Optional[list] = None,
        existing_criteria: Optional[list] = None,
        existing_interventions: Optional[list] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.advanced import extract_advanced_entities
        
        upstream_context = _build_advanced_context(
            existing_objectives, existing_endpoints,
            existing_criteria, existing_interventions,
        )
        
        result = extract_advanced_entities(
            pdf_path, model_name=model,
            upstream_context=upstream_context,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_advanced_confidence
        if result.data:
            conf = calculate_advanced_confidence(result.data)
            return conf.overall
        return None
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add advanced entities to study_version and combined."""
        advanced_added = False
        
        if result.success and result.data:
            data = result.data
            if data.amendments:
                study_version["amendments"] = [a.to_dict() for a in data.amendments]
            if data.geographic_scope:
                combined["geographicScope"] = data.geographic_scope.to_dict()
            if data.countries:
                combined["countries"] = [c.to_dict() for c in data.countries]
            advanced_added = True
        
        # Fallback to previously extracted advanced entities
        if not advanced_added and previous_extractions.get('advanced'):
            prev = previous_extractions['advanced']
            if prev.get('advanced'):
                adv = prev['advanced']
                if adv.get('studyAmendments'):
                    study_version["amendments"] = adv['studyAmendments']
                elif adv.get('amendments'):
                    study_version["amendments"] = adv['amendments']
                if adv.get('geographicScope'):
                    combined["geographicScope"] = adv['geographicScope']
                if adv.get('countries'):
                    combined["countries"] = adv['countries']


# Register the phase
register_phase(AdvancedPhase())
