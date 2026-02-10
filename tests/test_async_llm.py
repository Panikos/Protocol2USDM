"""
Tests for E23: Async LLM calls (asyncio).

Validates:
- Base LLMProvider.agenerate() fallback (asyncio.to_thread)
- Base LLMProvider.agenerate_stream() fallback
- All 3 providers have agenerate() and agenerate_stream()
- OpenAI async_client lazy init
- Claude async_client lazy init + _build_claude_params helper
- Gemini _build_gen_config + _build_genai_sdk_config helpers
- Async convenience functions (acall_llm, agenerate_text) exports
- Concurrent async gather pattern
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import asdict

from providers.base import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    StreamChunk,
    StreamCallback,
)


# ── Concrete provider for testing base class fallback ─────────────────

class FakeProvider(LLMProvider):
    """Minimal concrete provider for testing the base class async fallback."""

    def _get_api_key_from_env(self) -> str:
        return "fake-key"

    def generate(self, messages, config=None):
        return LLMResponse(
            content="sync hello",
            model="fake-model",
            usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            finish_reason="stop",
        )

    def generate_stream(self, messages, config=None, callback=None):
        resp = self.generate(messages, config)
        if callback:
            callback(StreamChunk(
                text=resp.content, accumulated_text=resp.content,
                done=True, usage=resp.usage, finish_reason=resp.finish_reason,
            ))
        return resp

    def supports_json_mode(self):
        return True


# ── Base class async fallback ─────────────────────────────────────────

class TestBaseAsyncFallback:

    @pytest.mark.asyncio
    async def test_agenerate_returns_response(self):
        provider = FakeProvider(model="fake-model", api_key="k")
        resp = await provider.agenerate([{"role": "user", "content": "hi"}])
        assert resp.content == "sync hello"
        assert resp.model == "fake-model"

    @pytest.mark.asyncio
    async def test_agenerate_with_config(self):
        provider = FakeProvider(model="fake-model", api_key="k")
        config = LLMConfig(temperature=0.5)
        resp = await provider.agenerate([{"role": "user", "content": "hi"}], config)
        assert resp.content == "sync hello"

    @pytest.mark.asyncio
    async def test_agenerate_stream_returns_response(self):
        provider = FakeProvider(model="fake-model", api_key="k")
        chunks = []
        resp = await provider.agenerate_stream(
            [{"role": "user", "content": "hi"}],
            callback=lambda c: chunks.append(c),
        )
        assert resp.content == "sync hello"
        assert len(chunks) == 1
        assert chunks[0].done is True

    @pytest.mark.asyncio
    async def test_agenerate_stream_no_callback(self):
        provider = FakeProvider(model="fake-model", api_key="k")
        resp = await provider.agenerate_stream([{"role": "user", "content": "hi"}])
        assert resp.content == "sync hello"


# ── Concurrent gather pattern ─────────────────────────────────────────

class TestConcurrentGather:

    @pytest.mark.asyncio
    async def test_gather_multiple_calls(self):
        """Verify asyncio.gather works with agenerate."""
        provider = FakeProvider(model="fake-model", api_key="k")
        msgs = [{"role": "user", "content": "hi"}]

        results = await asyncio.gather(
            provider.agenerate(msgs),
            provider.agenerate(msgs),
            provider.agenerate(msgs),
        )
        assert len(results) == 3
        assert all(r.content == "sync hello" for r in results)


# ── Provider method existence ─────────────────────────────────────────

class TestProviderAsyncMethodExists:

    def test_openai_has_agenerate(self):
        from providers.openai_provider import OpenAIProvider
        assert asyncio.iscoroutinefunction(OpenAIProvider.agenerate)
        assert asyncio.iscoroutinefunction(OpenAIProvider.agenerate_stream)

    def test_claude_has_agenerate(self):
        from providers.claude_provider import ClaudeProvider
        assert asyncio.iscoroutinefunction(ClaudeProvider.agenerate)
        assert asyncio.iscoroutinefunction(ClaudeProvider.agenerate_stream)

    def test_gemini_has_agenerate(self):
        from providers.gemini_provider import GeminiProvider
        assert asyncio.iscoroutinefunction(GeminiProvider.agenerate)
        assert asyncio.iscoroutinefunction(GeminiProvider.agenerate_stream)


# ── OpenAI async_client lazy init ─────────────────────────────────────

class TestOpenAIAsyncClient:

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_async_client_lazy_init(self):
        from providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider._async_client is None
        client = provider.async_client
        assert client is not None
        # Second access returns same instance
        assert provider.async_client is client


# ── Claude helpers ────────────────────────────────────────────────────

class TestClaudeHelpers:

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_async_client_lazy_init(self):
        from providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider(model="claude-sonnet-4", api_key="test-key")
        assert provider._async_client is None
        client = provider.async_client
        assert client is not None
        assert provider.async_client is client

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_claude_params_basic(self):
        from providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider(model="claude-sonnet-4", api_key="test-key")
        config = LLMConfig(temperature=0.5, json_mode=False)
        params = provider._build_claude_params(
            [{"role": "user", "content": "hello"}], config
        )
        assert params["model"] == "claude-sonnet-4"
        assert params["temperature"] == 0.5
        assert params["messages"] == [{"role": "user", "content": "hello"}]
        assert "system" not in params

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_claude_params_with_system(self):
        from providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider(model="claude-sonnet-4", api_key="test-key")
        config = LLMConfig(json_mode=True)
        params = provider._build_claude_params(
            [{"role": "system", "content": "You are helpful"}, {"role": "user", "content": "hi"}],
            config,
        )
        assert "system" in params
        assert "JSON" in params["system"]
        assert params["messages"] == [{"role": "user", "content": "hi"}]


# ── Gemini helpers ────────────────────────────────────────────────────

class TestGeminiHelpers:

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False)
    def test_build_gen_config(self):
        # Remove GOOGLE_CLOUD_PROJECT to avoid Vertex AI init
        import os
        old_val = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        try:
            from providers.gemini_provider import GeminiProvider
            provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
            config = LLMConfig(temperature=0.3, max_tokens=1000, json_mode=True)
            d = provider._build_gen_config(config)
            assert d["temperature"] == 0.3
            assert d["max_output_tokens"] == 1000
            assert d["response_mime_type"] == "application/json"
        finally:
            if old_val is not None:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_val

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False)
    def test_build_gen_config_minimal(self):
        import os
        old_val = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        try:
            from providers.gemini_provider import GeminiProvider
            provider = GeminiProvider(model="gemini-2.5-pro", api_key="test-key")
            config = LLMConfig(temperature=0.0, json_mode=False)
            d = provider._build_gen_config(config)
            assert d == {"temperature": 0.0}
        finally:
            if old_val is not None:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_val


# ── Exports ───────────────────────────────────────────────────────────

class TestAsyncExports:

    def test_core_exports_async_helpers(self):
        from core import acall_llm, agenerate_text
        assert asyncio.iscoroutinefunction(acall_llm)
        assert asyncio.iscoroutinefunction(agenerate_text)

    def test_llm_client_exports(self):
        from core.llm_client import acall_llm, agenerate_text
        assert asyncio.iscoroutinefunction(acall_llm)
        assert asyncio.iscoroutinefunction(agenerate_text)
