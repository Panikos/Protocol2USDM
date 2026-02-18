"""Document structure extraction phase."""

from typing import Optional
import logging
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class DocStructurePhase(BasePhase):
    """Extract document structure, references, and annotations."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="DocStructure",
            display_name="Document Structure",
            phase_number=10,
            output_filename="13_document_structure.json",
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
        from extraction.document_structure import extract_document_structure
        
        # Read narrative contents from pipeline context (populated by narrative phase)
        narrative_contents = context.narrative_contents if context.narrative_contents else None
        
        result = extract_document_structure(
            pdf_path,
            model=model,
            output_dir=output_dir,
            narrative_contents=narrative_contents,
        )
        
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
            refs = summary.get('referenceCount', 0)
            annotations = summary.get('annotationCount', 0)
            xrefs = summary.get('inlineReferenceCount', 0)
            figs = summary.get('figureCount', 0)
            logger.info(
                f"    References: {refs}, Annotations: {annotations}, "
                f"Cross-refs: {xrefs}, Figures: {figs}"
            )
        return result
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add document structure to combined."""
        if not (result.success and result.data):
            return
        
        data_dict = result.data.to_dict()
        
        if data_dict.get('documentContentReferences'):
            combined["documentContentReferences"] = data_dict['documentContentReferences']
        if data_dict.get('commentAnnotations'):
            combined["commentAnnotations"] = data_dict['commentAnnotations']
        if data_dict.get('studyDefinitionDocumentVersions'):
            combined["studyDefinitionDocumentVersions"] = data_dict['studyDefinitionDocumentVersions']
        if data_dict.get('inlineCrossReferences'):
            combined["inlineCrossReferences"] = data_dict['inlineCrossReferences']
        if data_dict.get('protocolFigures'):
            combined["protocolFigures"] = data_dict['protocolFigures']
            # Also store as extension attribute on study version for USDM compatibility
            import json
            ext = {
                "id": "ext-protocol-figures",
                "url": "https://protocol2usdm.io/extensions/x-protocol-figures",
                "valueString": json.dumps(data_dict['protocolFigures']),
                "instanceType": "ExtensionAttribute",
            }
            study_version.setdefault('extensionAttributes', []).append(ext)


# Register the phase
register_phase(DocStructurePhase())
