"""Procedures & Devices extraction phase."""

from typing import Optional
import logging
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class ProceduresPhase(BasePhase):
    """Extract procedures and medical devices."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Procedures",
            display_name="Procedures & Devices",
            phase_number=10,
            output_filename="9_procedures_devices.json",
            optional=True,  # Module may not exist
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
        from extraction.procedures import extract_procedures_devices
        
        result = extract_procedures_devices(pdf_path, model=model, output_dir=output_dir)
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_procedures(result.data.to_dict())
    
    def run(self, *args, **kwargs) -> PhaseResult:
        """Override run to log procedure count on success."""
        result = super().run(*args, **kwargs)
        if result.success and result.data:
            data_dict = result.data.to_dict()
            count = data_dict.get('summary', {}).get('procedureCount', 0)
            logger.info(f"    Procedures: {count}")
        return result
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add procedures to studyDesign and link to activities where possible."""
        if not (result.success and result.data):
            return
        
        data_dict = result.data.to_dict()
        procedures_list = data_dict.get('procedures', [])
        
        # Always add procedures to studyDesign.procedures first
        if procedures_list:
            study_design['procedures'] = procedures_list
            logger.info(f"  Added {len(procedures_list)} procedures to studyDesign")
        
        # Link procedures to activities via definedProcedures (optional enrichment)
        if procedures_list and study_design.get('activities'):
            # Build name-to-procedure mapping for matching
            proc_by_name = {}
            for proc in procedures_list:
                proc_name = proc.get('name', '').lower()
                if proc_name:
                    proc_by_name[proc_name] = proc
                    # Also add without common suffixes for fuzzy matching
                    for suffix in [' sampling', ' collection', ' test', ' assessment']:
                        if proc_name.endswith(suffix):
                            proc_by_name[proc_name[:-len(suffix)]] = proc
            
            # Match procedures to activities
            procedures_linked = 0
            for activity in study_design['activities']:
                act_name = activity.get('name', '').lower()
                matched_proc_ids = []
                
                # Direct match
                if act_name in proc_by_name:
                    matched_proc_ids.append(proc_by_name[act_name].get('id'))
                
                # Partial match
                for proc_name, proc in proc_by_name.items():
                    proc_id = proc.get('id')
                    if proc_id not in matched_proc_ids:
                        if proc_name in act_name or act_name in proc_name:
                            matched_proc_ids.append(proc_id)
                
                if matched_proc_ids:
                    # Link via procedureIds (reference by ID, not embedding)
                    activity['definedProcedures'] = [
                        {"procedureId": pid} for pid in matched_proc_ids if pid
                    ]
                    procedures_linked += len(matched_proc_ids)
            
            if procedures_linked > 0:
                logger.info(f"  Linked {procedures_linked} procedures to activities")
        
        # Medical devices go to studyVersion per USDM v4.0 dataStructure.yml
        devices_list = data_dict.get('medicalDevices', []) or data_dict.get('devices', [])
        if devices_list:
            study_version["medicalDevices"] = devices_list
            logger.info(f"  Added {len(devices_list)} medical devices")
        
        # Product-related data stored temporarily for later processing
        if data_dict.get('ingredients'):
            combined["_temp_ingredients"] = data_dict['ingredients']
        if data_dict.get('strengths'):
            combined["_temp_strengths"] = data_dict['strengths']


# Register the phase
register_phase(ProceduresPhase())
