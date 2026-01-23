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
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

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

# Load .env file from project root
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from openai import OpenAI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import anthropic

# For Gemini 3 models via Vertex AI (requires global endpoint)
try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    HAS_GENAI_SDK = True
    # Suppress verbose SDK logging (project/location precedence, AFC enabled messages)
    import logging
    logging.getLogger("google.genai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
except ImportError:
    HAS_GENAI_SDK = False


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


# Global token usage tracker
class TokenUsageTracker:
    """Tracks cumulative token usage across all LLM calls."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.calls_by_phase = {}
        self.current_phase = "unknown"
    
    def set_phase(self, phase: str):
        """Set the current extraction phase for tracking."""
        self.current_phase = phase
    
    def add_usage(self, input_tokens: int, output_tokens: int):
        """Add usage from an LLM call."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1
        
        if self.current_phase not in self.calls_by_phase:
            self.calls_by_phase[self.current_phase] = {"input": 0, "output": 0, "calls": 0}
        self.calls_by_phase[self.current_phase]["input"] += input_tokens
        self.calls_by_phase[self.current_phase]["output"] += output_tokens
        self.calls_by_phase[self.current_phase]["calls"] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "call_count": self.call_count,
            "by_phase": self.calls_by_phase,
        }
    
    def print_summary(self, model: str = "claude-opus-4-5"):
        """Print a formatted summary with cost estimates."""
        # Pricing per million tokens (as of Jan 2025)
        pricing = {
            # Claude models
            "claude-opus-4-5": (15.0, 75.0),
            "claude-sonnet-4": (3.0, 15.0),
            "claude-3-5-sonnet": (3.0, 15.0),
            # Gemini models (much cheaper)
            "gemini-2.5-pro": (1.25, 10.0),
            "gemini-2.5-flash": (0.075, 0.30),
            "gemini-3-flash": (0.50, 3.00),
            "gemini-3-flash-preview": (0.50, 3.00),
            # OpenAI models
            "gpt-4o": (2.50, 10.0),
            "gpt-4o-mini": (0.15, 0.60),
        }
        # Normalize model name for lookup (handle variations)
        model_lower = model.lower().replace("_", "-")
        input_rate, output_rate = pricing.get(model_lower, pricing.get(model, (1.0, 4.0)))
        
        input_cost = (self.total_input_tokens / 1_000_000) * input_rate
        output_cost = (self.total_output_tokens / 1_000_000) * output_rate
        total_cost = input_cost + output_cost
        
        print("\n" + "=" * 70)
        print("TOKEN USAGE SUMMARY")
        print("=" * 70)
        print(f"Model: {model}")
        print(f"Total LLM Calls: {self.call_count}")
        print()
        print("By Phase:")
        print("-" * 70)
        for phase, data in self.calls_by_phase.items():
            phase_cost = (data['input']/1e6 * input_rate) + (data['output']/1e6 * output_rate)
            print(f"  {phase:40} {data['input']:>8,} in / {data['output']:>7,} out  ${phase_cost:.2f}")
        print("-" * 70)
        print()
        print(f"Total Input Tokens:  {self.total_input_tokens:>12,}")
        print(f"Total Output Tokens: {self.total_output_tokens:>12,}")
        print(f"Total Tokens:        {self.total_input_tokens + self.total_output_tokens:>12,}")
        print()
        print(f"Input Cost:  ${input_cost:>8.2f}  (@${input_rate}/1M)")
        print(f"Output Cost: ${output_cost:>8.2f}  (@${output_rate}/1M)")
        print(f"TOTAL COST:  ${total_cost:>8.2f}")
        print("=" * 70)


# Global tracker instance
usage_tracker = TokenUsageTracker()


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
        # Gemini 3.x (preview) - use -preview suffix on Vertex AI
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
    
    # Vertex AI model name mappings (aliases -> actual model IDs)
    VERTEX_MODEL_ALIASES = {
        'gemini-3-flash': 'gemini-3-flash-preview',
        'gemini-3-pro': 'gemini-3-pro-preview',
    }
    
    # Models that require global endpoint (not regional like us-central1)
    GLOBAL_ENDPOINT_MODELS = ['gemini-3-flash', 'gemini-3-pro', 'gemini-3-flash-preview', 'gemini-3-pro-preview']
    
    # Models that are only available via AI Studio (not Vertex AI)
    AI_STUDIO_ONLY_MODELS = []  # Empty - route all models through Vertex AI when available
    
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
        has_vertex_config = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        is_ai_studio_only = model in self.AI_STUDIO_ONLY_MODELS
        is_gemini3 = model in self.GLOBAL_ENDPOINT_MODELS
        
        self.use_vertex = has_vertex_config and not is_ai_studio_only
        self.use_genai_sdk = is_gemini3 and HAS_GENAI_SDK and self.use_vertex
        
        if self.use_genai_sdk:
            # Gemini 3 models use google-genai SDK with Vertex AI backend
            # Use explicit client config instead of environment variables to avoid
            # polluting the environment for other models (like gemini-2.5-pro fallback)
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            self._genai_client = genai_new.Client(
                vertexai=True,
                project=project,
                location='global',  # Gemini 3 requires global endpoint
            )
        elif self.use_vertex:
            # Configure for Vertex AI (older models)
            import vertexai
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            # Ensure we use regional endpoint, not global (which may have been set by Gemini 3)
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            if location == 'global':
                location = 'us-central1'  # Fallback to us-central1 for non-Gemini-3 models
            vertexai.init(project=project, location=location)
        else:
            # Configure for Google AI Studio
            genai.configure(api_key=self.api_key)
    
    def _get_api_key_from_env(self) -> str:
        """Get Google API key from environment."""
        # Always need API key for AI Studio (including Gemini 3 models)
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
        if config.top_k is not None:
            gen_config_dict["top_k"] = config.top_k
        
        # Add JSON mode if requested
        if config.json_mode and self.supports_json_mode():
            gen_config_dict["response_mime_type"] = "application/json"
        
        # Convert messages to Gemini format
        full_prompt = self._format_messages_for_gemini(messages)
        
        if self.use_genai_sdk:
            return self._generate_genai_sdk(full_prompt, gen_config_dict)
        elif self.use_vertex:
            return self._generate_vertex(full_prompt, gen_config_dict)
        else:
            return self._generate_ai_studio(full_prompt, gen_config_dict)
    
    def _generate_genai_sdk(self, prompt: str, gen_config_dict: dict) -> LLMResponse:
        """Generate using google-genai SDK with Vertex AI backend (for Gemini 3 models)."""
        # Map model aliases to actual model IDs
        model_id = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        
        # Build config with safety settings completely disabled
        # Per https://ai.google.dev/gemini-api/docs/safety-settings
        # BLOCK_NONE = don't block any content regardless of probability
        # 
        # Disable thinking mode for Gemini 3 models to reduce token consumption
        # Per https://ai.google.dev/gemini-api/docs/thought-signatures
        # thinking_budget=0 disables thinking entirely
        config = genai_types.GenerateContentConfig(
            temperature=gen_config_dict.get("temperature", 0.0),
            max_output_tokens=gen_config_dict.get("max_output_tokens"),
            stop_sequences=gen_config_dict.get("stop_sequences"),
            top_p=gen_config_dict.get("top_p"),
            top_k=gen_config_dict.get("top_k"),
            response_mime_type=gen_config_dict.get("response_mime_type"),
            # Disable thinking to reduce token usage and avoid 429 rate limits
            thinking_config=genai_types.ThinkingConfig(
                thinking_budget=0,  # 0 = DISABLED, -1 = AUTOMATIC
            ),
            # Disable all safety filters for clinical/medical content
            safety_settings=[
                genai_types.SafetySetting(
                    category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai_types.SafetySetting(
                    category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai_types.SafetySetting(
                    category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai_types.SafetySetting(
                    category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
        )
        
        try:
            # Wrap API call with retry logic for 429 rate limit errors
            def make_request():
                return self._genai_client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=config,
                )
            
            response = _retry_with_backoff(make_request)
            
            # Extract usage information
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0) or 0,
                }
                # Track usage globally
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response
            )
        
        except Exception as e:
            raise RuntimeError(f"Gemini 3 (google-genai SDK) call failed for model '{self.model}': {e}")
    
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
        
        # Map model aliases to actual Vertex AI model IDs
        vertex_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        
        # Create model instance (safety_settings passed to generate_content, not constructor)
        model = GenerativeModel(vertex_model)
        
        try:
            # Wrap API call with retry logic for 429 rate limit errors
            def make_request():
                return model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
            
            response = _retry_with_backoff(make_request)
            
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": response.usage_metadata.total_token_count or 0
                }
                # Track usage globally
                usage_tracker.add_usage(input_tokens, output_tokens)
            
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
        """Generate using Google AI Studio (for Gemini 3 models)."""
        generation_config = genai.types.GenerationConfig(**gen_config_dict)
        
        # Map model aliases to actual AI Studio model IDs (same as Vertex)
        ai_studio_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        
        model = genai.GenerativeModel(
            ai_studio_model,
            generation_config=generation_config,
            safety_settings=self.SAFETY_SETTINGS,
        )
        
        try:
            # Wrap API call with retry logic for 429 rate limit errors
            def make_request():
                return model.generate_content(prompt)
            
            response = _retry_with_backoff(make_request)
            
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": response.usage_metadata.total_token_count or 0
                }
                # Track usage globally
                usage_tracker.add_usage(input_tokens, output_tokens)
            
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
        
        # Make API call with streaming to handle long operations
        # Anthropic requires streaming for operations >10 minutes
        try:
            import logging
            logger = logging.getLogger(__name__)
            
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
                logger.warning(
                    f"Claude response was truncated (max_tokens reached). "
                    f"Used {output_tokens} tokens. Consider increasing max_tokens."
                )
            
            # Log warning if empty response
            if not content:
                logger.warning(
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
