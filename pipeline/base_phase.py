"""
Base class for extraction phases.

Each phase implements a common interface for:
- Extraction from PDF
- Saving results
- Combining into USDM structure
- Context parameter requirements
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from extraction.pipeline_context import PipelineContext
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class PhaseProvenance:
    """Provenance metadata captured automatically for every phase run."""
    phase: str = ''
    model: str = ''
    started_at: str = ''
    duration_seconds: float = 0.0
    entity_counts: Dict[str, int] = field(default_factory=dict)
    confidence: Optional[float] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        d: dict = {
            'phase': self.phase,
            'model': self.model,
            'startedAt': self.started_at,
            'durationSeconds': round(self.duration_seconds, 2),
        }
        if self.entity_counts:
            d['entityCounts'] = self.entity_counts
        if self.confidence is not None:
            d['confidence'] = round(self.confidence, 4)
        if self.error:
            d['error'] = self.error
        return d


@dataclass
class PhaseResult:
    """Result from running an extraction phase."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    confidence: Optional[float] = None
    provenance: Optional[PhaseProvenance] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            'success': self.success,
            'error': self.error,
        }
        if self.data is not None:
            if hasattr(self.data, 'to_dict'):
                result['data'] = self.data.to_dict()
            elif isinstance(self.data, dict):
                result['data'] = self.data
        if self.confidence is not None:
            result['confidence'] = self.confidence
        if self.provenance is not None:
            result['provenance'] = self.provenance.to_dict()
        return result


@dataclass
class PhaseConfig:
    """Configuration for a phase."""
    name: str
    display_name: str
    phase_number: int
    output_filename: str
    requires_pdf: bool = True
    requires_soa: bool = False
    optional: bool = False  # If True, ImportError on extractor is OK


class BasePhase(ABC):
    """
    Abstract base class for extraction phases.
    
    Subclasses must implement:
    - config: PhaseConfig property
    - extract(): Run extraction
    - combine(): Merge results into USDM
    
    Optional overrides:
    - get_context_params(): Parameters from pipeline context
    - update_context(): Update pipeline context after extraction
    - calculate_confidence(): Confidence score for results
    """
    
    @property
    @abstractmethod
    def config(self) -> PhaseConfig:
        """Return phase configuration."""
        pass
    
    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        soa_data: Optional[dict] = None,
        **kwargs
    ) -> PhaseResult:
        """
        Run extraction for this phase.
        
        Args:
            pdf_path: Path to protocol PDF
            model: LLM model name
            output_dir: Output directory
            context: Pipeline context with accumulated data
            soa_data: Optional SoA extraction data
            **kwargs: Additional phase-specific parameters
            
        Returns:
            PhaseResult with extraction data
        """
        pass
    
    @abstractmethod
    def combine(
        self,
        result: PhaseResult,
        study_version: dict,
        study_design: dict,
        combined: dict,
        previous_extractions: dict,
    ) -> None:
        """
        Merge extraction results into USDM structure.
        
        Modifies study_version, study_design, and combined in-place.
        
        Args:
            result: PhaseResult from extract()
            study_version: USDM study version dict
            study_design: USDM study design dict
            combined: Root USDM dict
            previous_extractions: Previously saved extraction data
        """
        pass
    
    def get_context_params(self, context: PipelineContext) -> dict:
        """
        Get parameters from pipeline context for this phase.
        
        Override to specify what context data this phase needs.
        Default returns empty dict.
        """
        return {}
    
    def update_context(self, context: PipelineContext, result: PhaseResult) -> None:
        """
        Update pipeline context after successful extraction.
        
        Override to specify how this phase contributes to context.
        Default does nothing.
        """
        pass
    
    def calculate_confidence(self, result: PhaseResult) -> Optional[float]:
        """
        Calculate confidence score for extraction results.
        
        Override to provide phase-specific confidence calculation.
        Default returns None.
        """
        return None
    
    def save_result(self, result: PhaseResult, output_path: str) -> None:
        """
        Save extraction result to file.
        
        Default implementation saves to JSON with standard format.
        """
        import json
        import os
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        output = {
            "success": result.success,
            "pagesUsed": [],
            "modelUsed": "unknown",
        }
        
        if result.data:
            if hasattr(result.data, 'to_dict'):
                output[self.config.name.lower()] = result.data.to_dict()
            elif isinstance(result.data, dict):
                output[self.config.name.lower()] = result.data
            else:
                output["data"] = str(result.data)
        
        if result.error:
            output["error"] = result.error
        if result.confidence is not None:
            output["confidence"] = result.confidence
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    
    def run(
        self,
        pdf_path: str,
        model: str,
        output_dir: str,
        context: PipelineContext,
        usage_tracker: Any = None,
        soa_data: Optional[dict] = None,
        **kwargs
    ) -> PhaseResult:
        """
        Full phase execution: extract, save, update context.
        
        This is the main entry point called by the orchestrator.
        """
        import os
        
        config = self.config
        logger.info(f"\n--- Expansion: {config.display_name} (Phase {config.phase_number}) ---")
        
        # Set usage tracker phase
        if usage_tracker:
            usage_tracker.set_phase(config.name)
        
        # Start provenance tracking
        prov = PhaseProvenance(
            phase=config.name,
            model=model,
            started_at=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        )
        t0 = time.monotonic()
        
        try:
            # Get context parameters
            context_params = self.get_context_params(context)
            
            # Run extraction
            result = self.extract(
                pdf_path=pdf_path,
                model=model,
                output_dir=output_dir,
                context=context,
                soa_data=soa_data,
                **context_params,
                **kwargs
            )
            
            # Calculate confidence
            if result.success and result.data:
                result.confidence = self.calculate_confidence(result)
            
            # Finalize provenance
            prov.duration_seconds = time.monotonic() - t0
            prov.confidence = result.confidence
            prov.error = result.error
            if result.success and result.data:
                prov.entity_counts = self._count_entities(result.data)
            result.provenance = prov
            
            # Save result
            output_path = os.path.join(output_dir, config.output_filename)
            self.save_result(result, output_path)
            
            # Update context
            if result.success and result.data:
                self.update_context(context, result)
                conf_str = f" (\U0001f4ca {result.confidence:.0%})" if result.confidence else ""
                logger.info(f"  \u2713 {config.display_name} extraction{conf_str}")
            else:
                logger.info(f"  \u2717 {config.display_name} extraction failed")
            
            return result
            
        except ImportError as e:
            prov.duration_seconds = time.monotonic() - t0
            prov.error = str(e)
            if config.optional:
                logger.warning(f"  \u2717 {config.display_name} module not available: {e}")
                return PhaseResult(success=False, error=str(e), provenance=prov)
            raise
        except Exception as e:
            prov.duration_seconds = time.monotonic() - t0
            prov.error = str(e)
            logger.error(f"  \u2717 {config.display_name} extraction error: {e}")
            return PhaseResult(success=False, error=str(e), provenance=prov)
    
    @staticmethod
    def _count_entities(data: Any) -> Dict[str, int]:
        """Count entities in extraction result data for provenance."""
        counts: Dict[str, int] = {}
        if data is None:
            return counts
        
        # Handle Pydantic-like schema objects with known list attributes
        obj = data
        if hasattr(obj, '__dict__'):
            for attr_name, attr_val in vars(obj).items():
                if isinstance(attr_val, list) and attr_val:
                    counts[attr_name] = len(attr_val)
                elif isinstance(attr_val, dict) and attr_val:
                    counts[attr_name] = len(attr_val)
        elif isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, list) and val:
                    counts[key] = len(val)
        
        return counts
