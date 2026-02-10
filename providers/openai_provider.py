"""
OpenAI LLM Provider

Supports GPT-4, GPT-4o, GPT-5 (when available), and reasoning models (o1, o3).
Uses the Responses API for standard generation and Chat Completions for vision.
"""

import os
import base64
from typing import Dict, List, Optional, Any

from core.errors import ConfigurationError, LLMError
from .base import LLMProvider, LLMConfig, LLMResponse, StreamChunk, StreamCallback
from .tracker import usage_tracker

from openai import OpenAI, AsyncOpenAI


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider supporting GPT-4, GPT-4o, GPT-5 (when available).
    
    Features:
    - Native JSON mode
    - Function calling
    - High token limits
    """
    
    SUPPORTED_MODELS = [
        'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
        'o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high',
        'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini',
    ]
    
    # Models that don't support temperature parameter
    NO_TEMP_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini']
    
    # Models that use max_completion_tokens instead of max_tokens
    COMPLETION_TOKENS_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini']
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        super().__init__(model, api_key)
        self.client = OpenAI(api_key=self.api_key)
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def async_client(self) -> AsyncOpenAI:
        """Lazy-init async client to avoid event-loop issues at import time."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self.api_key)
        return self._async_client
    
    def _get_api_key_from_env(self) -> str:
        """Get OpenAI API key from environment."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY environment variable not set", model=self.model)
        return api_key
    
    def supports_json_mode(self) -> bool:
        """OpenAI supports JSON mode for most chat models."""
        return True
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        Generate completion using OpenAI Responses API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Generation configuration
        
        Returns:
            LLMResponse with content and metadata
        """
        if config is None:
            config = LLMConfig()
        
        # Convert messages to Responses API input format
        # Responses API uses 'input' with role-based messages
        input_items = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # Build message in Responses API format
            input_items.append({
                "role": role,
                "content": content
            })
        
        # Build parameters for Responses API
        params = {
            "model": self.model,
            "input": input_items,
        }
        
        # Add temperature if supported
        if self.model not in self.NO_TEMP_MODELS:
            params["temperature"] = config.temperature
        
        # Add JSON mode if requested (via text config)
        if config.json_mode and self.supports_json_mode():
            params["text"] = {"format": {"type": "json_object"}}
        
        # Add optional parameters
        if config.max_tokens:
            params["max_output_tokens"] = config.max_tokens
        
        # Make API call using Responses API
        try:
            response = self.client.responses.create(**params)
            
            # Extract usage information
            usage = None
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'input_tokens', 0) or 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0
                }
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            # Extract content from response - try output_text first (simpler)
            content = ""
            if hasattr(response, 'output_text'):
                content = response.output_text
            elif hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'content'):
                        for content_item in item.content:
                            if hasattr(content_item, 'text'):
                                content = content_item.text
                                break
            
            return LLMResponse(
                content=content,
                model=getattr(response, 'model', self.model),
                usage=usage,
                finish_reason=getattr(response, 'status', None),
                raw_response=response
            )
        
        except Exception as e:
            raise LLMError(f"OpenAI Responses API call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional[StreamCallback] = None,
    ) -> LLMResponse:
        """Generate with native OpenAI streaming via Chat Completions API."""
        if config is None:
            config = LLMConfig()

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if self.model not in self.NO_TEMP_MODELS:
            params["temperature"] = config.temperature
        if config.json_mode and self.supports_json_mode():
            params["response_format"] = {"type": "json_object"}
        if config.max_tokens:
            if self.model in self.COMPLETION_TOKENS_MODELS:
                params["max_completion_tokens"] = config.max_tokens
            else:
                params["max_tokens"] = config.max_tokens
        # Request usage in stream
        params["stream_options"] = {"include_usage": True}

        try:
            accumulated = ""
            usage = None
            finish_reason = None
            with self.client.chat.completions.create(**params) as stream:
                for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        text = delta.content or ""
                        if text:
                            accumulated += text
                            if callback:
                                callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                    if chunk.usage:
                        inp = chunk.usage.prompt_tokens or 0
                        out = chunk.usage.completion_tokens or 0
                        usage = {
                            "prompt_tokens": inp,
                            "completion_tokens": out,
                            "total_tokens": chunk.usage.total_tokens or 0,
                        }
                        usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True,
                                     usage=usage, finish_reason=finish_reason))

            return LLMResponse(
                content=accumulated, model=self.model,
                usage=usage, finish_reason=finish_reason,
            )
        except Exception as e:
            raise LLMError(f"OpenAI streaming failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    async def agenerate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Native async generation via OpenAI Responses API."""
        if config is None:
            config = LLMConfig()

        input_items = [{"role": msg.get('role', 'user'), "content": msg.get('content', '')} for msg in messages]
        params: Dict[str, Any] = {"model": self.model, "input": input_items}
        if self.model not in self.NO_TEMP_MODELS:
            params["temperature"] = config.temperature
        if config.json_mode and self.supports_json_mode():
            params["text"] = {"format": {"type": "json_object"}}
        if config.max_tokens:
            params["max_output_tokens"] = config.max_tokens

        try:
            response = await self.async_client.responses.create(**params)

            usage = None
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'input_tokens', 0) or 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0,
                }
                usage_tracker.add_usage(input_tokens, output_tokens)

            content = ""
            if hasattr(response, 'output_text'):
                content = response.output_text
            elif hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'content'):
                        for ci in item.content:
                            if hasattr(ci, 'text'):
                                content = ci.text
                                break

            return LLMResponse(
                content=content, model=getattr(response, 'model', self.model),
                usage=usage, finish_reason=getattr(response, 'status', None),
                raw_response=response,
            )
        except Exception as e:
            raise LLMError(f"OpenAI async Responses API failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    async def agenerate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional[StreamCallback] = None,
    ) -> LLMResponse:
        """Native async streaming via OpenAI Chat Completions API."""
        if config is None:
            config = LLMConfig()

        params: Dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
        if self.model not in self.NO_TEMP_MODELS:
            params["temperature"] = config.temperature
        if config.json_mode and self.supports_json_mode():
            params["response_format"] = {"type": "json_object"}
        if config.max_tokens:
            if self.model in self.COMPLETION_TOKENS_MODELS:
                params["max_completion_tokens"] = config.max_tokens
            else:
                params["max_tokens"] = config.max_tokens
        params["stream_options"] = {"include_usage": True}

        try:
            accumulated = ""
            usage = None
            finish_reason = None
            async with await self.async_client.chat.completions.create(**params) as stream:
                async for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        text = delta.content or ""
                        if text:
                            accumulated += text
                            if callback:
                                callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                    if chunk.usage:
                        inp = chunk.usage.prompt_tokens or 0
                        out = chunk.usage.completion_tokens or 0
                        usage = {"prompt_tokens": inp, "completion_tokens": out,
                                 "total_tokens": chunk.usage.total_tokens or 0}
                        usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True,
                                     usage=usage, finish_reason=finish_reason))
            return LLMResponse(content=accumulated, model=self.model,
                               usage=usage, finish_reason=finish_reason)
        except Exception as e:
            raise LLMError(f"OpenAI async streaming failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        mime_type: str = "image/png",
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """Generate completion with an image using OpenAI vision models."""
        if config is None:
            config = LLMConfig()
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        
        params = {
            "model": self.model,
            "messages": messages,
        }
        
        if self.model not in self.NO_TEMP_MODELS:
            params["temperature"] = config.temperature
        
        if config.json_mode and self.supports_json_mode():
            params["response_format"] = {"type": "json_object"}
        
        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        
        try:
            response = self.client.chat.completions.create(**params)
            
            usage = None
            if response.usage:
                input_tokens = response.usage.prompt_tokens or 0
                output_tokens = response.usage.completion_tokens or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": response.usage.total_tokens or 0
                }
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response
            )
        except Exception as e:
            raise LLMError(f"OpenAI vision call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
