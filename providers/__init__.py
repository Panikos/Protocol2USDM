"""
LLM Provider Package

Provides a unified interface for multiple LLM providers (OpenAI, Google Gemini, Anthropic Claude).

Usage:
    from providers import LLMProviderFactory, LLMConfig, usage_tracker
    
    provider = LLMProviderFactory.create("openai", model="gpt-4o")
    response = provider.generate(messages, LLMConfig(json_mode=True))
"""

from .base import LLMConfig, LLMResponse, LLMProvider, StreamChunk, StreamCallback, _retry_with_backoff
from .tracker import TokenUsageTracker, usage_tracker
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .claude_provider import ClaudeProvider
from .factory import LLMProviderFactory

__all__ = [
    # Base classes
    "LLMConfig",
    "LLMResponse",
    "LLMProvider",
    "StreamChunk",
    "StreamCallback",
    # Tracker
    "TokenUsageTracker",
    "usage_tracker",
    # Providers
    "OpenAIProvider",
    "GeminiProvider",
    "ClaudeProvider",
    # Factory
    "LLMProviderFactory",
    # Utilities
    "_retry_with_backoff",
]
