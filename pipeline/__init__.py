"""
Protocol2USDM Pipeline Package

Contains the full protocol extraction pipeline that produces
golden standard USDM output for computational execution.
"""

from .protocol_pipeline import (
    ProtocolExtractionPipeline,
    PipelineResult,
    PipelineStep,
)

__all__ = [
    'ProtocolExtractionPipeline',
    'PipelineResult',
    'PipelineStep',
]
