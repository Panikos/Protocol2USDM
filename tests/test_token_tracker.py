"""
Unit tests for TokenUsageTracker (providers/tracker.py).

Tests thread safety, per-phase tracking, cost estimation, and summary generation.
"""

import threading
import pytest
from providers.tracker import TokenUsageTracker


class TestTokenUsageTracker:
    """Test suite for TokenUsageTracker."""

    def setup_method(self):
        """Fresh tracker for each test."""
        self.tracker = TokenUsageTracker()

    def test_initial_state(self):
        """Tracker starts with zero counters."""
        summary = self.tracker.get_summary()
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["total_tokens"] == 0
        assert summary["call_count"] == 0
        assert summary["by_phase"] == {}

    def test_add_usage_basic(self):
        """Single add_usage call updates totals."""
        self.tracker.set_phase("metadata")
        self.tracker.add_usage(100, 50)
        summary = self.tracker.get_summary()
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
        assert summary["total_tokens"] == 150
        assert summary["call_count"] == 1

    def test_add_usage_accumulates(self):
        """Multiple calls accumulate correctly."""
        self.tracker.set_phase("narrative")
        self.tracker.add_usage(100, 50)
        self.tracker.add_usage(200, 100)
        self.tracker.add_usage(300, 150)
        summary = self.tracker.get_summary()
        assert summary["total_input_tokens"] == 600
        assert summary["total_output_tokens"] == 300
        assert summary["total_tokens"] == 900
        assert summary["call_count"] == 3

    def test_per_phase_tracking(self):
        """Usage is tracked per phase."""
        self.tracker.set_phase("metadata")
        self.tracker.add_usage(100, 50)
        self.tracker.set_phase("narrative")
        self.tracker.add_usage(200, 100)
        self.tracker.add_usage(300, 150)
        self.tracker.set_phase("eligibility")
        self.tracker.add_usage(150, 75)

        summary = self.tracker.get_summary()
        assert summary["by_phase"]["metadata"] == {"input": 100, "output": 50, "calls": 1}
        assert summary["by_phase"]["narrative"] == {"input": 500, "output": 250, "calls": 2}
        assert summary["by_phase"]["eligibility"] == {"input": 150, "output": 75, "calls": 1}

    def test_explicit_phase_parameter(self):
        """add_usage with explicit phase overrides current_phase."""
        self.tracker.set_phase("metadata")
        self.tracker.add_usage(100, 50, phase="soa")
        summary = self.tracker.get_summary()
        assert "soa" in summary["by_phase"]
        assert "metadata" not in summary["by_phase"]

    def test_default_phase_is_unknown(self):
        """Without set_phase, usage goes to 'unknown'."""
        self.tracker.add_usage(100, 50)
        summary = self.tracker.get_summary()
        assert "unknown" in summary["by_phase"]

    def test_reset(self):
        """Reset clears all counters."""
        self.tracker.set_phase("test")
        self.tracker.add_usage(100, 50)
        self.tracker.reset()
        summary = self.tracker.get_summary()
        assert summary["total_tokens"] == 0
        assert summary["call_count"] == 0
        assert summary["by_phase"] == {}

    def test_thread_safety_parallel_writes(self):
        """Concurrent add_usage calls from multiple threads produce correct totals."""
        calls_per_thread = 100
        num_threads = 10

        def worker(phase_name):
            self.tracker.set_phase(phase_name)
            for _ in range(calls_per_thread):
                self.tracker.add_usage(10, 5)

        threads = [
            threading.Thread(target=worker, args=(f"phase_{i}",))
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = self.tracker.get_summary()
        expected_calls = calls_per_thread * num_threads
        assert summary["call_count"] == expected_calls
        assert summary["total_input_tokens"] == 10 * expected_calls
        assert summary["total_output_tokens"] == 5 * expected_calls

    def test_thread_local_phase(self):
        """Each thread has its own current_phase (thread-local)."""
        phases_seen = {}

        def worker(phase_name):
            self.tracker.set_phase(phase_name)
            self.tracker.add_usage(10, 5)
            phases_seen[phase_name] = self.tracker.current_phase

        threads = [
            threading.Thread(target=worker, args=(f"phase_{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have seen its own phase
        for i in range(5):
            assert phases_seen[f"phase_{i}"] == f"phase_{i}"

    def test_get_summary_returns_copy(self):
        """get_summary returns a copy, not a reference to internal state."""
        self.tracker.set_phase("test")
        self.tracker.add_usage(100, 50)
        summary1 = self.tracker.get_summary()
        self.tracker.add_usage(200, 100)
        summary2 = self.tracker.get_summary()
        assert summary1["total_tokens"] == 150
        assert summary2["total_tokens"] == 450

    def test_print_summary_does_not_crash(self, capsys):
        """print_summary runs without error for various models."""
        self.tracker.set_phase("test")
        self.tracker.add_usage(1000, 500)
        # Should not raise for any model
        for model in ["gpt-4o", "gemini-3-flash", "claude-opus-4-5", "unknown-model"]:
            self.tracker.print_summary(model=model)
        captured = capsys.readouterr()
        assert "TOKEN USAGE SUMMARY" in captured.out

    def test_cost_calculation_gemini(self, capsys):
        """Verify cost calculation for gemini-3-flash pricing."""
        self.tracker.set_phase("test")
        self.tracker.add_usage(1_000_000, 1_000_000)
        self.tracker.print_summary(model="gemini-3-flash")
        captured = capsys.readouterr()
        # gemini-3-flash: $0.50/1M input + $3.00/1M output = $3.50
        assert "0.50" in captured.out  # input cost
        assert "3.00" in captured.out  # output cost
        assert "3.50" in captured.out  # total cost
