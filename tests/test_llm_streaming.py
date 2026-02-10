"""
Tests for E21: LLM response streaming for progress visibility.

Validates:
- StreamChunk dataclass fields
- Base LLMProvider.generate_stream() fallback (single chunk)
- Callback invocation contract (intermediate + final done=True chunk)
- Accumulated text correctness across chunks
- No callback = no error
- All 3 providers export generate_stream()
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from providers.base import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    StreamChunk,
    StreamCallback,
)


# ── StreamChunk dataclass ────────────────────────────────────────────

class TestStreamChunk:

    def test_defaults(self):
        c = StreamChunk(text="hi", accumulated_text="hi")
        assert c.done is False
        assert c.usage is None
        assert c.finish_reason is None

    def test_final_chunk(self):
        c = StreamChunk(
            text="", accumulated_text="full text", done=True,
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
        )
        assert c.done is True
        assert c.usage["total_tokens"] == 30

    def test_to_dict(self):
        c = StreamChunk(text="a", accumulated_text="a")
        d = asdict(c)
        assert "text" in d
        assert "accumulated_text" in d
        assert "done" in d


# ── Base LLMProvider fallback ─────────────────────────────────────────

class ConcreteProvider(LLMProvider):
    """Minimal concrete provider for testing the base class fallback."""

    def _get_api_key_from_env(self) -> str:
        return "fake-key"

    def generate(self, messages, config=None):
        return LLMResponse(
            content="hello world",
            model="test-model",
            usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            finish_reason="stop",
        )

    def supports_json_mode(self):
        return True


class TestBaseProviderFallback:

    def test_fallback_returns_response(self):
        provider = ConcreteProvider(model="test-model", api_key="k")
        resp = provider.generate_stream([{"role": "user", "content": "hi"}])
        assert resp.content == "hello world"
        assert resp.model == "test-model"

    def test_fallback_invokes_callback_once(self):
        provider = ConcreteProvider(model="test-model", api_key="k")
        chunks = []
        resp = provider.generate_stream(
            [{"role": "user", "content": "hi"}],
            callback=lambda c: chunks.append(c),
        )
        assert len(chunks) == 1
        assert chunks[0].done is True
        assert chunks[0].text == "hello world"
        assert chunks[0].accumulated_text == "hello world"
        assert chunks[0].usage == resp.usage

    def test_fallback_no_callback_ok(self):
        provider = ConcreteProvider(model="test-model", api_key="k")
        resp = provider.generate_stream([{"role": "user", "content": "hi"}])
        assert resp.content == "hello world"

    def test_fallback_with_config(self):
        provider = ConcreteProvider(model="test-model", api_key="k")
        config = LLMConfig(temperature=0.5, json_mode=False)
        resp = provider.generate_stream(
            [{"role": "user", "content": "hi"}], config=config,
        )
        assert resp.content == "hello world"


# ── Streaming callback contract ───────────────────────────────────────

class TestStreamingContract:
    """Verify the streaming callback contract across simulated chunks."""

    def test_accumulated_text_grows(self):
        """Simulate what a real streaming provider does."""
        chunks_received = []

        def on_chunk(chunk: StreamChunk):
            chunks_received.append(chunk)

        # Simulate 3 intermediate chunks + 1 final
        accumulated = ""
        for text in ["Hel", "lo ", "world"]:
            accumulated += text
            on_chunk(StreamChunk(text=text, accumulated_text=accumulated, done=False))
        on_chunk(StreamChunk(text="", accumulated_text=accumulated, done=True,
                             usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}))

        assert len(chunks_received) == 4
        assert chunks_received[0].text == "Hel"
        assert chunks_received[0].accumulated_text == "Hel"
        assert chunks_received[1].accumulated_text == "Hello "
        assert chunks_received[2].accumulated_text == "Hello world"
        assert chunks_received[3].done is True
        assert chunks_received[3].usage["total_tokens"] == 8

    def test_only_final_chunk_has_done_true(self):
        chunks = [
            StreamChunk(text="a", accumulated_text="a", done=False),
            StreamChunk(text="b", accumulated_text="ab", done=False),
            StreamChunk(text="", accumulated_text="ab", done=True),
        ]
        done_chunks = [c for c in chunks if c.done]
        assert len(done_chunks) == 1

    def test_final_chunk_has_empty_text(self):
        """Convention: final done=True chunk has text='' (no new content)."""
        final = StreamChunk(text="", accumulated_text="full", done=True)
        assert final.text == ""


# ── Provider method existence ─────────────────────────────────────────

class TestProviderMethodExists:
    """All 3 providers have generate_stream()."""

    def test_gemini_has_generate_stream(self):
        from providers.gemini_provider import GeminiProvider
        assert hasattr(GeminiProvider, 'generate_stream')
        assert callable(getattr(GeminiProvider, 'generate_stream'))

    def test_openai_has_generate_stream(self):
        from providers.openai_provider import OpenAIProvider
        assert hasattr(OpenAIProvider, 'generate_stream')
        assert callable(getattr(OpenAIProvider, 'generate_stream'))

    def test_claude_has_generate_stream(self):
        from providers.claude_provider import ClaudeProvider
        assert hasattr(ClaudeProvider, 'generate_stream')
        assert callable(getattr(ClaudeProvider, 'generate_stream'))


# ── Exports ───────────────────────────────────────────────────────────

class TestExports:

    def test_providers_package_exports(self):
        from providers import StreamChunk, StreamCallback
        assert StreamChunk is not None
        assert StreamCallback is not None

    def test_llm_providers_shim_exports(self):
        from llm_providers import StreamChunk, StreamCallback
        assert StreamChunk is not None
        assert StreamCallback is not None
