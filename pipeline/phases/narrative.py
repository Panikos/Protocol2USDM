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
        
        # Store narrative contents in context for downstream phases (e.g. docstructure)
        if result.success and result.data and result.data.sections:
            context.narrative_contents = [s.to_dict() for s in result.data.sections]
        
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
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add narrative content to study_version."""
        import logging
        _logger = logging.getLogger(__name__)
        narrative_added = False
        
        if result.success and result.data:
            data = result.data
            study_version["narrativeContents"] = [s.to_dict() for s in data.sections]
            study_version["narrativeContentItems"] = [i.to_dict() for i in data.items]
            study_version["abbreviations"] = [a.to_dict() for a in data.abbreviations]
            if data.document:
                combined["studyDefinitionDocument"] = data.document.to_dict()
            narrative_added = True
            
            # Run M11 section mapping
            try:
                from extraction.narrative.m11_mapper import map_sections_to_m11, build_m11_narrative, M11_TEMPLATE
                
                # Build section dicts for the mapper
                sec_dicts = []
                for s in data.sections:
                    sec_dicts.append({
                        'number': s.section_number or '',
                        'title': s.section_title or s.name or '',
                        'type': s.section_type.value if s.section_type else 'Other',
                    })
                
                # Build section texts dict
                sec_texts = {}
                for s in data.sections:
                    if s.text and s.text != s.name:
                        sec_texts[s.section_number or ''] = s.text
                
                mapping = map_sections_to_m11(sec_dicts, sec_texts)
                m11_narrative = build_m11_narrative(sec_dicts, sec_texts, mapping)
                
                # Store M11 mapping as extension data
                combined["m11Mapping"] = {
                    "coverage": f"{mapping.m11_covered}/{mapping.m11_total}",
                    "requiredCoverage": f"{mapping.m11_required_covered}/{mapping.m11_required_total}",
                    "unmappedSections": mapping.unmapped,
                    "sections": m11_narrative,
                }
                
                _logger.info(
                    f"M11 mapping: {mapping.m11_covered}/{mapping.m11_total} covered "
                    f"({mapping.m11_required_covered}/{mapping.m11_required_total} required)"
                )
            except Exception as e:
                _logger.warning(f"M11 mapping failed (non-fatal): {e}")
        
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
