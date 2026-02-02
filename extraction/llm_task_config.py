"""
LLM Task Configuration Loader

Loads task-specific LLM parameters from external config file (llm_config.yaml).
Supports YAML and JSON formats with environment variable overrides.

Usage:
    from extraction.llm_task_config import get_llm_task_config, to_llm_config
    
    # Get task-optimized config for an extractor
    task_config = get_llm_task_config("metadata", model="gemini-2.5-pro")
    llm_config = to_llm_config(task_config)
    
    # Use with LLM client
    response = client.generate(messages, llm_config)
"""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Config file search locations (relative to project root)
CONFIG_LOCATIONS = [
    "llm_config.yaml",
    "llm_config.json",
    "config/llm_config.yaml",
    "config/llm_config.json",
]


@dataclass
class TaskConfig:
    """Configuration for a specific task type."""
    temperature: Optional[float] = 0.0
    top_p: Optional[float] = 0.95
    top_k: Optional[int] = None
    max_tokens: Optional[int] = 8192
    json_mode: bool = True
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            "json_mode": self.json_mode,
        }


# Provider detection patterns
PROVIDER_PATTERNS = {
    "openai": ["gpt-", "o1", "o3"],
    "gemini": ["gemini-"],
    "claude": ["claude-"],
}


def detect_provider(model_name: Optional[str]) -> Optional[str]:
    """
    Detect the LLM provider from model name.
    
    Args:
        model_name: Model identifier (e.g., 'gemini-2.5-pro', 'gpt-4o')
        
    Returns:
        Provider name ('openai', 'gemini', 'claude') or None if unknown
    """
    if not model_name:
        return None
    
    model_lower = model_name.lower()
    for provider, patterns in PROVIDER_PATTERNS.items():
        for pattern in patterns:
            if pattern in model_lower:
                return provider
    return None


class LLMTaskConfigManager:
    """Manages LLM configurations for different extraction tasks."""
    
    _instance: Optional["LLMTaskConfigManager"] = None
    _config: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        config_path = self._find_config_file()
        
        if config_path:
            self._config = self._parse_config_file(config_path)
            logger.debug(f"Loaded LLM task config from {config_path}")
        else:
            logger.debug("No LLM config file found, using defaults")
            self._config = self._get_default_config()
        
        # Apply environment overrides
        self._apply_env_overrides()
    
    def _find_config_file(self) -> Optional[Path]:
        """Search for config file in standard locations."""
        # Check explicit env var first
        env_path = os.environ.get("LLM_CONFIG_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path
        
        # Search standard locations from project root
        # Go up from extraction/ to project root
        project_root = Path(__file__).parent.parent
        for location in CONFIG_LOCATIONS:
            path = project_root / location
            if path.exists():
                return path
        
        return None
    
    def _parse_config_file(self, path: Path) -> Dict[str, Any]:
        """Parse YAML or JSON config file."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if path.suffix in ('.yaml', '.yml'):
            try:
                import yaml
                return yaml.safe_load(content)
            except ImportError:
                logger.warning("PyYAML not installed, trying JSON parsing")
                return json.loads(content)
        else:
            return json.loads(content)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration when no file is found."""
        return {
            "task_types": {
                "deterministic": {
                    "temperature": 0.0,
                    "top_p": 0.95,
                    "top_k": None,
                    "max_tokens": 8192,
                    "json_mode": True,
                    "description": "Factual extraction from structured content",
                },
                "semantic": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "top_k": 40,
                    "max_tokens": 4096,
                    "json_mode": True,
                    "description": "Semantic entity resolution and mapping",
                },
                "structured_gen": {
                    "temperature": 0.2,
                    "top_p": 0.85,
                    "top_k": 40,
                    "max_tokens": 8192,
                    "json_mode": True,
                    "description": "Structured output generation and synthesis",
                },
                "narrative": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "top_k": None,
                    "max_tokens": 16384,
                    "json_mode": True,
                    "description": "Narrative and freeform text extraction",
                },
            },
            "extractor_mapping": {
                # SoA
                "soa_finder": "deterministic",
                "header_analyzer": "deterministic",
                "text_extractor": "deterministic",
                # Core
                "metadata": "deterministic",
                "eligibility": "deterministic",
                "objectives": "deterministic",
                "studydesign": "deterministic",
                "interventions": "deterministic",
                "procedures": "deterministic",
                # Execution Phase 1
                "dosing_regimen": "deterministic",
                "visit_window": "deterministic",
                "stratification": "deterministic",
                "time_anchor": "deterministic",
                "repetition": "deterministic",
                "sampling_density": "deterministic",
                # Execution Phase 2
                "entity_resolver": "semantic",
                "footnote_condition": "semantic",
                "crossover": "semantic",
                "traversal": "semantic",
                "binding": "semantic",
                # Execution Phase 3
                "state_machine": "structured_gen",
                "derived_variable": "structured_gen",
                "endpoint": "structured_gen",
                "execution_type": "structured_gen",
                # Narrative
                "narrative": "narrative",
                "amendments": "narrative",
                "scheduling": "narrative",
                "document_structure": "narrative",
                "sap": "narrative",
                "advanced": "narrative",
            },
            "defaults": {
                "task_type": "deterministic",
                "temperature": 0.0,
                "top_p": 0.95,
                "top_k": None,
                "max_tokens": 8192,
                "json_mode": True,
            },
            "provider_overrides": {
                "openai": {
                    "deterministic": {"top_p": 0.9, "top_k": None},
                    "semantic": {"top_p": 0.85, "top_k": None},
                    "structured_gen": {"top_p": 0.8, "top_k": None},
                    "narrative": {"top_p": 0.85, "top_k": None},
                },
                "gemini": {
                    "semantic": {"top_k": 40},
                    "structured_gen": {"top_k": 40},
                },
                "claude": {
                    "semantic": {"top_k": 40},
                    "structured_gen": {"top_k": 40},
                    "narrative": {"max_tokens": 12288},
                },
            },
            "model_overrides": {},
        }
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to defaults."""
        env_overrides = {
            "LLM_TEMPERATURE": ("defaults", "temperature", float),
            "LLM_TOP_P": ("defaults", "top_p", float),
            "LLM_TOP_K": ("defaults", "top_k", int),
            "LLM_MAX_TOKENS": ("defaults", "max_tokens", int),
        }
        
        for env_var, (section, key, type_fn) in env_overrides.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    self._config[section][key] = type_fn(value)
                    logger.debug(f"Applied env override: {env_var}={value}")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to apply env override {env_var}: {e}")
    
    def get_config_for_extractor(
        self,
        extractor_name: str,
        model: Optional[str] = None
    ) -> TaskConfig:
        """
        Get optimized LLM config for a specific extractor.
        
        Args:
            extractor_name: Name of the extractor (e.g., 'metadata', 'entity_resolver')
            model: Optional model name for model-specific overrides
            
        Returns:
            TaskConfig with appropriate parameters
        """
        # Get task type for this extractor
        mapping = self._config.get("extractor_mapping", {})
        default_task = self._config.get("defaults", {}).get("task_type", "deterministic")
        task_type = mapping.get(extractor_name, default_task)
        
        # Get task type config
        task_types = self._config.get("task_types", {})
        defaults = self._config.get("defaults", {})
        task_params = task_types.get(task_type, defaults)
        
        # Build config from task params with defaults fallback
        config = TaskConfig(
            temperature=task_params.get("temperature", defaults.get("temperature", 0.0)),
            top_p=task_params.get("top_p", defaults.get("top_p", 0.95)),
            top_k=task_params.get("top_k", defaults.get("top_k")),
            max_tokens=task_params.get("max_tokens", defaults.get("max_tokens", 8192)),
            json_mode=task_params.get("json_mode", defaults.get("json_mode", True)),
            description=task_params.get("description", ""),
        )
        
        # Apply provider-specific overrides (before model overrides)
        if model:
            provider = detect_provider(model)
            if provider:
                provider_overrides = self._config.get("provider_overrides", {}).get(provider, {})
                task_provider_overrides = provider_overrides.get(task_type, {})
                for key, value in task_provider_overrides.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        # Apply model-specific overrides (most specific, applied last)
        if model:
            model_overrides = self._config.get("model_overrides", {}).get(model, {})
            for key, value in model_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        return config
    
    def get_task_type(self, extractor_name: str) -> str:
        """Get the task type name for an extractor."""
        mapping = self._config.get("extractor_mapping", {})
        default_task = self._config.get("defaults", {}).get("task_type", "deterministic")
        return mapping.get(extractor_name, default_task)
    
    def list_extractors(self) -> Dict[str, str]:
        """List all configured extractors and their task types."""
        return dict(self._config.get("extractor_mapping", {}))
    
    def list_task_types(self) -> Dict[str, Dict[str, Any]]:
        """List all task types and their configurations."""
        return dict(self._config.get("task_types", {}))
    
    def reload(self) -> None:
        """Force reload of configuration from file."""
        self._config = None
        self._load_config()


# Module-level singleton instance
_manager: Optional[LLMTaskConfigManager] = None


def get_llm_task_config(
    extractor_name: str,
    model: Optional[str] = None
) -> TaskConfig:
    """
    Get LLM config for an extractor.
    
    Args:
        extractor_name: Name of the extractor (e.g., 'metadata', 'entity_resolver')
        model: Optional model name for model-specific overrides
        
    Returns:
        TaskConfig with optimized parameters
        
    Example:
        >>> config = get_llm_task_config("metadata")
        >>> print(config.temperature)  # 0.0 (deterministic)
        
        >>> config = get_llm_task_config("entity_resolver")
        >>> print(config.temperature)  # 0.1 (semantic)
        
        >>> config = get_llm_task_config("narrative")
        >>> print(config.temperature)  # 0.3 (narrative)
    """
    global _manager
    if _manager is None:
        _manager = LLMTaskConfigManager()
    return _manager.get_config_for_extractor(extractor_name, model)


def get_task_type(extractor_name: str) -> str:
    """Get the task type name for an extractor."""
    global _manager
    if _manager is None:
        _manager = LLMTaskConfigManager()
    return _manager.get_task_type(extractor_name)


def to_llm_config(task_config: TaskConfig) -> "LLMConfig":
    """
    Convert TaskConfig to LLMConfig for use with LLM providers.
    
    Args:
        task_config: TaskConfig from get_llm_task_config()
        
    Returns:
        LLMConfig instance for use with provider.generate()
    """
    from llm_providers import LLMConfig
    return LLMConfig(
        temperature=task_config.temperature if task_config.temperature is not None else 0.0,
        top_p=task_config.top_p,
        top_k=task_config.top_k,
        max_tokens=task_config.max_tokens,
        json_mode=task_config.json_mode,
    )


def reload_config() -> None:
    """Force reload of LLM task configuration from file."""
    global _manager
    if _manager is not None:
        _manager.reload()
    else:
        _manager = LLMTaskConfigManager()
