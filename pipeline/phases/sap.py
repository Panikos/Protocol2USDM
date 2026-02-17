"""SAP (Statistical Analysis Plan) extraction phase.

Wraps the conditional SAP extractor as a proper pipeline phase,
enabling parallel execution, dependency management, and combine integration.
"""

import json
import os
import logging
from typing import Optional

from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class SAPPhase(BasePhase):
    """Extract analysis populations, statistical methods, and sample size from SAP."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="SAP",
            display_name="SAP Analysis Populations",
            phase_number=14,
            output_filename="14_sap_extraction.json",
            requires_pdf=False,
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
        sap_path = kwargs.get('sap_path')
        if not sap_path:
            return PhaseResult(success=False, error="No SAP file provided")
        
        from extraction.conditional import extract_from_sap
        
        result = extract_from_sap(sap_path, model=model, output_dir=output_dir)
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') and result.error else None,
        )
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add SAP data to study design: populations, extensions, ARS."""
        sap_dict = None
        
        if result.success and result.data:
            sap_dict = result.data.to_dict() if hasattr(result.data, 'to_dict') else result.data
        elif previous_extractions.get('sap'):
            prev = previous_extractions['sap']
            sap_dict = prev.get('sapData', prev)
        
        if not sap_dict:
            return
        
        # Analysis populations → studyDesign
        populations = sap_dict.get('analysisPopulations', [])
        if populations:
            # B5: Populate empty description from text/populationDescription
            for pop in populations:
                if not pop.get('description'):
                    pop['description'] = (
                        pop.get('populationDescription')
                        or pop.get('text')
                        or ''
                    )
            study_design['analysisPopulations'] = populations
            logger.info(f"  Added {len(populations)} analysis populations to studyDesign")
        
        # SAP elements → extension attributes (data-driven)
        from pipeline.integrations import SAP_EXTENSION_TYPES as _SAP_EXTENSION_TYPES
        extensions = study_design.setdefault('extensionAttributes', [])
        ext_counts = []
        for dict_key, url_suffix, label in _SAP_EXTENSION_TYPES:
            items = sap_dict.get(dict_key, [])
            if items:
                extensions.append({
                    "id": f"ext_sap_{dict_key}",
                    "url": f"https://protocol2usdm.io/extensions/x-sap-{url_suffix}",
                    "valueString": json.dumps(items),
                    "instanceType": "ExtensionAttribute"
                })
                ext_counts.append(f"{len(items)} {label}")
        
        if ext_counts:
            logger.info(f"  Added SAP extensions: {', '.join(ext_counts)}")
        
        # Generate CDISC ARS output
        output_dir = combined.get('_output_dir', '')
        if output_dir:
            try:
                from extraction.conditional.ars_generator import generate_ars_from_sap
                study_name = study_version.get('titles', [{}])[0].get('text', 'Study')
                ars_output_path = os.path.join(output_dir, "ars_reporting_event.json")
                ars_data = generate_ars_from_sap(sap_dict, study_name, ars_output_path)
                
                re_data = ars_data.get('reportingEvent', {})
                ars_counts = [
                    f"{len(re_data.get('analysisSets', []))} analysis sets",
                    f"{len(re_data.get('analysisMethods', []))} methods",
                    f"{len(re_data.get('analyses', []))} analyses",
                ]
                logger.info(f"  ✓ Generated CDISC ARS: {', '.join(ars_counts)}")
            except Exception as e:
                logger.warning(f"  ⚠ ARS generation failed: {e}")


# Register the phase
register_phase(SAPPhase())
