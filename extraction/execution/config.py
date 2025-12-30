"""
Configuration Management for Execution Model Extraction

Provides configuration loading and defaults for extraction settings.
Supports YAML/JSON config files and environment variables.
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Default config file locations
CONFIG_LOCATIONS = [
    "execution_config.yaml",
    "execution_config.json",
    ".execution_config.yaml",
    ".execution_config.json",
]


@dataclass
class ExtractionConfig:
    """Configuration for execution model extraction."""
    
    # LLM settings
    model: str = "gemini-2.5-pro"
    use_llm: bool = True
    max_tokens: int = 4000
    temperature: float = 0.1
    
    # Extraction settings
    min_confidence: float = 0.5
    max_pages: int = 100
    
    # Phase control
    enable_phase1: bool = True  # Time anchors, repetitions, types
    enable_phase2: bool = True  # Crossover, traversal, footnotes
    enable_phase3: bool = True  # Endpoints, variables, state machine
    
    # Component control
    skip_endpoints: bool = False
    skip_variables: bool = False
    skip_state_machine: bool = False
    
    # Validation settings
    validate: bool = False
    require_state_machine: bool = False
    
    # Export settings
    export_csv: bool = False
    export_report: bool = False
    
    # Therapeutic area (for enhanced patterns)
    therapeutic_area: Optional[str] = None
    
    # Output settings
    output_dir: Optional[str] = None
    output_prefix: str = "execution_model"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionConfig":
        """Create config from dictionary."""
        # Filter to only valid fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)
    
    def merge(self, other: "ExtractionConfig") -> "ExtractionConfig":
        """Merge with another config, other takes precedence for non-None values."""
        result = ExtractionConfig()
        for field_name in self.__dataclass_fields__:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)
            # Use other's value if it's not None/default
            if other_val is not None:
                setattr(result, field_name, other_val)
            else:
                setattr(result, field_name, self_val)
        return result


@dataclass
class TherapeuticConfig:
    """Therapeutic area-specific configuration."""
    
    name: str = ""
    endpoints: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    patterns: Dict[str, List[str]] = field(default_factory=dict)


def load_config(
    config_path: Optional[str] = None,
    search_cwd: bool = True,
) -> ExtractionConfig:
    """
    Load configuration from file.
    
    Args:
        config_path: Explicit path to config file
        search_cwd: Whether to search current directory for config files
        
    Returns:
        ExtractionConfig with loaded settings
    """
    config = ExtractionConfig()
    
    # Try explicit path first
    if config_path:
        path = Path(config_path)
        if path.exists():
            config = _load_config_file(path)
            logger.info(f"Loaded config from {path}")
            return config
        else:
            logger.warning(f"Config file not found: {path}")
    
    # Search default locations
    if search_cwd:
        for filename in CONFIG_LOCATIONS:
            path = Path(filename)
            if path.exists():
                config = _load_config_file(path)
                logger.info(f"Loaded config from {path}")
                return config
    
    # Load from environment variables
    config = _load_from_env(config)
    
    return config


def _load_config_file(path: Path) -> ExtractionConfig:
    """Load config from YAML or JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if path.suffix in ('.yaml', '.yml'):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            logger.warning("PyYAML not installed, falling back to JSON parsing")
            data = json.loads(content)
    else:
        data = json.loads(content)
    
    return ExtractionConfig.from_dict(data)


def _load_from_env(config: ExtractionConfig) -> ExtractionConfig:
    """Override config with environment variables."""
    env_mappings = {
        "EXECUTION_MODEL": "model",
        "EXECUTION_USE_LLM": "use_llm",
        "EXECUTION_MIN_CONFIDENCE": "min_confidence",
        "EXECUTION_THERAPEUTIC_AREA": "therapeutic_area",
        "EXECUTION_VALIDATE": "validate",
        "EXECUTION_EXPORT_CSV": "export_csv",
        "EXECUTION_EXPORT_REPORT": "export_report",
    }
    
    for env_var, field_name in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Convert to appropriate type
            field_type = type(getattr(config, field_name))
            if field_type == bool:
                value = value.lower() in ('true', '1', 'yes')
            elif field_type == float:
                value = float(value)
            elif field_type == int:
                value = int(value)
            setattr(config, field_name, value)
    
    return config


def save_config(
    config: ExtractionConfig,
    path: str,
    format: str = "json",
) -> str:
    """
    Save configuration to file.
    
    Args:
        config: Configuration to save
        path: Output file path
        format: Output format ('json' or 'yaml')
        
    Returns:
        Path to saved file
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = config.to_dict()
    
    if format == "yaml":
        try:
            import yaml
            content = yaml.dump(data, default_flow_style=False)
        except ImportError:
            logger.warning("PyYAML not installed, using JSON format")
            content = json.dumps(data, indent=2)
    else:
        content = json.dumps(data, indent=2)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Saved config to {output_path}")
    return str(output_path)


def create_default_config(output_path: str = "execution_config.json") -> str:
    """Create a default config file with all options documented."""
    config = ExtractionConfig()
    return save_config(config, output_path)
