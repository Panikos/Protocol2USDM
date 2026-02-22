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
            phase_number=13,
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
        
        # Pass endpoint context from objectives phase for method-to-endpoint linkage
        endpoints_context = context.endpoints if context.endpoints else None
        
        # Pass analysis approach for approach-aware extraction gating
        analysis_approach = kwargs.get('analysis_approach')
        
        result = extract_from_sap(
            sap_path, model=model, output_dir=output_dir,
            endpoints_context=endpoints_context,
            analysis_approach=analysis_approach,
        )
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
        
        # Build AnalysisSpecification entities — traceability bridge
        analysis_specs = _build_analysis_specifications(
            sap_dict, study_design, study_version,
        )
        if analysis_specs:
            extensions.append({
                "id": "ext_sap_analysisSpecifications",
                "url": "https://protocol2usdm.io/extensions/x-sap-analysis-specifications",
                "valueString": json.dumps(analysis_specs),
                "instanceType": "ExtensionAttribute",
            })
            logger.info(f"  Built {len(analysis_specs)} analysis specifications (endpoint→method traceability)")
        
        # Generate CDISC ARS output (with endpoint IDs for linkage)
        output_dir = combined.get('_output_dir', '')
        if output_dir:
            try:
                from extraction.conditional.ars_generator import generate_ars_from_sap
                study_name = study_version.get('titles', [{}])[0].get('text', 'Study')
                ars_output_path = os.path.join(output_dir, "ars_reporting_event.json")
                # Pass endpoint map for ARS→USDM endpoint linkage
                endpoint_map = _build_endpoint_map(study_design)
                ars_data = generate_ars_from_sap(
                    sap_dict, study_name, ars_output_path,
                    endpoint_map=endpoint_map,
                )
                
                re_data = ars_data.get('reportingEvent', {})
                ars_counts = [
                    f"{len(re_data.get('analysisSets', []))} analysis sets",
                    f"{len(re_data.get('analysisMethods', []))} methods",
                    f"{len(re_data.get('analyses', []))} analyses",
                ]
                logger.info(f"  ✓ Generated CDISC ARS: {', '.join(ars_counts)}")
            except Exception as e:
                logger.warning(f"  ⚠ ARS generation failed: {e}")


def _build_endpoint_map(study_design: dict) -> dict:
    """Build a lookup map from endpoint names/text to endpoint IDs.
    
    Used by ARS generator to link Analysis objects to USDM endpoint IDs.
    Returns: {normalized_name: endpoint_id}
    """
    ep_map = {}
    for obj in study_design.get('objectives', []):
        for ep in obj.get('endpoints', []):
            ep_id = ep.get('id', '')
            ep_text = ep.get('text', ep.get('endpointText', ep.get('name', '')))
            if ep_text and ep_id:
                ep_map[ep_text.strip().lower()] = ep_id
                # Also index by first N words for fuzzy matching
                words = ep_text.strip().split()
                if len(words) > 3:
                    ep_map[' '.join(words[:5]).lower()] = ep_id
    return ep_map


def _build_analysis_specifications(
    sap_dict: dict,
    study_design: dict,
    study_version: dict,
) -> list:
    """Build AnalysisSpecification entities by reconciling SAP methods with protocol endpoints.
    
    Creates the traceability bridge: Endpoint → Method → Population → Estimand.
    Uses word-overlap matching to link SAP method endpoint names to USDM endpoint IDs.
    """
    import uuid as _uuid
    
    methods = sap_dict.get('statisticalMethods', [])
    populations = sap_dict.get('analysisPopulations', [])
    if not methods:
        return []
    
    # Build endpoint lookup from protocol
    ep_map = _build_endpoint_map(study_design)
    
    # Build population lookup by name
    pop_map = {}
    for pop in populations:
        if isinstance(pop, dict):
            name = (pop.get('name') or pop.get('label') or '').strip().lower()
            if name:
                pop_map[name] = pop.get('id', '')
    
    # Build estimand lookup by endpoint name (for confirmatory studies)
    est_map = {}  # endpoint_name_lower → estimand_id
    for est in study_design.get('estimands', []):
        if isinstance(est, dict):
            # Estimands reference endpoints via endpointId or endpoint text
            ep_text = ''
            ep_ref = est.get('variableOfInterest', {})
            if isinstance(ep_ref, dict):
                ep_text = ep_ref.get('text', ep_ref.get('name', ''))
            elif isinstance(ep_ref, str):
                ep_text = ep_ref
            if ep_text:
                est_map[ep_text.strip().lower()] = est.get('id', '')
    
    specs = []
    for method in methods:
        if not isinstance(method, dict):
            continue
        
        method_id = method.get('id', '')
        method_name = method.get('name', '')
        endpoint_name = method.get('endpointName', '')
        endpoint_id = method.get('endpointId')  # May come from Pass 2 directly
        pop_name = method.get('populationName', '')
        analysis_type = method.get('arsReason', 'PRIMARY').lower()
        missing_data = method.get('missingDataMethod', '')
        model_spec = method.get('modelSpecification', '')
        if isinstance(model_spec, dict):
            model_spec = json.dumps(model_spec)
        
        # Map analysis type to standard values
        type_map = {'primary': 'primary', 'sensitivity': 'sensitivity',
                    'exploratory': 'exploratory', 'supportive': 'sensitivity'}
        analysis_type = type_map.get(analysis_type, 'primary')
        
        # Resolve endpoint ID via name matching if not already set
        if not endpoint_id and endpoint_name:
            ep_key = endpoint_name.strip().lower()
            endpoint_id = ep_map.get(ep_key)
            # Fuzzy fallback: word overlap
            if not endpoint_id:
                ep_words = set(ep_key.split())
                best_score, best_id = 0.0, None
                for stored_name, stored_id in ep_map.items():
                    stored_words = set(stored_name.split())
                    if ep_words and stored_words:
                        overlap = len(ep_words & stored_words) / max(len(ep_words), len(stored_words))
                        if overlap > best_score and overlap > 0.4:
                            best_score = overlap
                            best_id = stored_id
                if best_id:
                    endpoint_id = best_id
        
        # Resolve population ID
        pop_id = None
        if pop_name:
            pop_id = pop_map.get(pop_name.strip().lower())
        
        # Resolve estimand ID (for confirmatory studies)
        estimand_id = None
        if endpoint_name:
            estimand_id = est_map.get(endpoint_name.strip().lower())
        
        spec = {
            "id": str(_uuid.uuid4()),
            "endpointId": endpoint_id,
            "endpointName": endpoint_name or None,
            "methodId": method_id or None,
            "methodName": method_name or None,
            "populationId": pop_id,
            "populationName": pop_name or None,
            "estimandId": estimand_id,
            "analysisType": analysis_type,
            "missingDataStrategy": missing_data or None,
            "modelSpecification": model_spec or None,
            "instanceType": "AnalysisSpecification",
        }
        # Remove None values for clean output
        spec = {k: v for k, v in spec.items() if v is not None}
        specs.append(spec)
    
    return specs


# Register the phase
register_phase(SAPPhase())
