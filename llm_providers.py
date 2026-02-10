"""
LLM Provider Abstraction Layer — Backward Compatibility Shim

All provider implementations have been moved to the providers/ package.
This module re-exports everything for backward compatibility.

Usage:
    from llm_providers import LLMProviderFactory, LLMConfig, usage_tracker
    # or use the new package directly:
    from providers import LLMProviderFactory, LLMConfig, usage_tracker
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Re-export everything from providers/ package for backward compatibility
from providers import (
    LLMConfig,
    LLMResponse,
    LLMProvider,
    StreamChunk,
    StreamCallback,
    TokenUsageTracker,
    usage_tracker,
    OpenAIProvider,
    GeminiProvider,
    ClaudeProvider,
    LLMProviderFactory,
    _retry_with_backoff,
)

__all__ = [
    "LLMConfig",
    "LLMResponse",
    "LLMProvider",
    "StreamChunk",
    "StreamCallback",
    "TokenUsageTracker",
    "usage_tracker",
    "OpenAIProvider",
    "GeminiProvider",
    "ClaudeProvider",
    "LLMProviderFactory",
    "_retry_with_backoff",
]
