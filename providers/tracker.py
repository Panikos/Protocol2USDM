"""
Token Usage Tracker

Thread-safe tracking of cumulative token usage across all LLM calls,
with per-phase breakdown and cost estimation.
"""

import logging
import threading
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TokenUsageTracker:
    """
    Tracks cumulative token usage across all LLM calls.
    
    Thread-safe: Uses thread-local storage for current_phase to avoid
    race conditions when phases run in parallel with ThreadPoolExecutor.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._thread_local = threading.local()
        self.reset()
    
    def reset(self):
        """Reset all counters."""
        with self._lock:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.call_count = 0
            self.calls_by_phase = {}
        self._thread_local.current_phase = "unknown"
    
    @property
    def current_phase(self) -> str:
        """Get current phase for this thread."""
        return getattr(self._thread_local, 'current_phase', 'unknown')
    
    def set_phase(self, phase: str):
        """Set the current extraction phase for tracking (thread-local)."""
        self._thread_local.current_phase = phase
    
    def add_usage(self, input_tokens: int, output_tokens: int, phase: str = None):
        """
        Add usage from an LLM call.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens  
            phase: Optional explicit phase name. If None, uses thread-local current_phase.
        """
        # Use explicit phase if provided, otherwise thread-local
        phase_name = phase if phase is not None else self.current_phase
        
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.call_count += 1
            
            if phase_name not in self.calls_by_phase:
                self.calls_by_phase[phase_name] = {"input": 0, "output": 0, "calls": 0}
            self.calls_by_phase[phase_name]["input"] += input_tokens
            self.calls_by_phase[phase_name]["output"] += output_tokens
            self.calls_by_phase[phase_name]["calls"] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get usage summary (thread-safe)."""
        with self._lock:
            return {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_input_tokens + self.total_output_tokens,
                "call_count": self.call_count,
                "by_phase": dict(self.calls_by_phase),  # Copy to avoid mutation
            }
    
    def print_summary(self, model: str = "claude-opus-4-5"):
        """Print a formatted summary with cost estimates (thread-safe)."""
        # Pricing per million tokens (as of Jan 2025)
        pricing = {
            # Claude models
            "claude-opus-4-5": (15.0, 75.0),
            "claude-sonnet-4": (3.0, 15.0),
            "claude-3-5-sonnet": (3.0, 15.0),
            # Gemini models (much cheaper)
            "gemini-2.5-pro": (1.25, 10.0),
            "gemini-2.5-flash": (0.075, 0.30),
            "gemini-3-flash": (0.50, 3.00),
            "gemini-3-flash-preview": (0.50, 3.00),
            # OpenAI models
            "gpt-4o": (2.50, 10.0),
            "gpt-4o-mini": (0.15, 0.60),
        }
        # Normalize model name for lookup (handle variations)
        model_lower = model.lower().replace("_", "-")
        input_rate, output_rate = pricing.get(model_lower, pricing.get(model, (1.0, 4.0)))
        
        # Get thread-safe snapshot of data
        with self._lock:
            total_input = self.total_input_tokens
            total_output = self.total_output_tokens
            call_count = self.call_count
            phases = dict(self.calls_by_phase)
        
        input_cost = (total_input / 1_000_000) * input_rate
        output_cost = (total_output / 1_000_000) * output_rate
        total_cost = input_cost + output_cost
        
        lines = [
            "",
            "=" * 70,
            "TOKEN USAGE SUMMARY",
            "=" * 70,
            f"Model: {model}",
            f"Total LLM Calls: {call_count}",
            "",
            "By Phase:",
            "-" * 70,
        ]
        for phase, data in phases.items():
            phase_cost = (data['input']/1e6 * input_rate) + (data['output']/1e6 * output_rate)
            lines.append(f"  {phase:40} {data['input']:>8,} in / {data['output']:>7,} out  ${phase_cost:.2f}")
        lines += [
            "-" * 70,
            "",
            f"Total Input Tokens:  {total_input:>12,}",
            f"Total Output Tokens: {total_output:>12,}",
            f"Total Tokens:        {total_input + total_output:>12,}",
            "",
            f"Input Cost:  ${input_cost:>8.2f}  (@${input_rate}/1M)",
            f"Output Cost: ${output_cost:>8.2f}  (@${output_rate}/1M)",
            f"TOTAL COST:  ${total_cost:>8.2f}",
            "=" * 70,
        ]
        logger.info("\n".join(lines))


# Global tracker instance
usage_tracker = TokenUsageTracker()


def create_tracker() -> TokenUsageTracker:
    """Create a fresh TokenUsageTracker instance (useful in tests for isolation)."""
    return TokenUsageTracker()


def set_usage_tracker(tracker: TokenUsageTracker) -> None:
    """Inject a custom usage tracker globally (useful in tests)."""
    global usage_tracker
    usage_tracker = tracker


def reset_usage_tracker() -> None:
    """Reset the global usage tracker to a fresh instance."""
    global usage_tracker
    usage_tracker = TokenUsageTracker()
