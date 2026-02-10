"""
Tests for E14: Phase provenance tracking.

Validates:
- PhaseProvenance dataclass and to_dict()
- PhaseResult includes provenance
- BasePhase.run() auto-captures timing, model, entity counts
- _count_entities works for schema objects, dicts, and None
- PipelineOrchestrator.aggregate_provenance() collects all phases
"""

import time
import pytest
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

from pipeline.base_phase import (
    PhaseProvenance,
    PhaseResult,
    PhaseConfig,
    BasePhase,
)


# ── PhaseProvenance ──────────────────────────────────────────────────

class TestPhaseProvenance:
    """PhaseProvenance dataclass and serialization."""

    def test_defaults(self):
        p = PhaseProvenance()
        assert p.phase == ''
        assert p.model == ''
        assert p.duration_seconds == 0.0
        assert p.entity_counts == {}
        assert p.confidence is None
        assert p.error is None

    def test_to_dict_minimal(self):
        p = PhaseProvenance(phase='metadata', model='gemini-3-flash')
        d = p.to_dict()
        assert d['phase'] == 'metadata'
        assert d['model'] == 'gemini-3-flash'
        assert 'entityCounts' not in d  # empty dict omitted
        assert 'confidence' not in d    # None omitted
        assert 'error' not in d         # None omitted

    def test_to_dict_full(self):
        p = PhaseProvenance(
            phase='eligibility',
            model='gpt-4o',
            started_at='2026-02-10T12:00:00Z',
            duration_seconds=5.678,
            entity_counts={'criteria': 12, 'population': 1},
            confidence=0.85,
            error=None,
        )
        d = p.to_dict()
        assert d['phase'] == 'eligibility'
        assert d['startedAt'] == '2026-02-10T12:00:00Z'
        assert d['durationSeconds'] == 5.68
        assert d['entityCounts'] == {'criteria': 12, 'population': 1}
        assert d['confidence'] == 0.85
        assert 'error' not in d

    def test_to_dict_with_error(self):
        p = PhaseProvenance(phase='test', model='m', error='boom')
        d = p.to_dict()
        assert d['error'] == 'boom'


# ── PhaseResult with provenance ──────────────────────────────────────

class TestPhaseResultProvenance:
    """PhaseResult includes provenance in to_dict()."""

    def test_no_provenance_by_default(self):
        r = PhaseResult(success=True)
        assert r.provenance is None
        d = r.to_dict()
        assert 'provenance' not in d

    def test_provenance_included_in_to_dict(self):
        prov = PhaseProvenance(phase='metadata', model='test')
        r = PhaseResult(success=True, provenance=prov)
        d = r.to_dict()
        assert 'provenance' in d
        assert d['provenance']['phase'] == 'metadata'


# ── _count_entities ──────────────────────────────────────────────────

class TestCountEntities:
    """BasePhase._count_entities static method."""

    def test_none_returns_empty(self):
        assert BasePhase._count_entities(None) == {}

    def test_dict_with_lists(self):
        data = {'criteria': [1, 2, 3], 'scalar': 'x', 'empty': []}
        counts = BasePhase._count_entities(data)
        assert counts['criteria'] == 3
        assert 'scalar' not in counts  # scalars not counted
        assert 'empty' not in counts   # empty lists not counted

    def test_object_with_list_attrs(self):
        @dataclass
        class FakeData:
            titles: List[str] = field(default_factory=list)
            identifiers: List[str] = field(default_factory=list)
            phase: Optional[str] = None

        data = FakeData(titles=['a', 'b'], identifiers=['x'])
        counts = BasePhase._count_entities(data)
        assert counts['titles'] == 2
        assert counts['identifiers'] == 1
        assert 'phase' not in counts

    def test_empty_dict(self):
        assert BasePhase._count_entities({}) == {}


# ── BasePhase.run() provenance capture ───────────────────────────────

class _StubPhase(BasePhase):
    """Minimal concrete phase for testing."""

    @property
    def config(self):
        return PhaseConfig(
            name='StubPhase',
            display_name='Stub Phase',
            phase_number=99,
            output_filename='99_stub.json',
        )

    def extract(self, pdf_path, model, output_dir, context, soa_data=None, **kwargs):
        return PhaseResult(success=True, data={'items': [1, 2, 3]})

    def combine(self, result, study_version, study_design, combined, previous_extractions):
        pass


class _FailingPhase(BasePhase):
    """Phase that raises an exception."""

    @property
    def config(self):
        return PhaseConfig(
            name='FailPhase',
            display_name='Failing Phase',
            phase_number=99,
            output_filename='99_fail.json',
        )

    def extract(self, pdf_path, model, output_dir, context, soa_data=None, **kwargs):
        raise RuntimeError("extraction blew up")

    def combine(self, result, study_version, study_design, combined, previous_extractions):
        pass


class TestBasePhaseRunProvenance:
    """BasePhase.run() automatically captures provenance."""

    def test_successful_run_has_provenance(self, tmp_path):
        phase = _StubPhase()
        ctx = MagicMock()
        ctx.get_summary.return_value = {}

        result = phase.run(
            pdf_path='test.pdf',
            model='gemini-3-flash',
            output_dir=str(tmp_path),
            context=ctx,
        )

        assert result.success is True
        assert result.provenance is not None
        assert result.provenance.phase == 'StubPhase'
        assert result.provenance.model == 'gemini-3-flash'
        assert result.provenance.duration_seconds >= 0
        assert result.provenance.started_at.endswith('Z')
        assert result.provenance.entity_counts == {'items': 3}
        assert result.provenance.error is None

    def test_failed_run_has_provenance(self, tmp_path):
        phase = _FailingPhase()
        ctx = MagicMock()
        ctx.get_summary.return_value = {}

        result = phase.run(
            pdf_path='test.pdf',
            model='gpt-4o',
            output_dir=str(tmp_path),
            context=ctx,
        )

        assert result.success is False
        assert result.provenance is not None
        assert result.provenance.phase == 'FailPhase'
        assert result.provenance.model == 'gpt-4o'
        assert result.provenance.error is not None
        assert 'blew up' in result.provenance.error
        assert result.provenance.duration_seconds >= 0


# ── PipelineOrchestrator.aggregate_provenance ────────────────────────

class TestAggregateProvenance:
    """Orchestrator aggregates provenance from all phases."""

    def test_aggregate_empty(self):
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        prov = orch.aggregate_provenance()
        assert prov['totalPhases'] == 0
        assert prov['phases'] == []

    def test_aggregate_with_results(self):
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        orch._results = {
            'metadata': PhaseResult(
                success=True,
                provenance=PhaseProvenance(
                    phase='Metadata', model='m', duration_seconds=2.5,
                    entity_counts={'titles': 3},
                ),
            ),
            'eligibility': PhaseResult(
                success=True,
                provenance=PhaseProvenance(
                    phase='Eligibility', model='m', duration_seconds=4.1,
                    entity_counts={'criteria': 10},
                ),
            ),
            '_pipeline_context': MagicMock(),  # should be skipped
        }
        prov = orch.aggregate_provenance()
        assert prov['totalPhases'] == 2
        assert prov['succeededPhases'] == 2
        assert prov['totalDurationSeconds'] == 6.6
        assert len(prov['phases']) == 2

    def test_aggregate_counts_failures(self):
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        orch._results = {
            'ok': PhaseResult(
                success=True,
                provenance=PhaseProvenance(phase='ok', model='m', duration_seconds=1),
            ),
            'fail': PhaseResult(
                success=False,
                provenance=PhaseProvenance(
                    phase='fail', model='m', duration_seconds=0.5, error='boom',
                ),
            ),
        }
        prov = orch.aggregate_provenance()
        assert prov['totalPhases'] == 2
        assert prov['succeededPhases'] == 1

    def test_save_provenance(self, tmp_path):
        from pipeline.orchestrator import PipelineOrchestrator
        import json

        orch = PipelineOrchestrator()
        orch._results = {
            'test': PhaseResult(
                success=True,
                provenance=PhaseProvenance(phase='test', model='m', duration_seconds=1),
            ),
        }
        path = orch.save_provenance(str(tmp_path))
        assert path.endswith('extraction_provenance.json')

        with open(path, 'r') as f:
            data = json.load(f)
        assert data['totalPhases'] == 1
        assert data['phases'][0]['phase'] == 'test'
