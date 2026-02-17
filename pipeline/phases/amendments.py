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
        """Embed amendment details inline per USDM schema (Value relationships)."""
        if not (result.success and result.data):
            return
        
        data_dict = result.data.to_dict()
        
        # Build LLM amendmentId → actual amendment entity ID mapping
        import re
        actual_amendments = study_version.get("amendments", [])
        id_map = {}
        for amend in actual_amendments:
            num = amend.get("number", "")
            amend_id = amend.get("id", "")
            if num and amend_id:
                id_map[f"amend_{num}"] = amend_id
                id_map[f"amendment_{num}"] = amend_id
                id_map[amend_id] = amend_id
        
        if len(actual_amendments) == 1:
            single_id = actual_amendments[0].get("id", "")
            if single_id:
                for key in list(id_map.keys()):
                    id_map[key] = single_id
                id_map["amend_1"] = single_id
        
        def _resolve_amendment_id(old_id):
            """Resolve an amendmentId to actual amendment entity ID."""
            if old_id in id_map:
                return id_map[old_id]
            m = re.search(r'(\d+)', old_id)
            if m:
                num = m.group(1)
                for amend in actual_amendments:
                    if amend.get("number", "") == num:
                        return amend.get("id", old_id)
            return old_id
        
        # Group detail entities by parent amendment ID
        # Per USDM schema: impacts, changes, secondaryReasons are inline Value relationships
        amend_reasons = {}   # amendment_id -> list of reason dicts
        amend_impacts = {}   # amendment_id -> list of impact dicts
        amend_changes = {}   # amendment_id -> list of change dicts
        
        for entity in data_dict.get('studyAmendmentReasons', []):
            resolved_id = _resolve_amendment_id(entity.get("amendmentId", ""))
            entity.pop("amendmentId", None)
            amend_reasons.setdefault(resolved_id, []).append(entity)
        
        for entity in data_dict.get('studyAmendmentImpacts', []):
            resolved_id = _resolve_amendment_id(entity.get("amendmentId", ""))
            entity.pop("amendmentId", None)
            amend_impacts.setdefault(resolved_id, []).append(entity)
        
        for entity in data_dict.get('studyChanges', []):
            resolved_id = _resolve_amendment_id(entity.get("amendmentId", ""))
            entity.pop("amendmentId", None)
            amend_changes.setdefault(resolved_id, []).append(entity)
        
        # Embed inline in parent amendments and remove orphaned reasonIds
        embedded = 0
        for amend in actual_amendments:
            amend_id = amend.get("id", "")
            
            # Embed secondary reasons (first extracted reason → primaryReason if missing)
            reasons = amend_reasons.get(amend_id, [])
            if reasons:
                if not amend.get("primaryReason") or amend.get("primaryReason", {}).get("otherReason") == "Protocol Amendment":
                    amend["primaryReason"] = reasons[0]
                    amend["secondaryReasons"] = reasons[1:] if len(reasons) > 1 else []
                else:
                    amend.setdefault("secondaryReasons", []).extend(reasons)
                embedded += len(reasons)
            
            # Embed impacts
            impacts = amend_impacts.get(amend_id, [])
            if impacts:
                amend.setdefault("impacts", []).extend(impacts)
                embedded += len(impacts)
            
            # Embed changes
            changes = amend_changes.get(amend_id, [])
            if changes:
                amend.setdefault("changes", []).extend(changes)
                embedded += len(changes)
            
            # Ensure required arrays exist (USDM schema requires 'changes')
            amend.setdefault("changes", [])
            amend.setdefault("impacts", [])
            
            # Remove orphaned reasonIds — replaced by inline objects
            amend.pop("reasonIds", None)
        
        if embedded:
            logger.info(f"  ✓ Embedded {embedded} amendment detail entities inline")


# Register the phase
register_phase(AmendmentDetailsPhase())
