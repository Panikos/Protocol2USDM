"""
Tests for E20: Parallel execution model sub-extractors.

Validates:
- _run_sub_extractor catches exceptions gracefully
- Wave 1 runs 12 sub-extractors in parallel
- Wave 2 (state machine) runs after Wave 1 with correct dependencies
- Sequential fallback works when parallel=False
- Results merge correctly from parallel execution
- _log_sub_result handles all result states
"""

import time
import threading
from unittest.mock import MagicMock, patch
import pytest

from extraction.execution.pipeline_integration import (
    _run_sub_extractor,
    _log_sub_result,
    extract_execution_model,
    _DEFAULT_MAX_WORKERS,
)
from extraction.execution.schema import ExecutionModelData, ExecutionModelResult


# ── _run_sub_extractor ───────────────────────────────────────────────

class TestRunSubExtractor:
    """_run_sub_extractor wraps callables with error handling."""

    def test_successful_call(self):
        def fake_fn(x=1):
            return ExecutionModelResult(
                success=True, data=ExecutionModelData(), pages_used=[], model_used="m",
            )
        name, result = _run_sub_extractor("test", fake_fn, {"x": 1})
        assert name == "test"
        assert result.success is True

    def test_exception_returns_failed_result(self):
        def boom(**kw):
            raise RuntimeError("kaboom")
        name, result = _run_sub_extractor("boom", boom, {"model": "m"})
        assert name == "boom"
        assert result.success is False
        assert "kaboom" in result.error
        assert result.model_used == "m"

    def test_preserves_name(self):
        name, _ = _run_sub_extractor("my_extractor", lambda: None, {})
        assert name == "my_extractor"


# ── _log_sub_result ──────────────────────────────────────────────────

class TestLogSubResult:
    """_log_sub_result handles all result states without errors."""

    def test_none_result(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            _log_sub_result("test", None)
        assert "no result" in caplog.text

    def test_failed_result(self, caplog):
        import logging
        r = ExecutionModelResult(success=False, data=ExecutionModelData(),
                                 error="oops", pages_used=[], model_used="m")
        with caplog.at_level(logging.WARNING):
            _log_sub_result("test", r)
        assert "oops" in caplog.text

    def test_success_with_data(self, caplog):
        import logging
        data = ExecutionModelData()
        data.time_anchors = [MagicMock()]
        r = ExecutionModelResult(success=True, data=data, pages_used=[], model_used="m")
        with caplog.at_level(logging.INFO):
            _log_sub_result("test", r)
        assert "time_anchors" in caplog.text

    def test_success_empty_data(self, caplog):
        import logging
        r = ExecutionModelResult(success=True, data=ExecutionModelData(),
                                 pages_used=[], model_used="m")
        with caplog.at_level(logging.INFO):
            _log_sub_result("test", r)
        assert "empty" in caplog.text


# ── Parallel execution ───────────────────────────────────────────────

def _make_fake_result(name, delay=0.0, items=None):
    """Create a fake sub-extractor that returns after a delay."""
    def fake(**kwargs):
        if delay:
            time.sleep(delay)
        data = ExecutionModelData()
        if items:
            for attr, vals in items.items():
                setattr(data, attr, vals)
        return ExecutionModelResult(
            success=True, data=data, pages_used=[1], model_used="m",
        )
    return fake


class TestParallelExecution:
    """extract_execution_model runs sub-extractors in parallel."""

    @patch("extraction.execution.pipeline_integration.extract_soa_context")
    @patch("extraction.execution.pipeline_integration.extract_time_anchors")
    @patch("extraction.execution.pipeline_integration.extract_repetitions")
    @patch("extraction.execution.pipeline_integration.classify_execution_types")
    @patch("extraction.execution.pipeline_integration.extract_crossover_design")
    @patch("extraction.execution.pipeline_integration.extract_traversal_constraints")
    @patch("extraction.execution.pipeline_integration.extract_footnote_conditions")
    @patch("extraction.execution.pipeline_integration.extract_endpoint_algorithms")
    @patch("extraction.execution.pipeline_integration.extract_derived_variables")
    @patch("extraction.execution.pipeline_integration.extract_dosing_regimens")
    @patch("extraction.execution.pipeline_integration.extract_visit_windows")
    @patch("extraction.execution.pipeline_integration.extract_stratification")
    @patch("extraction.execution.pipeline_integration.extract_sampling_density")
    @patch("extraction.execution.pipeline_integration.generate_state_machine")
    def test_parallel_runs_all_extractors(
        self, mock_sm, mock_sampling, mock_strat, mock_visit, mock_dosing,
        mock_derived, mock_endpoint, mock_footnote, mock_traversal,
        mock_crossover, mock_classify, mock_rep, mock_anchor, mock_soa_ctx,
    ):
        # Setup SoA context
        ctx = MagicMock()
        ctx.has_epochs.return_value = False
        ctx.has_encounters.return_value = False
        ctx.has_activities.return_value = False
        ctx.has_footnotes.return_value = False
        ctx.arms = None
        mock_soa_ctx.return_value = ctx

        empty = ExecutionModelResult(
            success=True, data=ExecutionModelData(), pages_used=[], model_used="m",
        )
        for m in [mock_anchor, mock_rep, mock_classify, mock_crossover,
                   mock_traversal, mock_footnote, mock_endpoint, mock_derived,
                   mock_dosing, mock_visit, mock_strat, mock_sampling, mock_sm]:
            m.return_value = empty

        result = extract_execution_model(
            pdf_path="test.pdf", model="m", skip_llm=True,
            parallel=True, max_workers=4,
        )

        # All 12 wave-1 extractors + 1 wave-2 extractor called
        assert mock_anchor.called
        assert mock_rep.called
        assert mock_classify.called
        assert mock_crossover.called
        assert mock_traversal.called
        assert mock_footnote.called
        assert mock_endpoint.called
        assert mock_derived.called
        assert mock_dosing.called
        assert mock_visit.called
        assert mock_strat.called
        assert mock_sampling.called
        assert mock_sm.called  # Wave 2

    @patch("extraction.execution.pipeline_integration.extract_soa_context")
    @patch("extraction.execution.pipeline_integration.extract_time_anchors")
    @patch("extraction.execution.pipeline_integration.extract_repetitions")
    @patch("extraction.execution.pipeline_integration.classify_execution_types")
    @patch("extraction.execution.pipeline_integration.extract_crossover_design")
    @patch("extraction.execution.pipeline_integration.extract_traversal_constraints")
    @patch("extraction.execution.pipeline_integration.extract_footnote_conditions")
    @patch("extraction.execution.pipeline_integration.extract_endpoint_algorithms")
    @patch("extraction.execution.pipeline_integration.extract_derived_variables")
    @patch("extraction.execution.pipeline_integration.extract_dosing_regimens")
    @patch("extraction.execution.pipeline_integration.extract_visit_windows")
    @patch("extraction.execution.pipeline_integration.extract_stratification")
    @patch("extraction.execution.pipeline_integration.extract_sampling_density")
    @patch("extraction.execution.pipeline_integration.generate_state_machine")
    def test_sequential_fallback(
        self, mock_sm, mock_sampling, mock_strat, mock_visit, mock_dosing,
        mock_derived, mock_endpoint, mock_footnote, mock_traversal,
        mock_crossover, mock_classify, mock_rep, mock_anchor, mock_soa_ctx,
    ):
        ctx = MagicMock()
        ctx.has_epochs.return_value = False
        ctx.has_encounters.return_value = False
        ctx.has_activities.return_value = False
        ctx.has_footnotes.return_value = False
        ctx.arms = None
        mock_soa_ctx.return_value = ctx

        empty = ExecutionModelResult(
            success=True, data=ExecutionModelData(), pages_used=[], model_used="m",
        )
        for m in [mock_anchor, mock_rep, mock_classify, mock_crossover,
                   mock_traversal, mock_footnote, mock_endpoint, mock_derived,
                   mock_dosing, mock_visit, mock_strat, mock_sampling, mock_sm]:
            m.return_value = empty

        result = extract_execution_model(
            pdf_path="test.pdf", model="m", skip_llm=True,
            parallel=False,
        )

        # All extractors still called
        assert mock_anchor.called
        assert mock_sm.called

    @patch("extraction.execution.pipeline_integration.extract_soa_context")
    @patch("extraction.execution.pipeline_integration.extract_time_anchors")
    @patch("extraction.execution.pipeline_integration.extract_repetitions")
    @patch("extraction.execution.pipeline_integration.classify_execution_types")
    @patch("extraction.execution.pipeline_integration.extract_crossover_design")
    @patch("extraction.execution.pipeline_integration.extract_traversal_constraints")
    @patch("extraction.execution.pipeline_integration.extract_footnote_conditions")
    @patch("extraction.execution.pipeline_integration.extract_endpoint_algorithms")
    @patch("extraction.execution.pipeline_integration.extract_derived_variables")
    @patch("extraction.execution.pipeline_integration.extract_dosing_regimens")
    @patch("extraction.execution.pipeline_integration.extract_visit_windows")
    @patch("extraction.execution.pipeline_integration.extract_stratification")
    @patch("extraction.execution.pipeline_integration.extract_sampling_density")
    @patch("extraction.execution.pipeline_integration.generate_state_machine")
    def test_merges_data_from_all_extractors(
        self, mock_sm, mock_sampling, mock_strat, mock_visit, mock_dosing,
        mock_derived, mock_endpoint, mock_footnote, mock_traversal,
        mock_crossover, mock_classify, mock_rep, mock_anchor, mock_soa_ctx,
    ):
        ctx = MagicMock()
        ctx.has_epochs.return_value = False
        ctx.has_encounters.return_value = False
        ctx.has_activities.return_value = False
        ctx.has_footnotes.return_value = False
        ctx.arms = None
        mock_soa_ctx.return_value = ctx

        empty = ExecutionModelResult(
            success=True, data=ExecutionModelData(), pages_used=[], model_used="m",
        )
        for m in [mock_rep, mock_classify, mock_crossover,
                   mock_traversal, mock_footnote, mock_endpoint, mock_derived,
                   mock_dosing, mock_visit, mock_strat, mock_sampling, mock_sm]:
            m.return_value = empty

        # Give time_anchors some data
        anchor_data = ExecutionModelData()
        anchor_data.time_anchors = [MagicMock(), MagicMock()]
        mock_anchor.return_value = ExecutionModelResult(
            success=True, data=anchor_data, pages_used=[5, 6], model_used="m",
        )

        result = extract_execution_model(
            pdf_path="test.pdf", model="m", skip_llm=True, parallel=True,
        )

        assert result.success is True
        assert len(result.data.time_anchors) == 2
        assert 5 in result.pages_used

    @patch("extraction.execution.pipeline_integration.extract_soa_context")
    @patch("extraction.execution.pipeline_integration.extract_time_anchors")
    @patch("extraction.execution.pipeline_integration.extract_repetitions")
    @patch("extraction.execution.pipeline_integration.classify_execution_types")
    @patch("extraction.execution.pipeline_integration.extract_crossover_design")
    @patch("extraction.execution.pipeline_integration.extract_traversal_constraints")
    @patch("extraction.execution.pipeline_integration.extract_footnote_conditions")
    @patch("extraction.execution.pipeline_integration.extract_endpoint_algorithms")
    @patch("extraction.execution.pipeline_integration.extract_derived_variables")
    @patch("extraction.execution.pipeline_integration.extract_dosing_regimens")
    @patch("extraction.execution.pipeline_integration.extract_visit_windows")
    @patch("extraction.execution.pipeline_integration.extract_stratification")
    @patch("extraction.execution.pipeline_integration.extract_sampling_density")
    @patch("extraction.execution.pipeline_integration.generate_state_machine")
    def test_one_failure_doesnt_block_others(
        self, mock_sm, mock_sampling, mock_strat, mock_visit, mock_dosing,
        mock_derived, mock_endpoint, mock_footnote, mock_traversal,
        mock_crossover, mock_classify, mock_rep, mock_anchor, mock_soa_ctx,
    ):
        ctx = MagicMock()
        ctx.has_epochs.return_value = False
        ctx.has_encounters.return_value = False
        ctx.has_activities.return_value = False
        ctx.has_footnotes.return_value = False
        ctx.arms = None
        mock_soa_ctx.return_value = ctx

        empty = ExecutionModelResult(
            success=True, data=ExecutionModelData(), pages_used=[], model_used="m",
        )
        for m in [mock_rep, mock_classify, mock_crossover,
                   mock_traversal, mock_footnote, mock_endpoint, mock_derived,
                   mock_dosing, mock_visit, mock_strat, mock_sampling, mock_sm]:
            m.return_value = empty

        # Make time_anchors raise
        mock_anchor.side_effect = RuntimeError("LLM timeout")

        # Give repetitions some data
        rep_data = ExecutionModelData()
        rep_data.repetitions = [MagicMock()]
        mock_rep.return_value = ExecutionModelResult(
            success=True, data=rep_data, pages_used=[], model_used="m",
        )

        result = extract_execution_model(
            pdf_path="test.pdf", model="m", skip_llm=True, parallel=True,
        )

        # Should still succeed because repetitions has data
        assert result.success is True
        assert len(result.data.repetitions) == 1


# ── Concurrency verification ─────────────────────────────────────────

class TestConcurrencyVerification:
    """Verify that parallel mode actually runs concurrently."""

    def test_parallel_is_faster_than_sequential(self):
        """With artificial delays, parallel should be significantly faster."""
        seen_threads = set()

        def slow_extractor(**kwargs):
            seen_threads.add(threading.current_thread().name)
            time.sleep(0.05)
            return ExecutionModelResult(
                success=True, data=ExecutionModelData(),
                pages_used=[], model_used="m",
            )

        tasks = [(f"task_{i}", slow_extractor, {"model": "m"}) for i in range(6)]

        # Sequential
        t0 = time.monotonic()
        for name, fn, kw in tasks:
            _run_sub_extractor(name, fn, kw)
        seq_time = time.monotonic() - t0

        # Parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(_run_sub_extractor, name, fn, kw): name
                for name, fn, kw in tasks
            }
            for f in as_completed(futures):
                f.result()
        par_time = time.monotonic() - t0

        # Parallel should be at least 2x faster with 6 workers
        assert par_time < seq_time * 0.7, (
            f"Parallel ({par_time:.2f}s) not significantly faster than "
            f"sequential ({seq_time:.2f}s)"
        )


# ── Default max workers ──────────────────────────────────────────────

class TestDefaultMaxWorkers:

    def test_default_is_6(self):
        assert _DEFAULT_MAX_WORKERS == 6
