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
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import anthropic


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
        'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini',
    ]
    
    # Models that don't support temperature parameter
    NO_TEMP_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini']
    
    # Models that use max_completion_tokens instead of max_tokens
    COMPLETION_TOKENS_MODELS = ['o1', 'o1-mini', 'o3', 'o3-mini', 'o3-mini-high', 'gpt-5', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.2', 'gpt-5.2-mini']
    
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
    
    Routes through Vertex AI when GOOGLE_CLOUD_PROJECT is set.
    All safety controls are disabled for clinical protocol extraction.
    
    Features:
    - Native JSON mode (response_mime_type)
    - Long context windows
    - Multimodal support
    - Vertex AI routing (enterprise)
    - Safety controls disabled
    """
    
    SUPPORTED_MODELS = [
        # Gemini 3.x
        'gemini-3-pro', 'gemini-3-flash', 'gemini-3-pro-preview', 'gemini-3-flash-preview',
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
    
    # Safety settings: disable all safety filters for clinical content
    SAFETY_SETTINGS = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        super().__init__(model, api_key)
        
        # Check for Vertex AI configuration
        self.use_vertex = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        
        if self.use_vertex:
            # Configure for Vertex AI
            import vertexai
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            vertexai.init(project=project, location=location)
        else:
            # Configure for Google AI Studio
            genai.configure(api_key=self.api_key)
    
    def _get_api_key_from_env(self) -> str:
        """Get Google API key from environment (for AI Studio fallback)."""
        # Vertex AI uses ADC, not API key
        if os.environ.get("GOOGLE_CLOUD_PROJECT"):
            return "vertex-ai"  # Placeholder, uses ADC
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set (or use GOOGLE_CLOUD_PROJECT for Vertex AI)")
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
        Generate completion using Gemini API (Vertex AI or AI Studio).
        
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
        
        # Convert messages to Gemini format
        full_prompt = self._format_messages_for_gemini(messages)
        
        if self.use_vertex:
            return self._generate_vertex(full_prompt, gen_config_dict)
        else:
            return self._generate_ai_studio(full_prompt, gen_config_dict)
    
    def _generate_vertex(self, prompt: str, gen_config_dict: dict) -> LLMResponse:
        """Generate using Vertex AI with safety controls disabled."""
        from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold
        
        generation_config = GenerationConfig(**gen_config_dict)
        
        # Vertex AI safety settings - BLOCK_NONE for medical/clinical content
        # Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/configure-safety-filters
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Create model instance (safety_settings passed to generate_content, not constructor)
        model = GenerativeModel(self.model)
        
        try:
            # Pass safety_settings to generate_content() per Vertex AI pattern
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            
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
            raise RuntimeError(f"Vertex AI Gemini call failed for model '{self.model}': {e}")
    
    def _generate_ai_studio(self, prompt: str, gen_config_dict: dict) -> LLMResponse:
        """Generate using Google AI Studio (fallback)."""
        generation_config = genai.types.GenerationConfig(**gen_config_dict)
        
        model = genai.GenerativeModel(
            self.model,
            generation_config=generation_config,
            safety_settings=self.SAFETY_SETTINGS,
        )
        
        try:
            response = model.generate_content(prompt)
            
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
            raise RuntimeError(f"Gemini AI Studio call failed for model '{self.model}': {e}")
    
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
            raise ValueError("ANTHROPIC_API_KEY or CLAUDE_API_KEY environment variable not set")
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
        
        # Make API call
        try:
            response = self.client.messages.create(**params)
            
            # Extract content from response
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content = block.text
                        break
            
            # Log warning if response was truncated
            if response.stop_reason == 'max_tokens':
                import logging
                logging.getLogger(__name__).warning(
                    f"Claude response was truncated (max_tokens reached). "
                    f"Used {response.usage.output_tokens} tokens. Consider increasing max_tokens."
                )
            
            # Log warning if empty response
            if not content:
                import logging
                logging.getLogger(__name__).warning(
                    f"Claude returned empty content. Stop reason: {response.stop_reason}"
                )
            
            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.stop_reason,
                raw_response=response
            )
        
        except Exception as e:
            raise RuntimeError(f"Anthropic API call failed for model '{self.model}': {e}")


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers = {
        'openai': OpenAIProvider,
        'gemini': GeminiProvider,
        'claude': ClaudeProvider,
        'anthropic': ClaudeProvider,  # Alias
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
            model: Model identifier (e.g., "gpt-4o", "gemini-2.5-pro", "claude-sonnet-4")
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
        
        # Check Claude/Anthropic patterns
        if any(pattern in model_lower for pattern in ['claude', 'anthropic']):
            return cls.create('claude', model, api_key)
        
        raise ValueError(
            f"Could not auto-detect provider for model '{model}'. "
            f"Please specify provider explicitly."
        )
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """Get list of supported provider names."""
        return list(cls._providers.keys())
