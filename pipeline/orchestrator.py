"""
Pipeline orchestrator for running extraction phases.

Replaces the duplicated if-blocks in main_v2.py with a clean,
registry-driven approach.

Supports both sequential and parallel execution of phases.
"""

from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import logging

from .phase_registry import phase_registry
from .base_phase import BasePhase, PhaseResult
from extraction.pipeline_context import PipelineContext, create_pipeline_context
from extraction.conditional.ars_generator import generate_ars_from_sap

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


def load_previous_extractions(output_dir: str) -> dict:
    """
    Load previously extracted data from JSON files.
    
    This allows the combine function to use data from prior runs
    even when those phases weren't re-run in the current session.
    
    Returns dict of phase_name -> loaded data (dict format, not objects)
    """
    loaded = {}
    
    # Define extraction files and their phase names
    extraction_files = {
        'metadata': '2_study_metadata.json',
        'eligibility': '3_eligibility_criteria.json',
        'objectives': '4_objectives_endpoints.json',
        'studydesign': '5_study_design.json',
        'interventions': '6_interventions.json',
        'narrative': '7_narrative_structure.json',
        'advanced': '8_advanced_entities.json',
        'procedures': '9_procedures_devices.json',
        'scheduling': '10_scheduling_logic.json',
        'docstructure': '13_document_structure.json',
        'amendmentdetails': '14_amendment_details.json',
        'execution': '11_execution_model.json',
        'sap': '11_sap_populations.json',
    }
    
    for phase, filename in extraction_files.items():
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('success', True):
                        loaded[phase] = data
                        logger.debug(f"Loaded previous extraction: {phase}")
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not load {filename}: {e}")
    
    return loaded


def combine_to_full_usdm(
    output_dir: str,
    soa_data: dict = None,
    expansion_results: dict = None,
    pdf_path: str = None,
) -> tuple:
    """
    Combine SoA and expansion results into unified USDM JSON.
    
    This function merges:
    1. Data from expansion_results (current run, PhaseResult format)
    2. Data from previously saved JSON files (prior runs, dict format)
    
    Returns tuple of (combined_data, output_path)
    """
    import uuid
    
    # Import phases to trigger registration
    from . import phases as _  # noqa
    
    # Load previously extracted data from JSON files
    previous_extractions = load_previous_extractions(output_dir)
    logger.info(f"Loaded {len(previous_extractions)} previous extractions from output directory")
    
    # USDM v4.0 compliant structure
    combined = {
        "usdmVersion": "4.0",
        "generatedAt": datetime.now().isoformat(),
        "generator": "Protocol2USDM v7.2.0",
        "study": {
            "id": "study_1",
            "instanceType": "Study",
            "versions": []
        },
    }
    
    # Study version container
    study_version = {
        "id": "sv_1",
        "instanceType": "StudyVersion",
        "versionIdentifier": "1.0",
        "studyDesigns": [],
    }
    
    # Study design container — instanceType will be resolved after metadata combine
    study_design = {
        "id": "sd_1",
        "name": "Study Design",
        "rationale": "Protocol-defined study design for investigating efficacy and safety",
        "instanceType": "InterventionalStudyDesign",  # default, overridden below
    }
    
    # Run combine for each registered phase (always iterate, even without
    # current-run results, so previous_extractions can be used as fallback)
    for phase in phase_registry.get_all():
        phase_name = phase.config.name.lower()
        result = (expansion_results or {}).get(phase_name)
        
        phase.combine(
            result=result if result else PhaseResult(success=False),
            study_version=study_version,
            study_design=study_design,
            combined=combined,
            previous_extractions=previous_extractions,
        )
    
    # Apply defaults for required USDM fields
    _apply_defaults(study_version, study_design, combined, pdf_path)
    
    # Add SoA data
    _add_soa_data(study_design, soa_data)
    
    # Derive study design instanceType from metadata (instead of hardcoding)
    study_type = combined.pop("_temp_study_type", None)
    if study_type:
        normalized = study_type.strip().lower()
        if normalized in ("observational", "obs"):
            study_design["instanceType"] = "ObservationalStudyDesign"
            logger.info(f"  Study design type derived from metadata: ObservationalStudyDesign")
        else:
            study_design["instanceType"] = "InterventionalStudyDesign"
            logger.info(f"  Study design type derived from metadata: InterventionalStudyDesign")
    else:
        logger.info("  Study design type: defaulting to InterventionalStudyDesign (no metadata)")
    
    # Add indications to studyDesign (from metadata temp storage)
    if combined.get("_temp_indications"):
        study_design["indications"] = combined.pop("_temp_indications")
    
    # Add sites data from conditional sources (not a registered phase)
    if expansion_results and expansion_results.get('sites'):
        sites_result = expansion_results['sites']
        if hasattr(sites_result, 'data') and sites_result.data:
            sites_dict = sites_result.data.to_dict()
            sites_data = sites_dict.get('studySites', [])
            if sites_data:
                study_design['studySites'] = sites_data
                logger.info(f"  Added {len(sites_data)} study sites to studyDesign")
            
            # Add site organizations to study_version.organizations
            site_orgs = sites_dict.get('organizations', [])
            if site_orgs:
                existing_orgs = study_version.get('organizations', [])
                # Avoid duplicates by checking IDs
                existing_ids = {o.get('id') for o in existing_orgs}
                new_orgs = [o for o in site_orgs if o.get('id') not in existing_ids]
                study_version['organizations'] = existing_orgs + new_orgs
                logger.info(f"  Added {len(new_orgs)} site organizations")
    
    # Add SAP analysis populations from conditional sources
    if expansion_results and expansion_results.get('sap'):
        sap_result = expansion_results['sap']
        if hasattr(sap_result, 'data') and sap_result.data:
            sap_dict = sap_result.data.to_dict()
            populations = sap_dict.get('analysisPopulations', [])
            if populations:
                study_design['analysisPopulations'] = populations
                logger.info(f"  Added {len(populations)} analysis populations to studyDesign")
            
            # Store all SAP elements as USDM extensions with proper structure
            extensions = study_design.setdefault('extensionAttributes', [])
            
            # Derived variables
            derived_vars = sap_dict.get('derivedVariables', [])
            if derived_vars:
                extensions.append({
                    "id": "ext_sap_derived_variables",
                    "url": "https://protocol2usdm.io/extensions/x-sap-derived-variables",
                    "valueString": json.dumps(derived_vars),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Data handling rules
            data_rules = sap_dict.get('dataHandlingRules', [])
            if data_rules:
                extensions.append({
                    "id": "ext_sap_data_handling_rules",
                    "url": "https://protocol2usdm.io/extensions/x-sap-data-handling-rules",
                    "valueString": json.dumps(data_rules),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Statistical methods (STATO mapping)
            stat_methods = sap_dict.get('statisticalMethods', [])
            if stat_methods:
                extensions.append({
                    "id": "ext_sap_statistical_methods",
                    "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
                    "valueString": json.dumps(stat_methods),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Multiplicity adjustments
            mult_adj = sap_dict.get('multiplicityAdjustments', [])
            if mult_adj:
                extensions.append({
                    "id": "ext_sap_multiplicity_adjustments",
                    "url": "https://protocol2usdm.io/extensions/x-sap-multiplicity-adjustments",
                    "valueString": json.dumps(mult_adj),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Sensitivity analyses
            sens_analyses = sap_dict.get('sensitivityAnalyses', [])
            if sens_analyses:
                extensions.append({
                    "id": "ext_sap_sensitivity_analyses",
                    "url": "https://protocol2usdm.io/extensions/x-sap-sensitivity-analyses",
                    "valueString": json.dumps(sens_analyses),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Subgroup analyses
            subgroup_analyses = sap_dict.get('subgroupAnalyses', [])
            if subgroup_analyses:
                extensions.append({
                    "id": "ext_sap_subgroup_analyses",
                    "url": "https://protocol2usdm.io/extensions/x-sap-subgroup-analyses",
                    "valueString": json.dumps(subgroup_analyses),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Interim analyses
            interim_analyses = sap_dict.get('interimAnalyses', [])
            if interim_analyses:
                extensions.append({
                    "id": "ext_sap_interim_analyses",
                    "url": "https://protocol2usdm.io/extensions/x-sap-interim-analyses",
                    "valueString": json.dumps(interim_analyses),
                    "instanceType": "ExtensionAttribute"
                })
            
            # Sample size calculations
            sample_size = sap_dict.get('sampleSizeCalculations', [])
            if sample_size:
                extensions.append({
                    "id": "ext_sap_sample_size_calculations",
                    "url": "https://protocol2usdm.io/extensions/x-sap-sample-size-calculations",
                    "valueString": json.dumps(sample_size),
                    "instanceType": "ExtensionAttribute"
                })
            
            ext_counts = [
                f"{len(derived_vars)} derived variables" if derived_vars else None,
                f"{len(data_rules)} data handling rules" if data_rules else None,
                f"{len(stat_methods)} statistical methods" if stat_methods else None,
                f"{len(mult_adj)} multiplicity adjustments" if mult_adj else None,
                f"{len(sens_analyses)} sensitivity analyses" if sens_analyses else None,
                f"{len(subgroup_analyses)} subgroup analyses" if subgroup_analyses else None,
                f"{len(interim_analyses)} interim analyses" if interim_analyses else None,
                f"{len(sample_size)} sample size calculations" if sample_size else None,
            ]
            ext_summary = ", ".join([c for c in ext_counts if c])
            if ext_summary:
                logger.info(f"  Added SAP extensions: {ext_summary}")
            
            # Generate CDISC ARS output from SAP data
            try:
                study_name = study_version.get('titles', [{}])[0].get('text', 'Study')
                ars_output_path = os.path.join(output_dir, "ars_reporting_event.json")
                ars_data = generate_ars_from_sap(sap_dict, study_name, ars_output_path)
                
                # Count generated entities
                re = ars_data.get('reportingEvent', {})
                ars_counts = [
                    f"{len(re.get('analysisSets', []))} analysis sets",
                    f"{len(re.get('analysisMethods', []))} methods",
                    f"{len(re.get('analyses', []))} analyses",
                ]
                logger.info(f"  ✓ Generated CDISC ARS: {', '.join(ars_counts)}")
                logger.info(f"    Saved to: {ars_output_path}")
            except Exception as e:
                logger.warning(f"  ⚠ ARS generation failed: {e}")
    
    # Add studyDesign to study_version
    study_version["studyDesigns"] = [study_design]
    
    # Add computational execution metadata
    combined["computationalExecution"] = {
        "ready": True,
        "supportedSystems": ["EDC", "ePRO", "CTMS", "RTSM"],
        "validationStatus": "pending",
    }
    
    # Assemble final structure
    combined["study"]["versions"] = [study_version]
    
    # Handle execution model enrichment (special case - needs full structure)
    if expansion_results and expansion_results.get('execution'):
        exec_result = expansion_results['execution']
        if exec_result.success and exec_result.data:
            exec_phase = phase_registry.get('execution')
            if exec_phase and hasattr(exec_phase, 'enrich_usdm'):
                combined = exec_phase.enrich_usdm(combined, exec_result)
                logger.info(f"  ✓ Enriched USDM with execution model (Phase 14)")
                
                # Filter epochs added by enrichment
                combined = _filter_enrichment_epochs(combined, soa_data)
    
    # Run reconciliation
    combined = _run_reconciliation(combined, expansion_results, soa_data)
    
    # Mark activity sources
    _mark_activity_sources(study_design)
    
    # Link procedures to activities
    _link_procedures_to_activities(study_design)
    
    # Add SoA footnotes from header
    _add_soa_footnotes(study_design, output_dir)
    
    # Save combined output
    output_path = os.path.join(output_dir, "protocol_usdm.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Combined USDM saved to: {output_path}")
    return combined, output_path


def _apply_defaults(study_version: dict, study_design: dict, combined: dict, pdf_path: str) -> None:
    """Apply default values for required USDM fields."""
    import uuid
    
    # Default titles
    if "titles" not in study_version:
        pdf_name = Path(pdf_path).stem if pdf_path else "Unknown Protocol"
        study_version["titles"] = [{
            "id": str(uuid.uuid4()),
            "instanceType": "StudyTitle",
            "text": pdf_name,
            "type": {"code": "C99905x1", "codeSystem": "http://www.cdisc.org", "decode": "Official Study Title"}
        }]
        logger.warning("  Using fallback default for titles (metadata extraction failed)")
    
    # Default study identifiers
    if "studyIdentifiers" not in study_version:
        sponsor_org_id = str(uuid.uuid4())
        if "organizations" not in study_version:
            study_version["organizations"] = []
        study_version["organizations"].append({
            "id": sponsor_org_id,
            "instanceType": "Organization",
            "name": "Sponsor",
            "identifier": "SPONSOR",
            "identifierScheme": "DUNS",
            "type": {"code": "C70793", "codeSystem": "http://www.cdisc.org", "decode": "Clinical Study Sponsor"}
        })
        study_version["studyIdentifiers"] = [{
            "id": str(uuid.uuid4()),
            "instanceType": "StudyIdentifier",
            "text": "UNKNOWN",
            "scopeId": sponsor_org_id,
            "type": {"code": "C132351", "codeSystem": "http://www.cdisc.org", "decode": "Sponsor Protocol Identifier"}
        }]
        logger.warning("  Using fallback default for studyIdentifiers (metadata extraction failed)")
    
    # Default population
    if "population" not in study_design:
        study_design["population"] = {
            "id": "pop_1",
            "instanceType": "StudyDesignPopulation",
            "name": "Study Population",
            "description": "Target population for the study as defined by eligibility criteria",
            "includesHealthySubjects": False
        }
    elif "includesHealthySubjects" not in study_design["population"]:
        study_design["population"]["includesHealthySubjects"] = False
    
    # Default arms
    if "arms" not in study_design or not study_design["arms"]:
        study_design["arms"] = [{
            "id": "arm_1",
            "name": "Treatment Arm",
            "description": "Main treatment arm",
            "type": {
                "id": "code_arm_type_1",
                "code": "C174266",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Experimental Arm",
                "instanceType": "Code"
            },
            "dataOriginType": {
                "id": "code_data_origin_1",
                "code": "C142493",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Collected",
                "instanceType": "Code"
            },
            "dataOriginDescription": "Data collected during study conduct",
            "instanceType": "StudyArm"
        }]
    
    # Default epochs
    if "epochs" not in study_design or not study_design["epochs"]:
        study_design["epochs"] = [{
            "id": "epoch_1",
            "name": "Treatment Period",
            "description": "Main treatment period of the study",
            "instanceType": "StudyEpoch",
            "type": {
                "id": "code_epoch_type_1",
                "code": "C101526",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Treatment Epoch",
                "instanceType": "Code"
            }
        }]
    
    # Default study cells
    if "studyCells" not in study_design or not study_design["studyCells"]:
        arms = study_design.get("arms", [])
        epochs = study_design.get("epochs", [])
        cells = []
        for arm in arms:
            arm_id = arm.get("id", "arm_1")
            for epoch in epochs:
                epoch_id = epoch.get("id", "") if isinstance(epoch, dict) else getattr(epoch, 'id', '')
                if epoch_id:
                    cells.append({
                        "id": f"cell_{arm_id}_{epoch_id}",
                        "armId": arm_id,
                        "epochId": epoch_id,
                        "elementIds": [],
                        "instanceType": "StudyCell"
                    })
        if cells:
            study_design["studyCells"] = cells
        else:
            study_design["studyCells"] = [{
                "id": "cell_1",
                "armId": study_design["arms"][0]["id"] if study_design.get("arms") else "arm_1",
                "epochId": epochs[0].get("id", "epoch_1") if epochs else "epoch_1",
                "elementIds": [],
                "instanceType": "StudyCell"
            }]
    
    # Default model
    if "model" not in study_design:
        arms = study_design.get("arms", [])
        if len(arms) >= 2:
            study_design["model"] = {
                "id": "code_model_1",
                "code": "C82639",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Parallel Study",
                "instanceType": "Code"
            }
        else:
            study_design["model"] = {
                "id": "code_model_1",
                "code": "C82638",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Single Group Study",
                "instanceType": "Code"
            }


def _add_soa_data(study_design: dict, soa_data: Optional[dict]) -> None:
    """Add SoA data to study design."""
    if not soa_data:
        return
    
    soa_schedule = None
    
    # Try USDM v4.0 path
    if "study" in soa_data:
        try:
            sds = soa_data["study"]["versions"][0].get("studyDesigns", [])
            if sds and (sds[0].get("activities") or sds[0].get("scheduleTimelines") or 
                       sds[0].get("epochs") or sds[0].get("encounters")):
                soa_schedule = sds[0]
        except (KeyError, IndexError, TypeError):
            pass
        
        # Fallback: legacy timeline path
        if not soa_schedule:
            try:
                timeline = soa_data["study"]["versions"][0].get("timeline", {})
                if timeline and (timeline.get("activities") or timeline.get("activityTimepoints")):
                    soa_schedule = timeline
            except (KeyError, IndexError, TypeError):
                pass
    
    # Try top-level studyDesigns
    if not soa_schedule and "studyDesigns" in soa_data and soa_data["studyDesigns"]:
        soa_schedule = soa_data["studyDesigns"][0]
    
    if soa_schedule:
        soa_keys = ["scheduleTimelines", "encounters", "activities", "epochs",
                    "plannedTimepoints", "activityTimepoints", "activityGroups", "notes"]
        for key in soa_keys:
            if key in soa_schedule and soa_schedule[key]:
                study_design[key] = soa_schedule[key]
        
        # Ensure scheduleTimelines have required fields
        for timeline in study_design.get('scheduleTimelines', []):
            if 'mainTimeline' not in timeline:
                timeline['mainTimeline'] = True
            if 'entryCondition' not in timeline:
                timeline['entryCondition'] = "Subject meets all inclusion criteria and none of the exclusion criteria"
            if 'entryId' not in timeline:
                timeline['entryId'] = timeline.get('id', 'timeline_1')


def _filter_enrichment_epochs(combined: dict, soa_data: Optional[dict]) -> dict:
    """Filter out epochs added by enrichment that weren't in original SoA."""
    if not soa_data:
        return combined
    
    # Get original SoA epoch names
    original_soa_epoch_names = set()
    try:
        soa_sd = soa_data.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        for epoch in soa_sd.get("epochs", []):
            original_soa_epoch_names.add(epoch.get("name", "").lower().strip())
    except (KeyError, IndexError, TypeError):
        return combined
    
    if not original_soa_epoch_names:
        return combined
    
    # Filter epochs
    try:
        post_enrich_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        if post_enrich_design.get("epochs"):
            original_epochs = []
            removed_epochs = []
            removed_epoch_ids = set()
            
            for epoch in post_enrich_design.get("epochs", []):
                epoch_name = epoch.get("name", "").lower().strip()
                if epoch_name in original_soa_epoch_names:
                    original_epochs.append(epoch)
                else:
                    removed_epochs.append(epoch.get("name", "Unknown"))
                    removed_epoch_ids.add(epoch.get("id"))
            
            if removed_epochs:
                post_enrich_design["epochs"] = original_epochs
                logger.info(f"  ✓ Filtered {len(removed_epochs)} non-SoA epochs: {removed_epochs}")
                
                # Clean up timeline instances (preserve anchor instances)
                if removed_epoch_ids:
                    for timeline in post_enrich_design.get("scheduleTimelines", []):
                        instances = timeline.get("instances", [])
                        cleaned = []
                        for inst in instances:
                            if inst.get("epochId") not in removed_epoch_ids:
                                cleaned.append(inst)
                            else:
                                # Preserve anchor instances (they have anchorClassification extension)
                                ext_attrs = inst.get("extensionAttributes", [])
                                is_anchor = any(
                                    'anchorClassification' in (e.get('url', '') or '')
                                    for e in ext_attrs
                                )
                                if is_anchor:
                                    # Re-assign to first surviving epoch instead of dropping
                                    surviving_epochs = post_enrich_design.get("epochs", [])
                                    if surviving_epochs:
                                        inst["epochId"] = surviving_epochs[0].get("id")
                                    cleaned.append(inst)
                        if len(cleaned) < len(instances):
                            timeline["instances"] = cleaned
                            logger.info(f"  ✓ Cleaned {len(instances) - len(cleaned)} timeline instances")
    except Exception as e:
        logger.warning(f"  ⚠ Epoch filtering failed: {e}")
    
    return combined


def _run_reconciliation(combined: dict, expansion_results: dict, soa_data: dict) -> dict:
    """Run entity reconciliation (epochs, encounters, activities)."""
    from core.reconciliation import (
        reconcile_epochs_from_pipeline,
        reconcile_encounters_from_pipeline,
        reconcile_activities_from_pipeline,
    )
    from core.epoch_reconciler import enrich_epoch_names_with_clinical_type
    
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        
        # Get execution data
        execution_data = None
        if expansion_results and expansion_results.get('execution'):
            exec_result = expansion_results['execution']
            if exec_result.success:
                execution_data = exec_result.data
        
        # Epoch reconciliation
        soa_epochs = study_design.get("epochs", [])
        soa_encounters = study_design.get("encounters", [])
        
        if soa_epochs:
            enrich_epoch_names_with_clinical_type(soa_epochs, soa_encounters)
            
            # Get traversal sequence
            traversal_sequence = None
            if execution_data and hasattr(execution_data, 'traversal_constraints'):
                constraints = execution_data.traversal_constraints or []
                if constraints and hasattr(constraints[0], 'required_sequence'):
                    traversal_sequence = constraints[0].required_sequence
            
            reconciled_epochs = reconcile_epochs_from_pipeline(
                soa_epochs=soa_epochs,
                traversal_sequence=traversal_sequence,
            )
            if reconciled_epochs:
                study_design["epochs"] = reconciled_epochs
                main_epochs = [e for e in reconciled_epochs if any(
                    ext.get("valueString") == "main"
                    for ext in e.get("extensionAttributes", [])
                    if ext.get("url", "").endswith("epochCategory")
                )]
                logger.info(f"  ✓ Reconciled {len(reconciled_epochs)} epochs ({len(main_epochs)} main)")
                
                # Fix dangling epochId references
                valid_epoch_ids = {e.get('id') for e in reconciled_epochs}
                fallback_epoch_id = reconciled_epochs[0].get('id') if reconciled_epochs else None
                for enc in study_design.get("encounters", []):
                    if enc.get('epochId') and enc['epochId'] not in valid_epoch_ids and fallback_epoch_id:
                        enc['epochId'] = fallback_epoch_id
        
        # Encounter reconciliation
        soa_encounters = study_design.get("encounters", [])
        if soa_encounters:
            visit_windows = None
            if execution_data and hasattr(execution_data, 'visit_windows'):
                visit_windows = [vw.__dict__ if hasattr(vw, '__dict__') else vw
                               for vw in (execution_data.visit_windows or [])]
            
            reconciled_encounters = reconcile_encounters_from_pipeline(
                soa_encounters=soa_encounters,
                visit_windows=visit_windows,
            )
            if reconciled_encounters:
                study_design["encounters"] = reconciled_encounters
                logger.info(f"  ✓ Reconciled {len(reconciled_encounters)} encounters")
                
                # Populate epochId on schedule instances
                enc_to_epoch = {enc.get('id'): enc.get('epochId') for enc in reconciled_encounters}
                epochs = study_design.get('epochs', [])
                fallback_epoch_id = epochs[0].get('id') if epochs else None
                
                for timeline in study_design.get('scheduleTimelines', []):
                    for inst in timeline.get('instances', []):
                        if not inst.get('epochId'):
                            enc_id = inst.get('encounterId')
                            if enc_id and enc_id in enc_to_epoch:
                                inst['epochId'] = enc_to_epoch[enc_id]
                            elif fallback_epoch_id:
                                inst['epochId'] = fallback_epoch_id
        
        # Activity reconciliation
        soa_activities = study_design.get("activities", [])
        if soa_activities:
            procedure_activities = None
            if expansion_results and expansion_results.get('procedures'):
                proc_result = expansion_results['procedures']
                if proc_result.success and proc_result.data:
                    if hasattr(proc_result.data, 'procedures'):
                        procedure_activities = [
                            p.__dict__ if hasattr(p, '__dict__') else p
                            for p in (proc_result.data.procedures or [])
                        ]
            
            execution_repetitions = None
            if execution_data and hasattr(execution_data, 'repetitions'):
                execution_repetitions = [r.__dict__ if hasattr(r, '__dict__') else r
                                        for r in (execution_data.repetitions or [])]
            
            footnote_conditions = None
            if execution_data and hasattr(execution_data, 'footnote_conditions'):
                footnote_conditions = [f.__dict__ if hasattr(f, '__dict__') else f
                                      for f in (execution_data.footnote_conditions or [])]
            
            activity_group_names = [g.get('name') for g in study_design.get('activityGroups', [])]
            
            reconciled_activities = reconcile_activities_from_pipeline(
                soa_activities=soa_activities,
                procedure_activities=procedure_activities,
                execution_repetitions=execution_repetitions,
                footnote_conditions=footnote_conditions,
                activity_group_names=activity_group_names,
            )
            if reconciled_activities:
                study_design["activities"] = reconciled_activities
                logger.info(f"  ✓ Reconciled {len(reconciled_activities)} activities")
                
                # Update activityIds in schedule instances
                _update_activity_references(study_design, soa_activities, reconciled_activities)
    
    except Exception as e:
        logger.warning(f"  ⚠ Entity reconciliation skipped: {e}")
    
    return combined


def _update_activity_references(study_design: dict, soa_activities: list, reconciled_activities: list) -> None:
    """Update activity references after reconciliation."""
    # Build name-to-ID mappings
    activity_name_to_new_id = {}
    for act in reconciled_activities:
        act_name = act.get('name', '').lower().strip()
        if act_name:
            activity_name_to_new_id[act_name] = act.get('id')
    
    old_id_to_new_id = {}
    for orig_act in soa_activities:
        orig_name = orig_act.get('name', '').lower().strip()
        orig_id = orig_act.get('id')
        if orig_name and orig_id and orig_name in activity_name_to_new_id:
            old_id_to_new_id[orig_id] = activity_name_to_new_id[orig_name]
    
    # Update activityGroups.childIds
    for group in study_design.get('activityGroups', []):
        old_child_ids = group.get('childIds', [])
        new_child_ids = []
        for old_id in old_child_ids:
            for orig_act in soa_activities:
                if orig_act.get('id') == old_id:
                    matched_name = orig_act.get('name', '').lower().strip()
                    if matched_name in activity_name_to_new_id:
                        new_child_ids.append(activity_name_to_new_id[matched_name])
                    break
        if new_child_ids:
            group['childIds'] = new_child_ids
    
    # Update schedule instances
    valid_activity_ids = {a.get('id') for a in reconciled_activities}
    updated = 0
    fixed_dangling = 0
    
    for timeline in study_design.get('scheduleTimelines', []):
        for inst in timeline.get('instances', []):
            old_act_ids = inst.get('activityIds', [])
            new_act_ids = [old_id_to_new_id.get(oid, oid) for oid in old_act_ids]
            
            if new_act_ids != old_act_ids:
                inst['activityIds'] = new_act_ids
                updated += 1
            
            # Fix dangling references
            valid_ids = [aid for aid in inst.get('activityIds', []) if aid in valid_activity_ids]
            if len(valid_ids) != len(inst.get('activityIds', [])):
                if valid_ids:
                    inst['activityIds'] = valid_ids
                else:
                    fallback = next(iter(valid_activity_ids), None)
                    if fallback:
                        inst['activityIds'] = [fallback]
                fixed_dangling += 1
    
    if updated > 0:
        logger.info(f"  ✓ Updated activityIds in {updated} schedule instances")
    if fixed_dangling > 0:
        logger.info(f"  ✓ Fixed {fixed_dangling} dangling activityIds")


def _mark_activity_sources(study_design: dict) -> None:
    """Mark activities with their source (soa vs procedure_enrichment)."""
    try:
        scheduleTimelines = study_design.get('scheduleTimelines', [])
        if not scheduleTimelines:
            return
        
        instances = scheduleTimelines[0].get('instances', [])
        activity_ids_with_ticks = set()
        for inst in instances:
            activity_ids_with_ticks.update(inst.get('activityIds', []))
        
        soa_count = 0
        procedure_count = 0
        
        for activity in study_design.get('activities', []):
            act_id = activity.get('id')
            has_ticks = act_id in activity_ids_with_ticks
            
            if 'extensionAttributes' not in activity:
                activity['extensionAttributes'] = []
            
            # Remove existing activitySource
            activity['extensionAttributes'] = [
                ext for ext in activity['extensionAttributes']
                if not ext.get('url', '').endswith('activitySource')
            ]
            
            source = 'soa' if has_ticks else 'procedure_enrichment'
            activity['extensionAttributes'].append({
                'id': f"ext_source_{act_id[:8] if act_id else 'unknown'}",
                'url': 'http://example.org/usdm/activitySource',
                'valueString': source,
                'instanceType': 'ExtensionAttribute'
            })
            
            if has_ticks:
                soa_count += 1
            else:
                procedure_count += 1
        
        logger.info(f"  ✓ Marked activities: {soa_count} SoA, {procedure_count} procedure enrichment")
        
        # Update activityGroups.childIds to only include SoA activities
        for group in study_design.get('activityGroups', []):
            child_ids = group.get('childIds', [])
            group['childIds'] = [cid for cid in child_ids if cid in activity_ids_with_ticks]
    
    except Exception as e:
        logger.warning(f"  ⚠ Activity source marking skipped: {e}")


def _link_procedures_to_activities(study_design: dict) -> None:
    """Link procedures to activities via definedProcedures."""
    import uuid
    
    try:
        procedures = study_design.get('procedures', [])
        activities = study_design.get('activities', [])
        
        if not procedures or not activities:
            return
        
        # Sanitize procedure codes
        for proc in procedures:
            code = proc.get('code')
            if code and isinstance(code, dict) and not code.get('code'):
                proc_type = proc.get('procedureType', 'Clinical Procedure')
                type_codes = {
                    'Diagnostic Procedure': ('C25391', 'Diagnostic Procedure'),
                    'Therapeutic Procedure': ('C49236', 'Therapeutic Procedure'),
                    'Surgical Procedure': ('C17173', 'Surgical Procedure'),
                    'Biospecimen Collection': ('C70793', 'Biospecimen Collection'),
                    'Imaging Technique': ('C17369', 'Imaging Technique'),
                    'Monitoring': ('C25548', 'Monitoring'),
                    'Assessment': ('C25218', 'Assessment'),
                }
                default_code, default_decode = type_codes.get(proc_type, ('C25218', 'Clinical Procedure'))
                proc['code'] = {
                    'id': code.get('id') or str(uuid.uuid4()),
                    'code': default_code,
                    'codeSystem': 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl',
                    'codeSystemVersion': '25.01d',
                    'decode': default_decode,
                    'instanceType': 'Code',
                }
        
        # Build name lookup
        proc_by_name = {proc.get('name', '').lower().strip(): proc for proc in procedures if proc.get('name')}
        
        # Link procedures to activities
        linked_count = 0
        for activity in activities:
            act_name = activity.get('name', '').lower().strip()
            
            matched_proc = proc_by_name.get(act_name)
            if not matched_proc:
                for proc_name, proc in proc_by_name.items():
                    if proc_name in act_name or act_name in proc_name:
                        matched_proc = proc
                        break
            
            if matched_proc:
                if 'definedProcedures' not in activity:
                    activity['definedProcedures'] = []
                existing_ids = {p.get('id') for p in activity['definedProcedures']}
                if matched_proc.get('id') not in existing_ids:
                    activity['definedProcedures'].append(matched_proc)
                    linked_count += 1
        
        if linked_count > 0:
            logger.info(f"  ✓ Linked {linked_count} procedures to activities")
    
    except Exception as e:
        logger.warning(f"  ⚠ Procedure-Activity linking skipped: {e}")


def _add_soa_footnotes(study_design: dict, output_dir: str) -> None:
    """Add authoritative SoA footnotes from header_structure.json."""
    try:
        header_path = os.path.join(output_dir, "4_header_structure.json")
        if not os.path.exists(header_path):
            return
        
        with open(header_path, 'r', encoding='utf-8') as f:
            header_data = json.load(f)
        
        soa_footnotes = header_data.get('footnotes', [])
        if soa_footnotes:
            if 'extensionAttributes' not in study_design:
                study_design['extensionAttributes'] = []
            
            # Remove existing SoA footnotes
            study_design['extensionAttributes'] = [
                ext for ext in study_design['extensionAttributes']
                if not ext.get('url', '').endswith('soaFootnotes')
            ]
            
            study_design['extensionAttributes'].append({
                'id': f"ext_soa_footnotes_{study_design.get('id', 'sd')[:8]}",
                'url': 'https://protocol2usdm.io/extensions/x-soaFootnotes',
                'valueString': json.dumps(soa_footnotes),
                'instanceType': 'ExtensionAttribute'
            })
            logger.info(f"  ✓ Added {len(soa_footnotes)} authoritative SoA footnotes")
    
    except Exception as e:
        logger.warning(f"  ⚠ SoA footnotes addition skipped: {e}")
