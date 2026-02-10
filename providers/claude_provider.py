"""
Anthropic Claude LLM Provider

Supports Claude 3, 3.5, 3.7, 4, and 4.5 models.
Uses streaming to avoid 10-minute timeout on long operations.
"""

import os
import logging
from typing import Dict, List, Optional, Any

from core.errors import ConfigurationError, LLMError
from .base import LLMProvider, LLMConfig, LLMResponse, StreamChunk, StreamCallback
from .tracker import usage_tracker

import anthropic

_logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude provider supporting Claude 3, 3.5, and 4 models.
    
    Features:
    - Native JSON mode (via tool_use or system prompt)
    - 200K context window
    - Strong reasoning capabilities
    - Vision support (Claude 3+)
    """
    
    SUPPORTED_MODELS = [
        # Claude Opus 4.5 (latest, most powerful)
        'claude-opus-4-5-20250918', 'claude-opus-4-5',
        # Claude Sonnet 4.5
        'claude-sonnet-4-5-20250918', 'claude-sonnet-4-5',
        # Claude Opus 4.x
        'claude-opus-4-1', 'claude-opus-4-1-20250805',
        'claude-opus-4', 'claude-opus-4-20250514',
        # Claude Sonnet 4
        'claude-sonnet-4', 'claude-sonnet-4-20250514',
        # Claude 3.7 Sonnet
        'claude-3-7-sonnet-latest', 'claude-3-7-sonnet-20250219',
        # Claude 3.5
        'claude-3-5-sonnet-latest', 'claude-3-5-sonnet-20241022',
        'claude-3-5-haiku-latest', 'claude-3-5-haiku-20241022',
        # Claude 3 (legacy)
        'claude-3-haiku', 'claude-3-haiku-20240307',
    ]
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        super().__init__(model, api_key)
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def _get_api_key_from_env(self) -> str:
        """Get Anthropic API key from environment."""
        # Check common environment variable names
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY or CLAUDE_API_KEY environment variable not set", model=self.model)
        return api_key
    
    def supports_json_mode(self) -> bool:
        """Claude supports JSON mode via system prompt."""
        return True
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        Generate completion using Anthropic Claude API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Generation configuration
        
        Returns:
            LLMResponse with content and metadata
        """
        if config is None:
            config = LLMConfig()
        
        # Separate system message from other messages (Claude API requirement)
        system_content = ""
        api_messages = []
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                system_content = content
            else:
                # Claude uses 'assistant' for assistant messages
                api_messages.append({
                    "role": role,
                    "content": content
                })
        
        # Add JSON mode instruction to system prompt if requested
        if config.json_mode:
            json_instruction = "\n\nYou must respond with valid JSON only. No markdown, no explanation, just the JSON object."
            system_content = (system_content + json_instruction) if system_content else json_instruction.strip()
        
        # Build parameters
        # Claude needs higher max_tokens for complex extractions
        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": config.max_tokens or 16384,
        }
        
        if system_content:
            params["system"] = system_content
        
        # Add temperature
        params["temperature"] = config.temperature
        
        # Add optional parameters
        if config.stop_sequences:
            params["stop_sequences"] = config.stop_sequences
        if config.top_p is not None:
            params["top_p"] = config.top_p
        
        # Make API call with streaming to handle long operations
        # Anthropic requires streaming for operations >10 minutes
        try:
            # Use streaming to avoid 10-minute timeout
            content = ""
            input_tokens = 0
            output_tokens = 0
            stop_reason = None
            model_used = self.model
            
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    content += text
                
                # Get final message for metadata
                final_message = stream.get_final_message()
                if final_message:
                    stop_reason = final_message.stop_reason
                    model_used = final_message.model
                    if final_message.usage:
                        input_tokens = final_message.usage.input_tokens
                        output_tokens = final_message.usage.output_tokens
            
            # Log warning if response was truncated
            if stop_reason == 'max_tokens':
                _logger.warning(
                    f"Claude response was truncated (max_tokens reached). "
                    f"Used {output_tokens} tokens. Consider increasing max_tokens."
                )
            
            # Log warning if empty response
            if not content:
                _logger.warning(
                    f"Claude returned empty content. Stop reason: {stop_reason}"
                )
            
            # Build usage information
            usage = None
            if input_tokens or output_tokens:
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                }
                # Track usage globally
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=content,
                model=model_used,
                usage=usage,
                finish_reason=stop_reason,
                raw_response=None  # No raw response with streaming
            )
        
        except Exception as e:
            raise LLMError(f"Anthropic API call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional[StreamCallback] = None,
    ) -> LLMResponse:
        """Generate with native Anthropic streaming, invoking *callback* per chunk."""
        if config is None:
            config = LLMConfig()

        system_content = ""
        api_messages = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                system_content = content
            else:
                api_messages.append({"role": role, "content": content})

        if config.json_mode:
            json_instruction = "\n\nYou must respond with valid JSON only. No markdown, no explanation, just the JSON object."
            system_content = (system_content + json_instruction) if system_content else json_instruction.strip()

        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": config.max_tokens or 16384,
            "temperature": config.temperature,
        }
        if system_content:
            params["system"] = system_content
        if config.stop_sequences:
            params["stop_sequences"] = config.stop_sequences
        if config.top_p is not None:
            params["top_p"] = config.top_p

        try:
            accumulated = ""
            input_tokens = 0
            output_tokens = 0
            stop_reason = None
            model_used = self.model

            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    accumulated += text
                    if callback and text:
                        callback(StreamChunk(
                            text=text, accumulated_text=accumulated, done=False,
                        ))

                final_message = stream.get_final_message()
                if final_message:
                    stop_reason = final_message.stop_reason
                    model_used = final_message.model
                    if final_message.usage:
                        input_tokens = final_message.usage.input_tokens
                        output_tokens = final_message.usage.output_tokens

            usage = None
            if input_tokens or output_tokens:
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }
                usage_tracker.add_usage(input_tokens, output_tokens)

            if callback:
                callback(StreamChunk(
                    text="", accumulated_text=accumulated, done=True,
                    usage=usage, finish_reason=stop_reason,
                ))

            return LLMResponse(
                content=accumulated, model=model_used,
                usage=usage, finish_reason=stop_reason,
            )
        except Exception as e:
            raise LLMError(f"Anthropic streaming failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
