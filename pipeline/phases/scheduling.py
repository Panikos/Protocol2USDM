"""Scheduling logic extraction phase."""

from typing import Optional
import logging
from ..base_phase import BasePhase, PhaseConfig, PhaseResult
from ..phase_registry import register_phase
from extraction.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


def _build_scheduling_context(
    epochs: list = None,
    encounters: list = None,
    arms: list = None,
) -> str:
    """Build a compact upstream context summary for LLM grounding."""
    parts = []
    if epochs:
        names = [e.get('name', '') if isinstance(e, dict) else str(e) for e in epochs]
        parts.append(f"Study Epochs: {', '.join(n for n in names if n)}")
    if encounters:
        names = [e.get('name', '') if isinstance(e, dict) else str(e) for e in encounters]
        parts.append(f"Encounters/Visits: {', '.join(n for n in names if n)}")
    if arms:
        names = [a.get('name', '') if isinstance(a, dict) else str(a) for a in arms]
        parts.append(f"Study Arms: {', '.join(n for n in names if n)}")
    return '\n'.join(parts) if parts else ''


class SchedulingPhase(BasePhase):
    """Extract scheduling logic, timings, and conditions."""
    
    @property
    def config(self) -> PhaseConfig:
        return PhaseConfig(
            name="Scheduling",
            display_name="Scheduling Logic",
            phase_number=11,
            output_filename="10_scheduling_logic.json",
            optional=True,
        )
    
    def get_context_params(self, context: PipelineContext) -> dict:
        params = {}
        if context.has_epochs():
            params['existing_epochs'] = context.epochs
        if context.has_encounters():
            params['existing_encounters'] = context.encounters
        if context.has_arms():
            params['existing_arms'] = context.arms
        return params
    
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        existing_epochs: Optional[list] = None,
        existing_encounters: Optional[list] = None,
        existing_arms: Optional[list] = None,
        **kwargs
    ) -> PhaseResult:
        from extraction.scheduling import extract_scheduling
        
        upstream_context = _build_scheduling_context(
            existing_epochs, existing_encounters, existing_arms
        )
        
        result = extract_scheduling(
            pdf_path, model=model, output_dir=output_dir,
            upstream_context=upstream_context,
        )
        
        return PhaseResult(
            success=result.success,
            data=result.data if result.success else None,
            error=result.error if hasattr(result, 'error') else None,
        )
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        if result.data:
            context.update_from_scheduling(result.data.to_dict())
    
    def run(self, *args, **kwargs) -> PhaseResult:
        """Override run to log timing count on success."""
        result = super().run(*args, **kwargs)
        if result.success and result.data:
            data_dict = result.data.to_dict()
            count = data_dict.get('summary', {}).get('timingCount', 0)
            logger.info(f"    Timings: {count}")
        return result
    
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """Add scheduling to scheduleTimeline and study_version."""
        scheduling_added = False
        data_dict = None
        
        if result.success and result.data:
            data_dict = result.data.to_dict()
            scheduling_added = True
        elif previous_extractions.get('scheduling'):
            prev = previous_extractions['scheduling']
            if prev.get('scheduling'):
                data_dict = prev['scheduling']
        
        if not data_dict:
            return
        
        # Timings and exits go into scheduleTimeline
        if study_design.get('scheduleTimelines'):
            main_timeline = study_design['scheduleTimelines'][0]
            
            if data_dict.get('timings'):
                if 'timings' not in main_timeline:
                    main_timeline['timings'] = []
                main_timeline['timings'].extend(data_dict['timings'])
                
                # Link timingId on ScheduledActivityInstances
                linked = self._link_timing_ids_to_instances(study_design)
                if linked > 0:
                    logger.info(f"    Linked {linked} instances to timings")
            
            if data_dict.get('scheduleTimelineExits'):
                if 'exits' not in main_timeline:
                    main_timeline['exits'] = []
                main_timeline['exits'].extend(data_dict['scheduleTimelineExits'])
        
        # Conditions go to studyVersion
        if data_dict.get('conditions'):
            study_version["conditions"] = data_dict['conditions']
        
        # TransitionRules stay at root
        if data_dict.get('transitionRules'):
            combined["transitionRules"] = data_dict['transitionRules']
    
    def _link_timing_ids_to_instances(self, study_design: dict) -> int:
        """Link timingId on ScheduledActivityInstances based on encounter matching."""
        import re
        
        if not study_design.get('scheduleTimelines'):
            return 0
        
        main_timeline = study_design['scheduleTimelines'][0]
        instances = main_timeline.get('instances', [])
        timings = main_timeline.get('timings', [])
        
        if not instances or not timings:
            return 0
        
        def extract_day_numbers(text: str) -> set:
            if not text:
                return set()
            matches = re.findall(r'day\s*(-?\d+)', text.lower())
            return set(int(m) for m in matches)
        
        def extract_visit_number(text: str) -> int:
            if not text:
                return None
            match = re.search(r'(?:visit|v)\s*(\d+)', text.lower())
            return int(match.group(1)) if match else None
        
        # Build encounter ID -> info lookup
        enc_id_to_info = {}
        for enc in study_design.get('encounters', []):
            enc_id = enc.get('id', '')
            enc_name = enc.get('name', '')
            if enc_id:
                enc_id_to_info[enc_id] = {
                    'name': enc_name.lower().strip(),
                    'days': extract_day_numbers(enc_name),
                    'visit': extract_visit_number(enc_name),
                }
        
        # Build timing lookups
        timing_by_name = {}
        timing_by_day = {}
        timing_by_visit = {}
        
        for timing in timings:
            timing_id = timing.get('id', '')
            if not timing_id:
                continue
            
            name = timing.get('name', '').lower().strip()
            value_label = timing.get('valueLabel', '').lower().strip()
            
            if name:
                timing_by_name[name] = timing_id
            if value_label:
                timing_by_name[value_label] = timing_id
            
            for text in [name, value_label]:
                for day in extract_day_numbers(text):
                    timing_by_day[day] = timing_id
            
            value = timing.get('value')
            if isinstance(value, str) and value.startswith('P') and 'D' in value:
                match = re.search(r'P(-?\d+)D', value)
                if match:
                    timing_by_day[int(match.group(1))] = timing_id
            
            for text in [name, value_label]:
                visit = extract_visit_number(text)
                if visit:
                    timing_by_visit[visit] = timing_id
        
        # Link instances to timings
        linked_count = 0
        for instance in instances:
            if instance.get('timingId'):
                continue
            
            enc_id = instance.get('encounterId', '')
            enc_info = enc_id_to_info.get(enc_id, {})
            
            if not enc_info:
                continue
            
            timing_id = None
            
            # Strategy 1: Exact name match
            if enc_info['name'] in timing_by_name:
                timing_id = timing_by_name[enc_info['name']]
            
            # Strategy 2: Day number match
            if not timing_id and enc_info['days']:
                for day in enc_info['days']:
                    if day in timing_by_day:
                        timing_id = timing_by_day[day]
                        break
            
            # Strategy 3: Visit number match
            if not timing_id and enc_info['visit']:
                if enc_info['visit'] in timing_by_visit:
                    timing_id = timing_by_visit[enc_info['visit']]
            
            if timing_id:
                instance['timingId'] = timing_id
                linked_count += 1
        
        return linked_count


# Register the phase
register_phase(SchedulingPhase())
