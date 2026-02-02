"""
Unified LLM Client - Consolidates all LLM initialization and access.

This module eliminates the duplicated LLM setup code that was scattered across:
- reconcile_soa_llm.py
- send_pdf_to_llm.py
- vision_extract_soa.py
- soa_postprocess_consolidated.py
- find_soa_pages.py

Usage:
    from core.llm_client import get_llm_client, LLMConfig
    
    client = get_llm_client("gemini-2.5-pro")
    response = client.generate(messages, LLMConfig(json_mode=True))
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables once at module level
_env_loaded = False

def _ensure_env_loaded():
    """Ensure .env is loaded exactly once."""
    global _env_loaded
    if not _env_loaded:
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        _env_loaded = True


# Re-export from llm_providers for backward compatibility
try:
    from llm_providers import (
        LLMProviderFactory, 
        LLMConfig, 
        LLMResponse,
        OpenAIProvider,
        GeminiProvider,
    )
    PROVIDER_LAYER_AVAILABLE = True
except ImportError:
    PROVIDER_LAYER_AVAILABLE = False
    
    # Minimal fallback definitions
    @dataclass
    class LLMConfig:
        """Configuration for LLM generation."""
        temperature: float = 0.0
        max_tokens: Optional[int] = None
        json_mode: bool = True
        
    @dataclass
    class LLMResponse:
        """Standardized response from LLM."""
        content: str
        model: str
        usage: Optional[Dict[str, int]] = None


def get_llm_client(model_name: str, api_key: Optional[str] = None):
    """
    Get a configured LLM client for the specified model.
    
    This is the single entry point for obtaining LLM clients across the pipeline.
    
    Args:
        model_name: Model identifier (e.g., 'gpt-4o', 'gemini-2.5-pro', 'gpt-5.1')
        api_key: Optional API key override. If None, reads from environment.
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        ValueError: If provider layer unavailable and no fallback possible
        RuntimeError: If API key not configured
        
    Example:
        >>> client = get_llm_client("gemini-2.5-pro")
        >>> response = client.generate(messages, LLMConfig(json_mode=True))
        >>> print(response.content)
    """
    _ensure_env_loaded()
    
    if not PROVIDER_LAYER_AVAILABLE:
        raise ValueError(
            "LLM provider layer not available. "
            "Ensure llm_providers.py is in the project root."
        )
    
    return LLMProviderFactory.auto_detect(model_name, api_key=api_key)


def get_default_model() -> str:
    """
    Get the default model from environment or use fallback.
    
    Checks in order:
    1. OPENAI_MODEL environment variable
    2. Default to 'gemini-2.5-pro' (user preference)
    """
    _ensure_env_loaded()
    return os.environ.get("OPENAI_MODEL", "gemini-2.5-pro")


def is_reasoning_model(model_name: str) -> bool:
    """
    Check if model is a reasoning model (o1, o3, gpt-5 series).
    
    Reasoning models have different parameter requirements:
    - No temperature parameter
    - Use max_completion_tokens instead of max_tokens
    """
    from core.constants import REASONING_MODELS
    return any(rm in model_name.lower() for rm in REASONING_MODELS)


def detect_provider(model_name: str) -> str:
    """
    Detect the provider for a given model name.
    
    Deprecated: Use LLMProviderFactory.auto_detect() instead.
    
    Returns:
        'openai', 'google', 'anthropic', or 'unknown'
    """
    model_lower = model_name.lower()
    
    if any(x in model_lower for x in ['gpt', 'o1', 'o3']):
        return 'openai'
    elif 'gemini' in model_lower:
        return 'google'
    elif 'claude' in model_lower:
        return 'anthropic'
    else:
        return 'unknown'


# Max output tokens by model family (as of Jan 2026)
# Gemini 2.5 Flash/Pro and Gemini 3 Flash all support 65,536 output tokens
MAX_OUTPUT_TOKENS = {
    'gemini': 65536,  # Gemini 2.5 and 3.x models
    'gpt': 16384,     # GPT-4o and variants
    'claude': 8192,   # Claude models
    'default': 8192,
}

def _get_max_tokens_for_model(model_name: str) -> int:
    """Get the maximum output tokens supported by a model."""
    model_lower = model_name.lower()
    if 'gemini' in model_lower:
        return MAX_OUTPUT_TOKENS['gemini']
    elif 'gpt' in model_lower:
        return MAX_OUTPUT_TOKENS['gpt']
    elif 'claude' in model_lower:
        return MAX_OUTPUT_TOKENS['claude']
    return MAX_OUTPUT_TOKENS['default']


# Convenience function for simple text generation
def generate_text(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    extractor_name: Optional[str] = None,
) -> str:
    """
    Simple text generation helper.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        temperature: Generation temperature (ignored if extractor_name provided)
        max_tokens: Maximum output tokens (defaults to model's max)
        extractor_name: Optional extractor name to use task-specific config
        
    Returns:
        Generated text content
    """
    if model_name is None:
        model_name = get_default_model()
    
    # Use task config if extractor_name provided
    if extractor_name:
        from extraction.llm_task_config import get_llm_task_config, to_llm_config
        task_config = get_llm_task_config(extractor_name, model=model_name)
        config = to_llm_config(task_config)
        # Override max_tokens if explicitly provided
        if max_tokens is not None:
            config.max_tokens = max_tokens
    else:
        # Use model's max if not specified
        if max_tokens is None:
            max_tokens = _get_max_tokens_for_model(model_name)
        config = LLMConfig(
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )
    
    client = get_llm_client(model_name)
    response = client.generate(messages, config)
    return response.content


# Legacy compatibility - direct client access
def get_openai_client():
    """Get OpenAI client for legacy code. Prefer get_llm_client() instead."""
    _ensure_env_loaded()
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return OpenAI(api_key=api_key)
    except ImportError:
        pass
    return None


def get_gemini_client(model_name: str = "gemini-2.5-pro"):
    """Get Gemini client for legacy code. Prefer get_llm_client() instead."""
    _ensure_env_loaded()
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(model_name)
    except ImportError:
        pass
    return None


# Convenience functions for simple LLM calls
def call_llm(
    prompt: str,
    model_name: Optional[str] = None,
    json_mode: bool = True,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    extractor_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simple LLM call with a single prompt.
    
    Args:
        prompt: The prompt text
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        temperature: Generation temperature (ignored if extractor_name provided)
        max_tokens: Maximum output tokens (defaults to model's max: 65536 for Gemini)
        extractor_name: Optional extractor name to use task-specific config from llm_config.yaml
        
    Returns:
        Dict with 'response' key containing the generated text
    """
    if model_name is None:
        model_name = get_default_model()
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        content = generate_text(
            messages=messages,
            model_name=model_name,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
            extractor_name=extractor_name,
        )
        return {"response": content}
    except Exception as e:
        return {"error": str(e)}


def call_llm_with_image(
    prompt: str,
    image_path: str,
    model_name: Optional[str] = None,
    json_mode: bool = True,
) -> Dict[str, Any]:
    """
    LLM call with an image attachment.
    
    Uses the provider layer for consistent handling across all providers.
    
    Args:
        prompt: The prompt text
        image_path: Path to the image file
        model_name: Model to use (defaults to environment/gemini-2.5-pro)
        json_mode: Whether to request JSON output
        
    Returns:
        Dict with 'response' key containing the generated text
    """
    from pathlib import Path
    
    if model_name is None:
        model_name = get_default_model()
    
    _ensure_env_loaded()
    
    try:
        # Read image data
        image_data = Path(image_path).read_bytes()
        
        # Detect MIME type from extension
        suffix = Path(image_path).suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(suffix, 'image/png')
        
        # Use provider layer for consistent handling
        client = get_llm_client(model_name)
        config = LLMConfig(json_mode=json_mode, temperature=0.0)
        
        response = client.generate_with_image(
            prompt=prompt,
            image_data=image_data,
            mime_type=mime_type,
            config=config,
        )
        
        return {"response": response.content}
            
    except Exception as e:
        return {"error": str(e)}
