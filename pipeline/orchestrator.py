"""
Pipeline orchestrator for running extraction phases.

Replaces the duplicated if-blocks in main_v2.py with a clean,
registry-driven approach.

Supports both sequential and parallel execution of phases.

Note: combine_to_full_usdm and helpers have been decomposed into:
  - pipeline.combiner       — combine_to_full_usdm, load_previous_extractions, defaults, SoA
  - pipeline.integrations   — SAP/sites integration, content refs, estimand reconciliation
  - pipeline.post_processing — entity reconciliation, activity sources, procedure linking
  - pipeline.promotion      — extension→USDM promotion rules

Backward-compatible re-exports are provided at the bottom of this module.
"""

from typing import Dict, List, Optional, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from .phase_registry import phase_registry
from .base_phase import BasePhase, PhaseResult, PhaseProvenance
from extraction.pipeline_context import PipelineContext, create_pipeline_context

logger = logging.getLogger(__name__)

# Phase dependency graph - phases that must complete before others can start
# Format: phase_name -> set of phases it depends on
PHASE_DEPENDENCIES = {
    'metadata': set(),  # No dependencies
    'eligibility': {'metadata'},  # Uses indication/phase from metadata
    'objectives': {'metadata'},  # Uses indication/phase from metadata
    'studydesign': set(),  # Uses SoA data (passed separately)
    'interventions': {'metadata', 'studydesign'},  # Uses arms + indication
    'narrative': set(),  # Independent
    'advanced': set(),  # Independent
    'procedures': set(),  # Independent
    'scheduling': set(),  # Independent
    'docstructure': set(),  # Independent
    'amendmentdetails': set(),  # Independent
    'execution': {'metadata', 'studydesign'},  # Needs study context for enrichment
}


class PipelineOrchestrator:
    """
    Orchestrates extraction phases using the registry pattern.
    
    Features:
    - Registry-driven phase execution
    - Automatic context propagation
    - Fallback to previous extractions
    - Clean separation of extraction and combination
    """
    
    def __init__(self, usage_tracker: Any = None):
        """
        Initialize orchestrator.
        
        Args:
            usage_tracker: Optional token usage tracker
        """
        self.usage_tracker = usage_tracker
        self._results: Dict[str, PhaseResult] = {}
        self._pipeline_context: Optional[PipelineContext] = None
    
    def run_phases(
        self,
        pdf_path: str,
        output_dir: str,
        model: str,
        phases_to_run: Dict[str, bool],
        soa_data: Optional[dict] = None,
        pipeline_context: Optional[PipelineContext] = None,
    ) -> Dict[str, PhaseResult]:
        """
        Run requested extraction phases.
        
        Args:
            pdf_path: Path to protocol PDF
            output_dir: Output directory
            model: LLM model name
            phases_to_run: Dict of phase_name -> bool indicating which to run
            soa_data: Optional SoA extraction data
            pipeline_context: Optional existing pipeline context
            
        Returns:
            Dict of phase_name -> PhaseResult
        """
        # Create or use existing pipeline context
        if pipeline_context is None:
            pipeline_context = create_pipeline_context(soa_data)
        self._pipeline_context = pipeline_context
        
        logger.info(f"Pipeline context: {pipeline_context.get_summary()}")
        
        results = {}
        
        # Enforce dependencies: auto-enable required phases
        phases_to_run = self._enforce_dependencies(phases_to_run)
        
        # Run each requested phase in registry order
        for phase in phase_registry.get_all():
            phase_name = phase.config.name.lower()
            
            # Check if this phase should run
            if not phases_to_run.get(phase_name, False):
                continue
            
            # Run the phase
            result = phase.run(
                pdf_path=pdf_path,
                model=model,
                output_dir=output_dir,
                context=pipeline_context,
                usage_tracker=self.usage_tracker,
                soa_data=soa_data,
            )
            
            results[phase_name] = result
        
        # Store pipeline context in results for downstream use
        results['_pipeline_context'] = pipeline_context
        self._results = results
        
        return results
    
    def run_phases_parallel(
        self,
        pdf_path: str,
        output_dir: str,
        model: str,
        phases_to_run: Dict[str, bool],
        soa_data: Optional[dict] = None,
        pipeline_context: Optional[PipelineContext] = None,
        max_workers: int = 4,
    ) -> Dict[str, PhaseResult]:
        """
        Run extraction phases with parallel execution where possible.
        
        Phases are grouped by dependency level and run in parallel within each level.
        
        Args:
            pdf_path: Path to protocol PDF
            output_dir: Output directory
            model: LLM model name
            phases_to_run: Dict of phase_name -> bool indicating which to run
            soa_data: Optional SoA extraction data
            pipeline_context: Optional existing pipeline context
            max_workers: Maximum parallel workers (default: 4)
            
        Returns:
            Dict of phase_name -> PhaseResult
        """
        # Create or use existing pipeline context
        if pipeline_context is None:
            pipeline_context = create_pipeline_context(soa_data)
        self._pipeline_context = pipeline_context
        
        logger.info(f"Pipeline context: {pipeline_context.get_summary()}")
        
        # Filter to only requested phases
        requested_phases = {
            name for name, should_run in phases_to_run.items() 
            if should_run and phase_registry.has(name)
        }
        
        if not requested_phases:
            logger.info("No phases requested")
            return {'_pipeline_context': pipeline_context}
        
        # Enforce dependencies: auto-enable required phases
        enforced = self._enforce_dependencies({p: True for p in requested_phases})
        requested_phases = {name for name, enabled in enforced.items() if enabled and phase_registry.has(name)}
        
        results = {}
        completed: Set[str] = set()
        
        # Build execution waves based on dependencies
        waves = self._build_execution_waves(requested_phases)
        logger.info(f"Parallel execution: {len(waves)} waves for {len(requested_phases)} phases")
        
        for wave_num, wave_phases in enumerate(waves, 1):
            if len(wave_phases) == 1:
                # Single phase - run directly
                phase_name = list(wave_phases)[0]
                phase = phase_registry.get(phase_name)
                if phase:
                    result = phase.run(
                        pdf_path=pdf_path,
                        model=model,
                        output_dir=output_dir,
                        context=pipeline_context,
                        usage_tracker=self.usage_tracker,
                        soa_data=soa_data,
                    )
                    results[phase_name] = result
                    completed.add(phase_name)
            else:
                # Multiple phases - run in parallel with isolated context snapshots
                logger.info(f"  Wave {wave_num}: Running {len(wave_phases)} phases in parallel: {wave_phases}")
                
                # Each phase gets its own snapshot to avoid shared-state races
                phase_snapshots = {}
                with ThreadPoolExecutor(max_workers=min(max_workers, len(wave_phases))) as executor:
                    futures = {}
                    for phase_name in wave_phases:
                        phase = phase_registry.get(phase_name)
                        if phase:
                            ctx_snapshot = pipeline_context.snapshot()
                            phase_snapshots[phase_name] = ctx_snapshot
                            future = executor.submit(
                                phase.run,
                                pdf_path=pdf_path,
                                model=model,
                                output_dir=output_dir,
                                context=ctx_snapshot,
                                usage_tracker=self.usage_tracker,
                                soa_data=soa_data,
                            )
                            futures[future] = phase_name
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        phase_name = futures[future]
                        try:
                            result = future.result()
                            results[phase_name] = result
                            completed.add(phase_name)
                        except Exception as e:
                            logger.error(f"Phase {phase_name} failed: {e}")
                            results[phase_name] = PhaseResult(success=False, error=str(e))
                            completed.add(phase_name)
                
                # Merge snapshots back into the authoritative context (main thread)
                for phase_name in wave_phases:
                    if phase_name in phase_snapshots and results.get(phase_name, PhaseResult(success=False)).success:
                        pipeline_context.merge_from(phase_name, phase_snapshots[phase_name])
        
        results['_pipeline_context'] = pipeline_context
        self._results = results
        
        return results
    
    def _build_execution_waves(self, requested_phases: Set[str]) -> List[Set[str]]:
        """
        Build execution waves based on phase dependencies.
        
        Returns list of sets, where each set contains phases that can run in parallel.
        """
        waves = []
        remaining = set(requested_phases)
        completed: Set[str] = set()
        
        while remaining:
            # Find phases whose dependencies are all satisfied
            ready = set()
            for phase in remaining:
                deps = PHASE_DEPENDENCIES.get(phase, set())
                # Only consider dependencies that are in requested_phases
                relevant_deps = deps & requested_phases
                if relevant_deps <= completed:
                    ready.add(phase)
            
            if not ready:
                # No phases ready - break dependency cycle by running all remaining
                logger.warning(f"Breaking dependency cycle, running remaining: {remaining}")
                ready = remaining.copy()
            
            waves.append(ready)
            completed.update(ready)
            remaining -= ready
        
        return waves
    
    def _enforce_dependencies(self, phases_to_run: Dict[str, bool]) -> Dict[str, bool]:
        """
        Enforce phase dependencies by auto-enabling required upstream phases.
        
        If a requested phase depends on another that wasn't requested,
        the dependency is automatically enabled and a warning is logged.
        
        Args:
            phases_to_run: Dict of phase_name -> bool
            
        Returns:
            Updated dict with dependencies auto-enabled
        """
        result = dict(phases_to_run)
        added = []
        
        # Iterate until stable (handles transitive deps)
        changed = True
        while changed:
            changed = False
            for phase_name, should_run in list(result.items()):
                if not should_run:
                    continue
                deps = PHASE_DEPENDENCIES.get(phase_name, set())
                for dep in deps:
                    if not result.get(dep, False) and phase_registry.has(dep):
                        result[dep] = True
                        added.append(f"{dep} (required by {phase_name})")
                        changed = True
        
        if added:
            logger.info(f"Auto-enabled dependency phases: {', '.join(added)}")
        
        return result
    
    def get_results(self) -> Dict[str, PhaseResult]:
        """Get all phase results."""
        return self._results
    
    def get_pipeline_context(self) -> Optional[PipelineContext]:
        """Get the pipeline context."""
        return self._pipeline_context
    
    def aggregate_provenance(self) -> dict:
        """Aggregate provenance from all completed phases.
        
        Returns a dict suitable for saving as extraction_provenance.json.
        """
        phases = []
        for name, result in self._results.items():
            if name.startswith('_'):
                continue
            if isinstance(result, PhaseResult) and result.provenance:
                phases.append(result.provenance.to_dict())
        
        total_duration = sum(p.get('durationSeconds', 0) for p in phases)
        succeeded = sum(1 for p in phases if not p.get('error'))
        
        return {
            'pipelineVersion': 'v3',
            'totalPhases': len(phases),
            'succeededPhases': succeeded,
            'totalDurationSeconds': round(total_duration, 2),
            'phases': phases,
        }
    
    def save_provenance(self, output_dir: str) -> str:
        """Save aggregated provenance to extraction_provenance.json.
        
        Returns the path to the saved file.
        """
        import json
        import os
        
        prov = self.aggregate_provenance()
        path = os.path.join(output_dir, 'extraction_provenance.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(prov, f, indent=2, ensure_ascii=False)
        logger.info(f"Extraction provenance: {path}")
        return path


# ---------------------------------------------------------------------------
# Backward-compatible re-exports
#
# All combine/integration/post-processing/promotion logic has been moved to
# dedicated modules. These re-exports ensure existing imports continue to work:
#   from pipeline.orchestrator import combine_to_full_usdm
#   from pipeline.orchestrator import _SAP_EXTENSION_TYPES
#   from pipeline.orchestrator import load_previous_extractions
# ---------------------------------------------------------------------------

from .combiner import combine_to_full_usdm, load_previous_extractions  # noqa: F401
from .integrations import SAP_EXTENSION_TYPES as _SAP_EXTENSION_TYPES  # noqa: F401
