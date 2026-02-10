"""Sites extraction phase.

Wraps the conditional sites extractor as a proper pipeline phase,
enabling parallel execution, dependency management, and combine integration.
"""

import logging
from typing import Optional

from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class SitesPhase(BasePhase):
    """Extract study sites and site organizations from sites CSV/Excel."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Sites",
            display_name="Study Sites",
            phase_number=15,
            output_filename="15_sites_extraction.json",
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
        sites_path = kwargs.get('sites_path')
        if not sites_path:
            return PhaseResult(success=False, error="No sites file provided")
        
        from extraction.conditional import extract_from_sites
        
        result = extract_from_sites(sites_path, output_dir=output_dir)
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
        """Add sites data to study design and organizations to study version."""
        sites_dict = None
        
        if result.success and result.data:
            sites_dict = result.data.to_dict() if hasattr(result.data, 'to_dict') else result.data
        elif previous_extractions.get('sites'):
            prev = previous_extractions['sites']
            sites_dict = prev.get('sites', prev)
        
        if not sites_dict:
            return
        
        sites_data = sites_dict.get('studySites', [])
        if sites_data:
            study_design['studySites'] = sites_data
            logger.info(f"  Added {len(sites_data)} study sites to studyDesign")
        
        site_orgs = sites_dict.get('organizations', [])
        if site_orgs:
            existing_orgs = study_version.get('organizations', [])
            existing_ids = {o.get('id') for o in existing_orgs}
            new_orgs = [o for o in site_orgs if o.get('id') not in existing_ids]
            study_version['organizations'] = existing_orgs + new_orgs
            logger.info(f"  Added {len(new_orgs)} site organizations")


# Register the phase
register_phase(SitesPhase())
