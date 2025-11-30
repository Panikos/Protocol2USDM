"""
LLM Provider Abstraction Layer

Provides a unified interface for multiple LLM providers (OpenAI, Google Gemini).
Supports GPT-4, GPT-5 (when available), and Gemini 2.x models.

Usage:
    provider = LLMProviderFactory.create("openai", model="gpt-4o")
    response = provider.generate(messages, config)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os
from openai import OpenAI
import google.generativeai as genai


@dataclass
class LLMConfig:
    """Configuration for LLM generation."""
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    json_mode: bool = True
    stop_sequences: Optional[List[str]] = None
    top_p: Optional[float] = None
    
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
        'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini',  # Future-proofing
    ]
    
    # Models that don't support temperature parameter
    NO_TEMP_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini']
    
    # Models that use max_completion_tokens instead of max_tokens
    COMPLETION_TOKENS_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini']
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        super().__init__(model, api_key)
        self.client = OpenAI(api_key=self.api_key)
    
    def _get_api_key_from_env(self) -> str:
        """Get OpenAI API key from environment."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
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
                usage = {
                    "prompt_tokens": getattr(response.usage, 'input_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'output_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0)
                }
            
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
            raise RuntimeError(f"OpenAI Responses API call failed for model '{self.model}': {e}")


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider supporting Gemini 1.5, 2.x, and 3.x models.
    
    Features:
    - Native JSON mode (response_mime_type)
    - Long context windows
    - Multimodal support
    """
    
    SUPPORTED_MODELS = [
        # Gemini 3.x (preview)
        'gemini-3-pro-preview',
        # Gemini 2.5 (stable)
        'gemini-2.5-pro', 'gemini-2.5-flash',
        # Gemini 2.0
        'gemini-2.0-pro', 'gemini-2.0-flash',
        'gemini-2.0-flash-exp',
        # Gemini 1.5
        'gemini-1.5-pro', 'gemini-1.5-flash',
        # Legacy
        'gemini-pro', 'gemini-pro-vision',
    ]
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        super().__init__(model, api_key)
        genai.configure(api_key=self.api_key)
    
    def _get_api_key_from_env(self) -> str:
        """Get Google API key from environment."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        return api_key
    
    def supports_json_mode(self) -> bool:
        """Gemini supports JSON mode via response_mime_type."""
        return True
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        Generate completion using Gemini API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Generation configuration
        
        Returns:
            LLMResponse with content and metadata
        """
        if config is None:
            config = LLMConfig()
        
        # Build generation config
        gen_config_dict = {
            "temperature": config.temperature,
        }
        
        if config.max_tokens:
            gen_config_dict["max_output_tokens"] = config.max_tokens
        if config.stop_sequences:
            gen_config_dict["stop_sequences"] = config.stop_sequences
        if config.top_p is not None:
            gen_config_dict["top_p"] = config.top_p
        
        # Add JSON mode if requested
        if config.json_mode and self.supports_json_mode():
            gen_config_dict["response_mime_type"] = "application/json"
        
        generation_config = genai.types.GenerationConfig(**gen_config_dict)
        
        # Convert messages to Gemini format
        # Gemini expects a single prompt string, not message history
        # Combine system and user messages
        full_prompt = self._format_messages_for_gemini(messages)
        
        # Create model instance
        model = genai.GenerativeModel(
            self.model,
            generation_config=generation_config
        )
        
        # Make API call
        try:
            response = model.generate_content(full_prompt)
            
            # Extract usage information (if available)
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count
                }
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response
            )
        
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed for model '{self.model}': {e}")
    
    def _format_messages_for_gemini(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert OpenAI-style messages to Gemini prompt format.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
        
        Returns:
            Single formatted prompt string
        """
        formatted_parts = []
        
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            if role == 'system':
                formatted_parts.append(f"{content}\n")
            elif role == 'user':
                formatted_parts.append(f"\n{content}")
            elif role == 'assistant':
                # For few-shot examples
                formatted_parts.append(f"\nAssistant: {content}")
        
        return '\n'.join(formatted_parts)


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers = {
        'openai': OpenAIProvider,
        'gemini': GeminiProvider,
    }
    
    @classmethod
    def create(
        cls, 
        provider_name: str, 
        model: str, 
        api_key: Optional[str] = None
    ) -> LLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            provider_name: Provider name ('openai', 'gemini')
            model: Model identifier
            api_key: Optional API key (reads from env if not provided)
        
        Returns:
            LLMProvider instance
        
        Raises:
            ValueError: If provider not supported
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls._providers:
            supported = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Provider '{provider_name}' not supported. "
                f"Supported providers: {supported}"
            )
        
        provider_class = cls._providers[provider_name]
        return provider_class(model=model, api_key=api_key)
    
    @classmethod
    def auto_detect(cls, model: str, api_key: Optional[str] = None) -> LLMProvider:
        """
        Auto-detect provider from model name.
        
        Args:
            model: Model identifier (e.g., "gpt-4o", "gemini-2.5-pro")
            api_key: Optional API key
        
        Returns:
            LLMProvider instance
        
        Raises:
            ValueError: If model name doesn't match known patterns
        """
        model_lower = model.lower()
        
        # Check OpenAI patterns
        if any(pattern in model_lower for pattern in ['gpt', 'o1', 'o3']):
            return cls.create('openai', model, api_key)
        
        # Check Gemini patterns
        if 'gemini' in model_lower:
            return cls.create('gemini', model, api_key)
        
        raise ValueError(
            f"Could not auto-detect provider for model '{model}'. "
            f"Please specify provider explicitly."
        )
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """Get list of supported provider names."""
        return list(cls._providers.keys())
