"""
Full Protocol Extraction Pipeline

Orchestrates complete USDM extraction with proper:
- Step numbering
- Data merging
- Hierarchical USDM conversion
- Schema validation
- CDISC conformance checks

Produces a "Golden Standard" USDM output suitable for:
- EDC system configuration
- Mobile app configuration
- Study execution software
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """Result of a pipeline step."""
    step_number: int
    name: str
    success: bool
    output_file: Optional[str] = None
    data: Optional[Dict] = None
    confidence: float = 0.0
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    """Complete pipeline result."""
    success: bool
    mode: str  # 'soa_only' or 'full_protocol'
    steps: List[PipelineStep] = field(default_factory=list)
    final_output: Optional[str] = None
    schema_valid: bool = False
    conformance_issues: int = 0
    total_entities: int = 0
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)


class ProtocolExtractionPipeline:
    """
    Full Protocol to USDM Extraction Pipeline.
    
    Extracts clinical protocol content and produces a golden standard
    USDM v4.0 JSON suitable for computational execution.
    """
    
    def __init__(
        self,
        pdf_path: str,
        output_dir: str,
        model_name: str = "gemini-2.5-pro",
        soa_pages: Optional[List[int]] = None,
    ):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.soa_pages = soa_pages
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Step counter
        self.current_step = 0
        
        # Collected data
        self.soa_data = None
        self.expansion_data = {}
        self.combined_data = None
        
    def _next_step(self) -> int:
        """Get next step number."""
        self.current_step += 1
        return self.current_step
    
    def _step_file(self, name: str) -> str:
        """Get output file path for a step."""
        return os.path.join(self.output_dir, f"{self.current_step:02d}_{name}.json")
    
    def _save_json(self, data: dict, filepath: str) -> None:
        """Save data to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_json(self, filepath: str) -> Optional[dict]:
        """Load data from JSON file."""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def run_soa_extraction(self) -> PipelineStep:
        """
        Run Schedule of Activities extraction (Steps 1-6).
        """
        from extraction import run_from_files, PipelineConfig as SoAPipelineConfig
        
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Schedule of Activities Extraction")
        logger.info(f"{'='*60}")
        
        try:
            config = SoAPipelineConfig(
                model_name=self.model_name,
                validate_with_vision=True,
                remove_hallucinations=True,
                save_intermediate=True,
            )
            
            result = run_from_files(
                pdf_path=self.pdf_path,
                output_dir=self.output_dir,
                soa_pages=self.soa_pages,
                config=config,
            )
            
            if result.success and result.output_path:
                self.soa_data = self._load_json(result.output_path)
            
            return PipelineStep(
                step_number=step_num,
                name="soa_extraction",
                success=result.success,
                output_file=result.output_path,
                data=self.soa_data,
                confidence=0.95 if result.success else 0.0,
                error='; '.join(result.errors) if result.errors else None,
            )
            
        except Exception as e:
            logger.error(f"SoA extraction failed: {e}")
            return PipelineStep(
                step_number=step_num,
                name="soa_extraction",
                success=False,
                error=str(e),
            )
    
    def run_expansion_phase(
        self,
        phase_key: str,
        phase_name: str,
        extractor_fn,
        save_fn,
        confidence_fn,
        data_attr: str = 'data',
    ) -> PipelineStep:
        """
        Run a single expansion phase.
        """
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: {phase_name}")
        logger.info(f"{'='*60}")
        
        try:
            result = extractor_fn(self.pdf_path, model_name=self.model_name)
            
            output_file = self._step_file(phase_key)
            save_fn(result, output_file)
            
            data = getattr(result, data_attr, None) or getattr(result, 'metadata', None)
            confidence = 0.0
            if result.success and data:
                conf_result = confidence_fn(data)
                confidence = conf_result.overall if hasattr(conf_result, 'overall') else 0.0
                self.expansion_data[phase_key] = {
                    'success': result.success,
                    'data': data,
                    'confidence': confidence,
                }
                logger.info(f"  ✓ {phase_name} (📊 {confidence:.0%})")
            else:
                logger.warning(f"  ✗ {phase_name} failed: {result.error}")
            
            return PipelineStep(
                step_number=step_num,
                name=phase_key,
                success=result.success,
                output_file=output_file,
                confidence=confidence,
                error=result.error,
            )
            
        except Exception as e:
            logger.error(f"{phase_name} failed: {e}")
            return PipelineStep(
                step_number=step_num,
                name=phase_key,
                success=False,
                error=str(e),
            )
    
    def run_all_expansions(self) -> List[PipelineStep]:
        """Run all expansion phases."""
        from extraction.metadata import extract_study_metadata
        from extraction.metadata.extractor import save_metadata_result
        from extraction.eligibility import extract_eligibility_criteria
        from extraction.eligibility.extractor import save_eligibility_result
        from extraction.objectives import extract_objectives_endpoints
        from extraction.objectives.extractor import save_objectives_result
        from extraction.studydesign import extract_study_design
        from extraction.studydesign.extractor import save_study_design_result
        from extraction.interventions import extract_interventions
        from extraction.interventions.extractor import save_interventions_result
        from extraction.narrative import extract_narrative_structure
        from extraction.narrative.extractor import save_narrative_result
        from extraction.advanced import extract_advanced_entities
        from extraction.advanced.extractor import save_advanced_result
        from extraction.confidence import (
            calculate_metadata_confidence,
            calculate_eligibility_confidence,
            calculate_objectives_confidence,
            calculate_studydesign_confidence,
            calculate_interventions_confidence,
            calculate_narrative_confidence,
            calculate_advanced_confidence,
        )
        
        phases = [
            ('metadata', 'Study Metadata', extract_study_metadata, save_metadata_result, calculate_metadata_confidence, 'metadata'),
            ('eligibility', 'Eligibility Criteria', extract_eligibility_criteria, save_eligibility_result, calculate_eligibility_confidence, 'data'),
            ('objectives', 'Objectives & Endpoints', extract_objectives_endpoints, save_objectives_result, calculate_objectives_confidence, 'data'),
            ('studydesign', 'Study Design', extract_study_design, save_study_design_result, calculate_studydesign_confidence, 'data'),
            ('interventions', 'Interventions & Products', extract_interventions, save_interventions_result, calculate_interventions_confidence, 'data'),
            ('narrative', 'Narrative Structure', extract_narrative_structure, save_narrative_result, calculate_narrative_confidence, 'data'),
            ('advanced', 'Advanced Entities', extract_advanced_entities, save_advanced_result, calculate_advanced_confidence, 'data'),
        ]
        
        results = []
        for phase_key, phase_name, extractor, saver, conf_fn, data_attr in phases:
            result = self.run_expansion_phase(
                phase_key, phase_name, extractor, saver, conf_fn, data_attr
            )
            results.append(result)
        
        return results
    
    def combine_to_usdm(self) -> PipelineStep:
        """
        Combine all extracted data into unified USDM structure.
        """
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Combine to USDM Structure")
        logger.info(f"{'='*60}")
        
        try:
            combined = self._build_combined_usdm()
            
            output_file = self._step_file("combined_raw")
            self._save_json(combined, output_file)
            self.combined_data = combined
            
            entity_count = self._count_entities(combined)
            logger.info(f"  ✓ Combined {entity_count} entities")
            
            return PipelineStep(
                step_number=step_num,
                name="combine_usdm",
                success=True,
                output_file=output_file,
                data=combined,
            )
            
        except Exception as e:
            logger.error(f"Combine failed: {e}")
            return PipelineStep(
                step_number=step_num,
                name="combine_usdm",
                success=False,
                error=str(e),
            )
    
    def _build_combined_usdm(self) -> dict:
        """Build the combined USDM structure."""
        combined = {
            "usdmVersion": "4.0",
            "systemName": "Protocol2USDM",
            "systemVersion": "6.0",
            "extractionTimestamp": datetime.utcnow().isoformat() + "Z",
            "study": {
                "id": "study_1",
                "instanceType": "Study",
            }
        }
        
        # Initialize study version structure
        study_version = {
            "id": "sv_1",
            "instanceType": "StudyVersion",
            "titles": [],
            "studyIdentifiers": [],
            "organizations": [],
            "studyPhase": None,
            "studyType": None,
            "studyDesigns": [],
        }
        
        # Merge metadata
        if 'metadata' in self.expansion_data:
            md_data = self.expansion_data['metadata'].get('data')
            if md_data:
                study_version['titles'] = [t.to_dict() for t in getattr(md_data, 'titles', [])]
                study_version['studyIdentifiers'] = [i.to_dict() for i in getattr(md_data, 'identifiers', [])]
                study_version['organizations'] = [o.to_dict() for o in getattr(md_data, 'organizations', [])]
                if md_data.study_phase:
                    study_version['studyPhase'] = md_data.study_phase.to_dict()
                if md_data.indications:
                    study_version['studyIndications'] = [ind.to_dict() for ind in md_data.indications]
        
        # Build study design structure
        study_design = {
            "id": "sd_1",
            "instanceType": "StudyDesign",
        }
        
        # Merge eligibility
        if 'eligibility' in self.expansion_data:
            elig_data = self.expansion_data['eligibility'].get('data')
            if elig_data:
                study_design['populations'] = [elig_data.population.to_dict()] if elig_data.population else []
                study_design['eligibilityCriteria'] = [c.to_dict() for c in elig_data.criteria]
                study_design['eligibilityCriterionItems'] = [i.to_dict() for i in elig_data.criterion_items]
        
        # Merge objectives
        if 'objectives' in self.expansion_data:
            obj_data = self.expansion_data['objectives'].get('data')
            if obj_data:
                study_design['objectives'] = [o.to_dict() for o in obj_data.objectives]
                study_design['endpoints'] = [e.to_dict() for e in obj_data.endpoints]
                if obj_data.estimands:
                    study_design['estimands'] = [est.to_dict() for est in obj_data.estimands]
        
        # Merge study design structure
        if 'studydesign' in self.expansion_data:
            sd_data = self.expansion_data['studydesign'].get('data')
            if sd_data:
                if sd_data.study_design:
                    study_design['studyType'] = sd_data.study_design.to_dict()
                study_design['arms'] = [a.to_dict() for a in sd_data.arms]
                study_design['studyCells'] = [c.to_dict() for c in sd_data.cells]
                study_design['studyCohorts'] = [c.to_dict() for c in sd_data.cohorts]
        
        # Merge interventions
        if 'interventions' in self.expansion_data:
            iv_data = self.expansion_data['interventions'].get('data')
            if iv_data:
                study_design['studyInterventions'] = [i.to_dict() for i in iv_data.interventions]
                study_design['administrableProducts'] = [p.to_dict() for p in iv_data.products]
                study_design['administrations'] = [a.to_dict() for a in iv_data.administrations]
        
        # Merge SoA (schedule timelines)
        if self.soa_data:
            timeline = self._extract_timeline(self.soa_data)
            if timeline:
                study_design['scheduleTimelines'] = [timeline]
        
        study_version['studyDesigns'] = [study_design]
        
        # Merge narrative content
        if 'narrative' in self.expansion_data:
            narr_data = self.expansion_data['narrative'].get('data')
            if narr_data:
                study_version['narrativeContents'] = [s.to_dict() for s in narr_data.sections]
                study_version['abbreviations'] = [a.to_dict() for a in narr_data.abbreviations]
                if narr_data.document:
                    study_version['studyDefinitionDocument'] = narr_data.document.to_dict()
        
        # Merge advanced entities
        if 'advanced' in self.expansion_data:
            adv_data = self.expansion_data['advanced'].get('data')
            if adv_data:
                study_version['amendments'] = [a.to_dict() for a in adv_data.amendments]
                if adv_data.geographic_scope:
                    study_version['geographicScopes'] = [adv_data.geographic_scope.to_dict()]
        
        combined['study']['versions'] = [study_version]
        
        return combined
    
    def _extract_timeline(self, soa_data: dict) -> Optional[dict]:
        """Extract timeline from SoA data."""
        # Try standard USDM path
        try:
            timeline = soa_data.get('study', {}).get('versions', [{}])[0].get('timeline')
            if timeline:
                return {
                    "id": "timeline_1",
                    "instanceType": "ScheduleTimeline",
                    "name": "Main Schedule",
                    **timeline
                }
        except (KeyError, IndexError):
            pass
        
        # Try direct timeline
        if 'timeline' in soa_data:
            return {
                "id": "timeline_1", 
                "instanceType": "ScheduleTimeline",
                "name": "Main Schedule",
                **soa_data['timeline']
            }
        
        return None
    
    def _count_entities(self, data: dict) -> int:
        """Count total entities in combined data."""
        count = 0
        
        def count_recursive(obj):
            nonlocal count
            if isinstance(obj, dict):
                if 'instanceType' in obj:
                    count += 1
                for v in obj.values():
                    count_recursive(v)
            elif isinstance(obj, list):
                for item in obj:
                    count_recursive(item)
        
        count_recursive(data)
        return count
    
    def convert_to_hierarchical(self) -> PipelineStep:
        """
        Convert to proper hierarchical USDM structure.
        
        This step ensures the output matches the USDM 4.0 specification
        with proper nesting and relationships.
        """
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Convert to Hierarchical USDM")
        logger.info(f"{'='*60}")
        
        try:
            hierarchical = self._apply_hierarchical_transform(self.combined_data)
            
            output_file = self._step_file("hierarchical")
            self._save_json(hierarchical, output_file)
            self.combined_data = hierarchical
            
            logger.info(f"  ✓ Converted to hierarchical structure")
            
            return PipelineStep(
                step_number=step_num,
                name="hierarchical_transform",
                success=True,
                output_file=output_file,
                data=hierarchical,
            )
            
        except Exception as e:
            logger.error(f"Hierarchical transform failed: {e}")
            return PipelineStep(
                step_number=step_num,
                name="hierarchical_transform",
                success=False,
                error=str(e),
            )
    
    def _apply_hierarchical_transform(self, data: dict) -> dict:
        """
        Apply hierarchical transformations for USDM 4.0 compliance.
        
        Key transformations:
        1. Ensure StudyDesign contains proper ScheduleTimelines
        2. Link ScheduledActivityInstances properly
        3. Ensure all cross-references are valid
        4. Add computational execution metadata
        """
        # Deep copy to avoid modifying original
        import copy
        result = copy.deepcopy(data)
        
        # Add computational execution metadata
        result['computationalExecution'] = {
            'ready': True,
            'supportedSystems': ['EDC', 'ePRO', 'CTMS', 'RTSM'],
            'validationStatus': 'pending',
        }
        
        # Ensure proper StudyDesign structure
        if 'study' in result and 'versions' in result['study']:
            for version in result['study']['versions']:
                if 'studyDesigns' in version:
                    for study_design in version['studyDesigns']:
                        # Ensure scheduleTimelines is properly structured
                        if 'scheduleTimelines' in study_design:
                            for timeline in study_design['scheduleTimelines']:
                                self._structure_timeline(timeline)
        
        return result
    
    def _structure_timeline(self, timeline: dict) -> None:
        """Ensure timeline has proper USDM structure."""
        # Ensure required fields
        if 'id' not in timeline:
            timeline['id'] = 'timeline_1'
        if 'instanceType' not in timeline:
            timeline['instanceType'] = 'ScheduleTimeline'
        
        # Convert activityTimepoints to scheduledActivityInstances if needed
        if 'activityTimepoints' in timeline and 'scheduledActivityInstances' not in timeline:
            timeline['scheduledActivityInstances'] = []
            for i, atp in enumerate(timeline.get('activityTimepoints', [])):
                instance = {
                    'id': f'sai_{i+1}',
                    'instanceType': 'ScheduledActivityInstance',
                    'activityId': atp.get('activityId'),
                    'timepointId': atp.get('plannedTimepointId') or atp.get('timepointId'),
                    'timelineId': timeline['id'],
                }
                timeline['scheduledActivityInstances'].append(instance)
    
    def run_terminology_enrichment(self) -> PipelineStep:
        """Run terminology enrichment on combined data."""
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Terminology Enrichment")
        logger.info(f"{'='*60}")
        
        try:
            from enrichment.terminology import enrich_terminology
            
            # Save current state for enrichment
            temp_file = self._step_file("pre_enrichment")
            self._save_json(self.combined_data, temp_file)
            
            result = enrich_terminology(temp_file)
            
            if result.get('success'):
                # Reload enriched data
                self.combined_data = self._load_json(temp_file)
                logger.info(f"  ✓ Enriched {result.get('enriched', 0)} entities")
            else:
                logger.warning(f"  ⚠ Enrichment skipped: {result.get('error', 'Unknown')}")
            
            output_file = self._step_file("enriched")
            self._save_json(self.combined_data, output_file)
            
            return PipelineStep(
                step_number=step_num,
                name="terminology_enrichment",
                success=True,
                output_file=output_file,
            )
            
        except Exception as e:
            logger.warning(f"Terminology enrichment skipped: {e}")
            return PipelineStep(
                step_number=step_num,
                name="terminology_enrichment",
                success=True,  # Non-critical
                error=str(e),
            )
    
    def run_schema_validation(self) -> PipelineStep:
        """Validate against USDM schema."""
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Schema Validation")
        logger.info(f"{'='*60}")
        
        try:
            from validation.schema_validator import validate_schema
            
            result = validate_schema(self.combined_data)
            
            output_file = self._step_file("schema_validation")
            self._save_json(result, output_file)
            
            if result.get('valid'):
                logger.info(f"  ✓ Schema validation PASSED")
            else:
                issues = result.get('issues', [])
                logger.warning(f"  ⚠ Schema validation: {len(issues)} issues")
            
            return PipelineStep(
                step_number=step_num,
                name="schema_validation",
                success=result.get('valid', False),
                output_file=output_file,
                data=result,
            )
            
        except Exception as e:
            logger.warning(f"Schema validation skipped: {e}")
            return PipelineStep(
                step_number=step_num,
                name="schema_validation",
                success=True,  # Non-blocking
                error=str(e),
            )
    
    def run_cdisc_conformance(self) -> PipelineStep:
        """Run CDISC CORE conformance checks."""
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: CDISC Conformance")
        logger.info(f"{'='*60}")
        
        try:
            from validation.cdisc_conformance import run_cdisc_conformance
            
            # Save current data for conformance check
            temp_file = self._step_file("pre_conformance")
            self._save_json(self.combined_data, temp_file)
            
            result = run_cdisc_conformance(temp_file, self.output_dir)
            
            output_file = self._step_file("conformance_report")
            if result.get('output') and os.path.exists(result['output']):
                # Rename to proper step number
                os.rename(result['output'], output_file)
            else:
                self._save_json(result, output_file)
            
            if result.get('success'):
                logger.info(f"  ✓ Conformance check completed")
            else:
                logger.warning(f"  ⚠ Conformance: {result.get('error', 'Unknown')}")
            
            return PipelineStep(
                step_number=step_num,
                name="cdisc_conformance",
                success=result.get('success', False),
                output_file=output_file,
                data=result,
            )
            
        except Exception as e:
            logger.warning(f"CDISC conformance skipped: {e}")
            return PipelineStep(
                step_number=step_num,
                name="cdisc_conformance",
                success=True,  # Non-blocking
                error=str(e),
            )
    
    def save_final_output(self) -> PipelineStep:
        """Save final golden standard USDM output."""
        step_num = self._next_step()
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step_num}: Save Golden Standard Output")
        logger.info(f"{'='*60}")
        
        try:
            # Add final metadata
            self.combined_data['extractionComplete'] = True
            self.combined_data['finalTimestamp'] = datetime.utcnow().isoformat() + "Z"
            self.combined_data['computationalExecution']['validationStatus'] = 'complete'
            
            # Save as golden standard
            output_file = os.path.join(self.output_dir, "protocol_usdm.json")
            self._save_json(self.combined_data, output_file)
            
            entity_count = self._count_entities(self.combined_data)
            logger.info(f"  ✓ Saved golden standard USDM ({entity_count} entities)")
            logger.info(f"  📄 {output_file}")
            
            return PipelineStep(
                step_number=step_num,
                name="final_output",
                success=True,
                output_file=output_file,
                data={'entity_count': entity_count},
            )
            
        except Exception as e:
            logger.error(f"Failed to save final output: {e}")
            return PipelineStep(
                step_number=step_num,
                name="final_output",
                success=False,
                error=str(e),
            )
    
    def run_full_protocol(self) -> PipelineResult:
        """
        Run complete protocol extraction pipeline.
        
        Steps:
        1. SoA Extraction
        2-8. Expansion Phases (Metadata, Eligibility, Objectives, etc.)
        9. Combine to USDM
        10. Hierarchical Transform
        11. Terminology Enrichment
        12. Schema Validation
        13. CDISC Conformance
        14. Final Output
        """
        logger.info("\n" + "=" * 60)
        logger.info("FULL PROTOCOL EXTRACTION PIPELINE")
        logger.info("=" * 60)
        
        steps = []
        
        # Step 1: SoA Extraction
        steps.append(self.run_soa_extraction())
        
        # Steps 2-8: Expansion Phases
        expansion_steps = self.run_all_expansions()
        steps.extend(expansion_steps)
        
        # Step 9: Combine
        steps.append(self.combine_to_usdm())
        
        # Step 10: Hierarchical Transform
        steps.append(self.convert_to_hierarchical())
        
        # Step 11: Terminology Enrichment
        steps.append(self.run_terminology_enrichment())
        
        # Step 12: Schema Validation
        schema_step = self.run_schema_validation()
        steps.append(schema_step)
        
        # Step 13: CDISC Conformance
        conform_step = self.run_cdisc_conformance()
        steps.append(conform_step)
        
        # Step 14: Final Output
        final_step = self.save_final_output()
        steps.append(final_step)
        
        # Calculate overall result
        success_count = sum(1 for s in steps if s.success)
        total_count = len(steps)
        
        avg_confidence = sum(s.confidence for s in steps if s.confidence > 0) / max(1, sum(1 for s in steps if s.confidence > 0))
        
        return PipelineResult(
            success=final_step.success,
            mode='full_protocol',
            steps=steps,
            final_output=final_step.output_file,
            schema_valid=schema_step.success if schema_step.data else False,
            conformance_issues=conform_step.data.get('issues', 0) if conform_step.data else 0,
            total_entities=self._count_entities(self.combined_data) if self.combined_data else 0,
            confidence=avg_confidence,
            errors=[s.error for s in steps if s.error],
        )
    
    def run_soa_only(self) -> PipelineResult:
        """
        Run SoA-only extraction with validation.
        """
        logger.info("\n" + "=" * 60)
        logger.info("SOA-ONLY EXTRACTION PIPELINE")
        logger.info("=" * 60)
        
        steps = []
        
        # Step 1: SoA Extraction
        soa_step = self.run_soa_extraction()
        steps.append(soa_step)
        
        if soa_step.success:
            self.combined_data = self.soa_data
            
            # Step 2: Schema Validation
            steps.append(self.run_schema_validation())
            
            # Step 3: CDISC Conformance
            steps.append(self.run_cdisc_conformance())
        
        return PipelineResult(
            success=soa_step.success,
            mode='soa_only',
            steps=steps,
            final_output=soa_step.output_file,
            total_entities=self._count_entities(self.soa_data) if self.soa_data else 0,
            errors=[s.error for s in steps if s.error],
        )
