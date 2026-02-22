"""
Google Gemini LLM Provider

Supports Gemini 1.5, 2.x, and 3.x models via Vertex AI or Google AI Studio.
Routes through Vertex AI when GOOGLE_CLOUD_PROJECT is set.
All safety controls are disabled for clinical protocol extraction.
"""

import asyncio
import os
import time
import logging
from typing import Dict, List, Optional, Any

from core.errors import ConfigurationError, LLMError, LLMRateLimitError, LLMConnectionError

from .base import LLMProvider, LLMConfig, LLMResponse, StreamChunk, StreamCallback, _retry_with_backoff
from .tracker import usage_tracker

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
        'gemini-3.1-pro-preview',
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
        'gemini-3.1-pro': 'gemini-3.1-pro-preview',
    }
    
    # Models that require global endpoint (not regional like us-central1)
    GLOBAL_ENDPOINT_MODELS = ['gemini-3.1-pro-preview', 'gemini-3.1-pro', 'gemini-3-flash', 'gemini-3-pro', 'gemini-3-flash-preview', 'gemini-3-pro-preview']
    
    # Models that support thinking_config (thinking_budget parameter)
    # Pro models do NOT support thinking_budget=0; only Flash/thinking models do
    THINKING_SUPPORTED_MODELS = [
        'gemini-3-flash', 'gemini-3-flash-preview',
        'gemini-2.5-flash',
    ]
    
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
            raise ConfigurationError("GOOGLE_API_KEY environment variable not set", model=self.model)
        return api_key
    
    def _supports_thinking(self) -> bool:
        """Check if current model supports thinking_config (thinking_budget)."""
        resolved = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        return resolved in self.THINKING_SUPPORTED_MODELS or self.model in self.THINKING_SUPPORTED_MODELS

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
            # Disable thinking to reduce token usage (only for models that support it)
            thinking_config=genai_types.ThinkingConfig(
                thinking_budget=0,
            ) if self._supports_thinking() else None,
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
            raise LLMError(f"Gemini 3 (google-genai SDK) call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
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
            raise LLMError(f"Vertex AI Gemini call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
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
            raise LLMError(f"Gemini AI Studio call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional["StreamCallback"] = None,
    ) -> LLMResponse:
        """Generate with native Gemini streaming, invoking *callback* per chunk."""
        if config is None:
            config = LLMConfig()

        gen_config_dict = {"temperature": config.temperature}
        if config.max_tokens:
            gen_config_dict["max_output_tokens"] = config.max_tokens
        if config.stop_sequences:
            gen_config_dict["stop_sequences"] = config.stop_sequences
        if config.top_p is not None:
            gen_config_dict["top_p"] = config.top_p
        if config.top_k is not None:
            gen_config_dict["top_k"] = config.top_k
        if config.json_mode and self.supports_json_mode():
            gen_config_dict["response_mime_type"] = "application/json"

        prompt = self._format_messages_for_gemini(messages)

        if self.use_genai_sdk:
            return self._stream_genai_sdk(prompt, gen_config_dict, callback)
        elif self.use_vertex:
            return self._stream_vertex(prompt, gen_config_dict, callback)
        else:
            return self._stream_ai_studio(prompt, gen_config_dict, callback)

    def _stream_genai_sdk(self, prompt: str, gen_config_dict: dict, callback) -> LLMResponse:
        """Streaming via google-genai SDK (Gemini 3 models)."""
        model_id = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        config = genai_types.GenerateContentConfig(
            temperature=gen_config_dict.get("temperature", 0.0),
            max_output_tokens=gen_config_dict.get("max_output_tokens"),
            stop_sequences=gen_config_dict.get("stop_sequences"),
            top_p=gen_config_dict.get("top_p"),
            top_k=gen_config_dict.get("top_k"),
            response_mime_type=gen_config_dict.get("response_mime_type"),
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0) if self._supports_thinking() else None,
            safety_settings=[
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
            ],
        )
        try:
            accumulated = ""
            for chunk_resp in self._genai_client.models.generate_content_stream(
                model=model_id, contents=prompt, config=config,
            ):
                text = chunk_resp.text or ""
                accumulated += text
                if callback and text:
                    callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))

            # Final usage from last chunk
            usage = None
            if hasattr(chunk_resp, 'usage_metadata') and chunk_resp.usage_metadata:
                inp = getattr(chunk_resp.usage_metadata, 'prompt_token_count', 0) or 0
                out = getattr(chunk_resp.usage_metadata, 'candidates_token_count', 0) or 0
                usage = {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": getattr(chunk_resp.usage_metadata, 'total_token_count', 0) or 0}
                usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True, usage=usage))

            return LLMResponse(content=accumulated, model=self.model, usage=usage)
        except Exception as e:
            from core.errors import LLMError
            raise LLMError(f"Gemini 3 streaming failed for model '{self.model}': {e}", model=self.model, cause=e)

    def _stream_vertex(self, prompt: str, gen_config_dict: dict, callback) -> LLMResponse:
        """Streaming via Vertex AI."""
        from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold
        generation_config = GenerationConfig(**gen_config_dict)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        }
        vertex_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        model = GenerativeModel(vertex_model)
        try:
            accumulated = ""
            last_chunk = None
            for chunk_resp in model.generate_content(
                prompt, generation_config=generation_config,
                safety_settings=safety_settings, stream=True,
            ):
                text = chunk_resp.text or ""
                accumulated += text
                last_chunk = chunk_resp
                if callback and text:
                    callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))

            usage = None
            if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                inp = last_chunk.usage_metadata.prompt_token_count or 0
                out = last_chunk.usage_metadata.candidates_token_count or 0
                usage = {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": last_chunk.usage_metadata.total_token_count or 0}
                usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True, usage=usage))

            return LLMResponse(content=accumulated, model=self.model, usage=usage)
        except Exception as e:
            from core.errors import LLMError
            raise LLMError(f"Vertex AI streaming failed for model '{self.model}': {e}", model=self.model, cause=e)

    def _stream_ai_studio(self, prompt: str, gen_config_dict: dict, callback) -> LLMResponse:
        """Streaming via AI Studio."""
        generation_config = genai.types.GenerationConfig(**gen_config_dict)
        ai_studio_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        model = genai.GenerativeModel(
            ai_studio_model, generation_config=generation_config,
            safety_settings=self.SAFETY_SETTINGS,
        )
        try:
            accumulated = ""
            last_chunk = None
            for chunk_resp in model.generate_content(prompt, stream=True):
                text = chunk_resp.text or ""
                accumulated += text
                last_chunk = chunk_resp
                if callback and text:
                    callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))

            usage = None
            if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                inp = last_chunk.usage_metadata.prompt_token_count or 0
                out = last_chunk.usage_metadata.candidates_token_count or 0
                usage = {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": last_chunk.usage_metadata.total_token_count or 0}
                usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True, usage=usage))

            return LLMResponse(content=accumulated, model=self.model, usage=usage)
        except Exception as e:
            from core.errors import LLMError
            raise LLMError(f"AI Studio streaming failed for model '{self.model}': {e}", model=self.model, cause=e)

    # ── Async methods ─────────────────────────────────────────────────

    async def agenerate(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Async generation. Native for genai SDK; thread-wrapped for Vertex/AI Studio."""
        if config is None:
            config = LLMConfig()

        gen_config_dict = self._build_gen_config(config)
        prompt = self._format_messages_for_gemini(messages)

        if self.use_genai_sdk:
            return await self._agenerate_genai_sdk(prompt, gen_config_dict)
        else:
            # Vertex AI and AI Studio SDKs lack native async — use thread
            return await asyncio.to_thread(self.generate, messages, config)

    async def agenerate_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        callback: Optional["StreamCallback"] = None,
    ) -> LLMResponse:
        """Async streaming. Native for genai SDK; thread-wrapped for Vertex/AI Studio."""
        if config is None:
            config = LLMConfig()

        gen_config_dict = self._build_gen_config(config)
        prompt = self._format_messages_for_gemini(messages)

        if self.use_genai_sdk:
            return await self._astream_genai_sdk(prompt, gen_config_dict, callback)
        else:
            return await asyncio.to_thread(self.generate_stream, messages, config, callback)

    async def _agenerate_genai_sdk(self, prompt: str, gen_config_dict: dict) -> LLMResponse:
        """Native async generation via google-genai SDK."""
        model_id = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        sdk_config = self._build_genai_sdk_config(gen_config_dict)
        try:
            response = await self._genai_client.aio.models.generate_content(
                model=model_id, contents=prompt, config=sdk_config,
            )
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                inp = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                out = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                usage = {"prompt_tokens": inp, "completion_tokens": out,
                         "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0) or 0}
                usage_tracker.add_usage(inp, out)
            return LLMResponse(
                content=response.text, model=self.model, usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response,
            )
        except Exception as e:
            raise LLMError(f"Gemini async generate failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    async def _astream_genai_sdk(self, prompt: str, gen_config_dict: dict, callback) -> LLMResponse:
        """Native async streaming via google-genai SDK."""
        model_id = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        sdk_config = self._build_genai_sdk_config(gen_config_dict)
        try:
            accumulated = ""
            last_chunk = None
            async for chunk_resp in self._genai_client.aio.models.generate_content_stream(
                model=model_id, contents=prompt, config=sdk_config,
            ):
                text = chunk_resp.text or ""
                accumulated += text
                last_chunk = chunk_resp
                if callback and text:
                    callback(StreamChunk(text=text, accumulated_text=accumulated, done=False))

            usage = None
            if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                inp = getattr(last_chunk.usage_metadata, 'prompt_token_count', 0) or 0
                out = getattr(last_chunk.usage_metadata, 'candidates_token_count', 0) or 0
                usage = {"prompt_tokens": inp, "completion_tokens": out,
                         "total_tokens": getattr(last_chunk.usage_metadata, 'total_token_count', 0) or 0}
                usage_tracker.add_usage(inp, out)

            if callback:
                callback(StreamChunk(text="", accumulated_text=accumulated, done=True, usage=usage))
            return LLMResponse(content=accumulated, model=self.model, usage=usage)
        except Exception as e:
            raise LLMError(f"Gemini async streaming failed for model '{self.model}': {e}",
                          model=self.model, cause=e)

    def _build_gen_config(self, config: LLMConfig) -> dict:
        """Build gen_config_dict from LLMConfig (shared by sync/async)."""
        d: dict = {"temperature": config.temperature}
        if config.max_tokens:
            d["max_output_tokens"] = config.max_tokens
        if config.stop_sequences:
            d["stop_sequences"] = config.stop_sequences
        if config.top_p is not None:
            d["top_p"] = config.top_p
        if config.top_k is not None:
            d["top_k"] = config.top_k
        if config.json_mode and self.supports_json_mode():
            d["response_mime_type"] = "application/json"
        return d

    def _build_genai_sdk_config(self, gen_config_dict: dict):
        """Build genai_types.GenerateContentConfig from dict (shared by sync/async)."""
        return genai_types.GenerateContentConfig(
            temperature=gen_config_dict.get("temperature", 0.0),
            max_output_tokens=gen_config_dict.get("max_output_tokens"),
            stop_sequences=gen_config_dict.get("stop_sequences"),
            top_p=gen_config_dict.get("top_p"),
            top_k=gen_config_dict.get("top_k"),
            response_mime_type=gen_config_dict.get("response_mime_type"),
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0) if self._supports_thinking() else None,
            safety_settings=[
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
            ],
        )

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
    
    def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        mime_type: str = "image/png",
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """Generate completion with an image using Gemini vision."""
        if config is None:
            config = LLMConfig()
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Build generation config
        gen_config_dict = {
            "temperature": config.temperature,
        }
        if config.max_tokens:
            gen_config_dict["max_output_tokens"] = config.max_tokens
        if config.json_mode and self.supports_json_mode():
            gen_config_dict["response_mime_type"] = "application/json"
        
        # Create image part
        image_part = {
            "mime_type": mime_type,
            "data": base64_image,
        }
        
        if self.use_genai_sdk:
            return self._generate_with_image_genai_sdk(prompt, image_part, gen_config_dict)
        elif self.use_vertex:
            return self._generate_with_image_vertex(prompt, image_data, mime_type, gen_config_dict)
        else:
            return self._generate_with_image_ai_studio(prompt, image_part, gen_config_dict)
    
    def _generate_with_image_genai_sdk(self, prompt: str, image_part: dict, gen_config_dict: dict) -> LLMResponse:
        """Vision generation via google-genai SDK."""
        model_id = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        config_obj = genai_types.GenerateContentConfig(
            temperature=gen_config_dict.get("temperature", 0.0),
            max_output_tokens=gen_config_dict.get("max_output_tokens"),
            response_mime_type=gen_config_dict.get("response_mime_type"),
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0) if self._supports_thinking() else None,
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
            def make_request():
                return self._genai_client.models.generate_content(
                    model=model_id,
                    contents=[prompt, {"inline_data": image_part}],
                    config=config_obj,
                )
            
            response = _retry_with_backoff(make_request)
            
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0) or 0,
                }
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response
            )
        except Exception as e:
            raise LLMError(f"Gemini 3 vision call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
    def _generate_with_image_vertex(self, prompt: str, image_data: bytes, mime_type: str, gen_config_dict: dict) -> LLMResponse:
        """Vision generation via Vertex AI."""
        from vertexai.generative_models import GenerativeModel, GenerationConfig, Part
        from vertexai.generative_models import HarmCategory, HarmBlockThreshold
        
        generation_config = GenerationConfig(**gen_config_dict)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        vertex_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        model = GenerativeModel(vertex_model)
        
        try:
            image_part_vertex = Part.from_data(data=image_data, mime_type=mime_type)
            
            def make_request():
                return model.generate_content(
                    [prompt, image_part_vertex],
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
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response
            )
        except Exception as e:
            raise LLMError(f"Vertex AI Gemini vision call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
    
    def _generate_with_image_ai_studio(self, prompt: str, image_part: dict, gen_config_dict: dict) -> LLMResponse:
        """Vision generation via AI Studio."""
        generation_config = genai.types.GenerationConfig(**gen_config_dict)
        ai_studio_model = self.VERTEX_MODEL_ALIASES.get(self.model, self.model)
        model = genai.GenerativeModel(
            ai_studio_model,
            generation_config=generation_config,
            safety_settings=self.SAFETY_SETTINGS,
        )
        
        try:
            def make_request():
                return model.generate_content([prompt, image_part])
            
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
                usage_tracker.add_usage(input_tokens, output_tokens)
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                usage=usage,
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
                raw_response=response
            )
        except Exception as e:
            raise LLMError(f"Gemini AI Studio vision call failed for model '{self.model}': {e}",
                          model=self.model, cause=e)
