"""
LLM Provider Factory

Auto-detects and creates the appropriate LLM provider based on model name.
"""

from typing import List, Optional

from .base import LLMProvider
from core.errors import ConfigurationError
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .claude_provider import ClaudeProvider


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
            raise ConfigurationError(
                f"Provider '{provider_name}' not supported. "
                f"Supported providers: {supported}",
                model=model,
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
        
        raise ConfigurationError(
            f"Could not auto-detect provider for model '{model}'. "
            f"Please specify provider explicitly.",
            model=model,
        )
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """Get list of supported provider names."""
        return list(cls._providers.keys())
