"""
LLM Provider Base Classes and Configuration

Provides the abstract base class for LLM providers, configuration dataclasses,
and shared utilities like retry logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional, Any, Callable
from dataclasses import dataclass, field
import asyncio
import time
import logging

_logger = logging.getLogger(__name__)

# Retry configuration for rate limiting (429 errors)
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 60


def _retry_with_backoff(func, max_retries=MAX_RETRIES, initial_backoff=INITIAL_BACKOFF_SECONDS):
    """
    Retry a function with exponential backoff for rate limit (429) errors.
    
    Args:
        func: Callable to retry
        max_retries: Maximum number of retries
        initial_backoff: Initial backoff in seconds (doubles each retry)
    
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    backoff = initial_backoff
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            error_str = str(e).lower()
            # Check for rate limit errors (429) or resource exhausted
            is_rate_limit = '429' in error_str or 'rate' in error_str or 'exhausted' in error_str or 'quota' in error_str
            
            if is_rate_limit and attempt < max_retries:
                wait_time = min(backoff, MAX_BACKOFF_SECONDS)
                _logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(wait_time)
                backoff *= 2  # Exponential backoff
                last_exception = e
            else:
                # Not a rate limit error or out of retries
                raise e
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


@dataclass
class LLMConfig:
    """Configuration for LLM generation."""
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    json_mode: bool = True
    stop_sequences: Optional[List[str]] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response.

    Attributes:
        text: The incremental text content in this chunk.
        accumulated_text: All text received so far (including this chunk).
        done: True when this is the final chunk.
        usage: Token usage (populated only on the final chunk).
        finish_reason: Stop reason (populated only on the final chunk).
    """
    text: str
    accumulated_text: str
    done: bool = False
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


# Callback invoked for each StreamChunk during streaming generation.
StreamCallback = Callable[[StreamChunk], None]


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        """
        Initialize provider.
        
        Args:
            model: Model identifier (e.g., "gpt-4o", "gemini-2.5-pro")
            api_key: API key (if None, reads from environment)
        """
        self.model = model
        self.api_key = api_key or self._get_api_key_from_env()
    
    @abstractmethod
    def _get_api_key_from_env(self) -> str:
        """Get API key from environment variable."""
        pass
    
    @abstractmethod
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        Generate completion from messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Generation configuration
        
        Returns:
            LLMResponse with content and metadata
        """
        pass
    
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Check if model supports native JSON mode."""
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model='{self.model}')"

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional[StreamCallback] = None,
    ) -> LLMResponse:
        """Generate completion with streaming, invoking *callback* per chunk.

        Providers that support native streaming should override this method.
        The default implementation falls back to :meth:`generate` and emits
        a single chunk containing the full response.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            config: Generation configuration.
            callback: Optional callable invoked for each :class:`StreamChunk`.

        Returns:
            Final :class:`LLMResponse` (same as :meth:`generate`).
        """
        response = self.generate(messages, config)
        if callback:
            chunk = StreamChunk(
                text=response.content,
                accumulated_text=response.content,
                done=True,
                usage=response.usage,
                finish_reason=response.finish_reason,
            )
            callback(chunk)
        return response
    
    async def agenerate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Async version of :meth:`generate`.

        Providers that have native async SDKs should override this.
        The default implementation runs :meth:`generate` in a thread
        via :func:`asyncio.to_thread`.
        """
        return await asyncio.to_thread(self.generate, messages, config)

    async def agenerate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional[StreamCallback] = None,
    ) -> LLMResponse:
        """Async version of :meth:`generate_stream`.

        Providers that have native async SDKs should override this.
        The default implementation runs :meth:`generate_stream` in a thread
        via :func:`asyncio.to_thread`.
        """
        return await asyncio.to_thread(self.generate_stream, messages, config, callback)

    def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        mime_type: str = "image/png",
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        Generate completion with an image input.
        
        Args:
            prompt: Text prompt
            image_data: Raw image bytes
            mime_type: Image MIME type (e.g., 'image/png', 'image/jpeg')
            config: Generation configuration
            
        Returns:
            LLMResponse with content and metadata
            
        Raises:
            NotImplementedError: If provider doesn't support vision
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support image input")
