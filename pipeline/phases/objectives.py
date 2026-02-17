"""Objectives & Endpoints extraction phase."""

from typing import Optional
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext


# H5: Level-to-purpose defaults for endpoints missing a purpose value
_LEVEL_PURPOSE_DEFAULTS = {
    "primary": "Efficacy",
    "secondary": "Efficacy",
    "exploratory": "Exploratory",
}


def _default_endpoint_purpose(endpoints: list) -> None:
    """Fill empty Endpoint.purpose based on level decode (H5 gap fix)."""
    for ep in endpoints:
        if ep.get("purpose"):
            continue
        level = ep.get("level")
        if isinstance(level, dict):
            decode = (level.get("decode") or "").strip().lower()
        elif isinstance(level, str):
            decode = level.strip().lower()
        else:
            continue
        for key, default in _LEVEL_PURPOSE_DEFAULTS.items():
            if key in decode:
                ep["purpose"] = default
                break


def _nest_endpoints_in_objectives(objectives: list, endpoints: list) -> None:
    """Nest endpoints inside their parent objectives based on endpointIds.
    
    Per USDM v4.0, Objective.endpoints is a Value (inline) relationship.
    Endpoints must be nested inside their parent objective, not at the design level.
    """
    if not endpoints:
        return
    
    # Build endpoint lookup by ID
    ep_by_id = {ep.get("id"): ep for ep in endpoints if ep.get("id")}
    
    # Track which endpoints have been assigned
    assigned = set()
    
    for obj in objectives:
        ep_ids = obj.get("endpointIds", [])
        if not ep_ids:
            continue
        
        nested = []
        for eid in ep_ids:
            ep = ep_by_id.get(eid)
            if ep:
                nested.append(ep)
                assigned.add(eid)
        
        if nested:
            obj["endpoints"] = nested
        # Remove endpointIds — replaced by inline endpoints
        obj.pop("endpointIds", None)
    
    # Assign any unmatched endpoints to the first objective with matching level
    unassigned = [ep for ep in endpoints if ep.get("id") not in assigned]
    if unassigned and objectives:
        for ep in unassigned:
            ep_level = _get_level_key(ep)
            placed = False
            for obj in objectives:
                obj_level = _get_level_key(obj)
                if ep_level and obj_level and ep_level == obj_level:
                    obj.setdefault("endpoints", []).append(ep)
                    placed = True
                    break
            if not placed:
                # Last resort: put in first objective
                objectives[0].setdefault("endpoints", []).append(ep)


def _get_level_key(entity: dict) -> str:
    """Extract level key (primary/secondary/exploratory) from an entity."""
    level = entity.get("level")
    if isinstance(level, dict):
        decode = (level.get("decode") or "").strip().lower()
    elif isinstance(level, str):
        decode = level.strip().lower()
    else:
        return ""
    if "primary" in decode:
        return "primary"
    elif "secondary" in decode:
        return "secondary"
    elif "exploratory" in decode:
        return "exploratory"
    return decode


class ObjectivesPhase(BasePhase):
    """Extract objectives, endpoints, and estimands."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Objectives",
            display_name="Objectives & Endpoints",
            phase_number=3,
            output_filename="4_objectives_endpoints.json",
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.indication:
            params['study_indication'] = context.indication
        if context.phase:
            params['study_phase'] = context.phase
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        study_indication: Optional[str] = None,
        study_phase: Optional[str] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.objectives import extract_objectives_endpoints
        
        result = extract_objectives_endpoints(
            pdf_path,
            model_name=model,
            study_indication=study_indication,
            study_phase=study_phase,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        from extraction.confidence import calculate_objectives_confidence
        if result.data:
            conf = calculate_objectives_confidence(result.data)
            return conf.overall
        return None
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_objectives(result.data)
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add objectives and endpoints to study_design.
        
        Per USDM v4.0, Objective.endpoints is a Value (inline) relationship.
        Endpoints are nested inside their parent objectives, not at the design level.
        """
        objectives_added = False
        
        if result.success and result.data:
            data = result.data
            objectives = [o.to_dict() for o in data.objectives]
            endpoints = [e.to_dict() for e in data.endpoints]
            # H5: Default Endpoint.purpose based on level if empty
            _default_endpoint_purpose(endpoints)
            # Nest endpoints inside their parent objectives
            _nest_endpoints_in_objectives(objectives, endpoints)
            study_design["objectives"] = objectives
            # Keep flat endpoints in _temp for cross-referencing by estimands/post-processing
            combined["_temp_endpoints"] = endpoints
            if data.estimands:
                # Filter out incomplete estimands (ICH E9(R1) requires these fields)
                valid_estimands = []
                for e in data.estimands:
                    e_dict = e.to_dict()
                    # Check for required ICH E9(R1) estimand components
                    has_population = bool(e_dict.get('analysisPopulationId') or e_dict.get('populationSummary'))
                    has_variable = bool(e_dict.get('variableOfInterestId'))
                    has_intervention = bool(e_dict.get('interventionIds'))
                    
                    if has_population and has_variable and has_intervention:
                        valid_estimands.append(e_dict)
                    else:
                        # Log incomplete estimand but still include if it has meaningful content
                        if e_dict.get('name') and e_dict.get('populationSummary'):
                            valid_estimands.append(e_dict)
                
                if valid_estimands:
                    study_design["estimands"] = valid_estimands
            objectives_added = True
        
        # Fallback to previously extracted objectives
        if not objectives_added and previous_extractions.get('objectives'):
            prev = previous_extractions['objectives']
            if prev.get('objectives'):
                obj = prev['objectives']
                if obj.get('objectives'):
                    objectives = obj['objectives']
                    eps = obj.get('endpoints', [])
                    _default_endpoint_purpose(eps)
                    _nest_endpoints_in_objectives(objectives, eps)
                    study_design["objectives"] = objectives
                    combined["_temp_endpoints"] = eps
                if obj.get('estimands'):
                    study_design["estimands"] = obj['estimands']


# Register the phase
register_phase(ObjectivesPhase())
