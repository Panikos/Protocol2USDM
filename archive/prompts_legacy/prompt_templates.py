"""
Prompt Template System

Provides structured, testable, optimized prompts following OpenAI best practices.
Templates are stored as YAML files for easy maintenance and version control.

Key Principles (from OpenAI Prompt Engineering):
1. Write clear instructions - Be specific, detailed, descriptive
2. Provide reference text - Supply schema, examples
3. Split complex tasks - Break into simpler subtasks
4. Give time to "think" - Allow step-by-step reasoning
5. Use external tools - Leverage schemas, validators
6. Test systematically - Use gold-standard examples

Usage:
    template = PromptTemplate.load("soa_extraction")
    messages = template.render(
        protocol_text="...",
        schema=usdm_schema,
        examples=few_shot_examples
    )
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import re
import json


@dataclass
class PromptSection:
    """A section of a prompt with metadata."""
    name: str
    content: str
    required_vars: List[str] = field(default_factory=list)
    optional_vars: List[str] = field(default_factory=list)


@dataclass
class PromptMetadata:
    """Metadata about a prompt template."""
    name: str
    version: str
    description: str
    task_type: str  # e.g., "extraction", "validation", "reconciliation"
    model_hints: Dict[str, Any] = field(default_factory=dict)  # Model-specific settings
    variables: Dict[str, str] = field(default_factory=dict)  # Variable descriptions


class PromptTemplate:
    """
    A structured prompt template with validation and rendering.
    
    Follows OpenAI best practices:
    - Clear scope definition with boundaries
    - Step-by-step instructions
    - Explicit definitions and examples
    - Structured output requirements
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        user_prompt: str,
        metadata: Optional[PromptMetadata] = None,
        sections: Optional[Dict[str, PromptSection]] = None
    ):
        """
        Initialize prompt template.
        
        Args:
            name: Template identifier
            system_prompt: System message template
            user_prompt: User message template
            metadata: Optional metadata about the template
            sections: Optional dictionary of named sections
        """
        self.name = name
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.metadata = metadata or PromptMetadata(
            name=name,
            version="1.0",
            description="",
            task_type="general"
        )
        self.sections = sections or {}
    
    def render(self, **kwargs) -> List[Dict[str, str]]:
        """
        Render template with variables to create messages.
        
        Args:
            **kwargs: Variables to substitute in template
        
        Returns:
            List of message dicts for LLM API
        
        Raises:
            ValueError: If required variables are missing
        """
        # Validate required variables
        missing_vars = self._check_required_variables(kwargs)
        if missing_vars:
            raise ValueError(
                f"Missing required variables for template '{self.name}': {missing_vars}"
            )
        
        # Render system prompt
        system_content = self._substitute_variables(self.system_prompt, kwargs)
        
        # Render user prompt
        user_content = self._substitute_variables(self.user_prompt, kwargs)
        
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
    
    def _substitute_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Substitute variables in template string.
        
        Supports:
        - {variable_name} - Simple substitution
        - {variable_name:default} - With default value
        - {{ or }} - Escaped braces (literal { or })
        
        Args:
            template: Template string
            variables: Variable values
        
        Returns:
            Rendered string
        """
        # First, protect escaped braces by replacing with placeholders
        OPEN_BRACE_PLACEHOLDER = "\x00OPEN_BRACE\x00"
        CLOSE_BRACE_PLACEHOLDER = "\x00CLOSE_BRACE\x00"
        
        template = template.replace('{{', OPEN_BRACE_PLACEHOLDER)
        template = template.replace('}}', CLOSE_BRACE_PLACEHOLDER)
        
        def replace_var(match):
            var_name = match.group(1)
            
            # Handle default values: {var:default}
            if ':' in var_name:
                var_name, default = var_name.split(':', 1)
                return str(variables.get(var_name.strip(), default.strip()))
            
            # No default - use empty string if not found
            return str(variables.get(var_name, ''))
        
        # Replace all {variable} patterns
        result = re.sub(r'\{([^}]+)\}', replace_var, template)
        
        # Restore escaped braces
        result = result.replace(OPEN_BRACE_PLACEHOLDER, '{')
        result = result.replace(CLOSE_BRACE_PLACEHOLDER, '}')
        
        return result
    
    def _check_required_variables(self, provided: Dict[str, Any]) -> List[str]:
        """
        Check which required variables are missing.
        
        Args:
            provided: Provided variable values
        
        Returns:
            List of missing variable names
        """
        # Remove escaped braces before checking for variables
        system_temp = self.system_prompt.replace('{{', '').replace('}}', '')
        user_temp = self.user_prompt.replace('{{', '').replace('}}', '')
        
        # Extract all {variable} patterns from both prompts
        pattern = r'\{([^}:]+)'
        
        system_vars = set(re.findall(pattern, system_temp))
        user_vars = set(re.findall(pattern, user_temp))
        
        all_vars = system_vars | user_vars
        provided_vars = set(provided.keys())
        
        # Filter out variables with defaults (contain :)
        required_vars = {
            v for v in all_vars 
            if f'{{{v}:' not in system_temp and f'{{{v}:' not in user_temp
        }
        
        missing = required_vars - provided_vars
        return sorted(missing)
    
    def get_required_variables(self) -> List[str]:
        """Get list of required variables for this template."""
        return self._check_required_variables({})
    
    def validate_structure(self) -> List[str]:
        """
        Validate template structure follows best practices.
        
        Returns:
            List of validation warnings/issues
        """
        issues = []
        
        # Check for clear objective
        if "objective" not in self.system_prompt.lower() and "goal" not in self.system_prompt.lower():
            issues.append("Missing clear objective/goal statement")
        
        # Check for output format definition
        if "output" not in self.system_prompt.lower() and "format" not in self.system_prompt.lower():
            issues.append("Missing explicit output format requirements")
        
        # Check for examples
        if "example" not in self.system_prompt.lower():
            issues.append("Consider adding examples for clarity")
        
        # Check for boundaries
        if "do not" not in self.system_prompt.lower() and "never" not in self.system_prompt.lower():
            issues.append("Consider adding boundary conditions (what NOT to do)")
        
        # Check length (too short might lack detail)
        if len(self.system_prompt) < 200:
            issues.append("System prompt seems short - consider adding more detail")
        
        # Check length (too long might be unfocused)
        if len(self.system_prompt) > 5000:
            issues.append("System prompt is very long - consider splitting into sections")
        
        return issues
    
    @classmethod
    def load(cls, template_name: str, prompts_dir: str = "prompts") -> "PromptTemplate":
        """
        Load template from YAML file.
        
        Args:
            template_name: Name of template (without .yaml extension)
            prompts_dir: Directory containing prompt files
        
        Returns:
            PromptTemplate instance
        
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If YAML is invalid
        """
        template_path = Path(prompts_dir) / f"{template_name}.yaml"
        
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template '{template_name}' not found at {template_path}"
            )
        
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Parse metadata
        metadata_dict = data.get('metadata', {})
        metadata = PromptMetadata(
            name=metadata_dict.get('name', template_name),
            version=metadata_dict.get('version', '1.0'),
            description=metadata_dict.get('description', ''),
            task_type=metadata_dict.get('task_type', 'general'),
            model_hints=metadata_dict.get('model_hints', {}),
            variables=metadata_dict.get('variables', {})
        )
        
        # Parse sections (optional)
        sections = {}
        if 'sections' in data:
            for section_name, section_data in data['sections'].items():
                sections[section_name] = PromptSection(
                    name=section_name,
                    content=section_data.get('content', ''),
                    required_vars=section_data.get('required_vars', []),
                    optional_vars=section_data.get('optional_vars', [])
                )
        
        return cls(
            name=template_name,
            system_prompt=data['system_prompt'],
            user_prompt=data['user_prompt'],
            metadata=metadata,
            sections=sections
        )
    
    def save(self, prompts_dir: str = "prompts") -> Path:
        """
        Save template to YAML file.
        
        Args:
            prompts_dir: Directory to save prompt files
        
        Returns:
            Path to saved file
        """
        prompts_path = Path(prompts_dir)
        prompts_path.mkdir(exist_ok=True)
        
        template_path = prompts_path / f"{self.name}.yaml"
        
        data = {
            'metadata': {
                'name': self.metadata.name,
                'version': self.metadata.version,
                'description': self.metadata.description,
                'task_type': self.metadata.task_type,
                'model_hints': self.metadata.model_hints,
                'variables': self.metadata.variables
            },
            'system_prompt': self.system_prompt,
            'user_prompt': self.user_prompt
        }
        
        if self.sections:
            data['sections'] = {
                name: {
                    'content': section.content,
                    'required_vars': section.required_vars,
                    'optional_vars': section.optional_vars
                }
                for name, section in self.sections.items()
            }
        
        with open(template_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=100)
        
        return template_path
    
    def __repr__(self) -> str:
        var_count = len(self.get_required_variables())
        return f"PromptTemplate(name='{self.name}', version='{self.metadata.version}', vars={var_count})"


class PromptRegistry:
    """
    Registry for managing multiple prompt templates.
    Provides caching and easy access to templates.
    """
    
    def __init__(self, prompts_dir: str = "prompts"):
        """
        Initialize registry.
        
        Args:
            prompts_dir: Directory containing prompt YAML files
        """
        self.prompts_dir = prompts_dir
        self._cache: Dict[str, PromptTemplate] = {}
    
    def get(self, template_name: str, use_cache: bool = True) -> PromptTemplate:
        """
        Get template by name.
        
        Args:
            template_name: Name of template
            use_cache: Whether to use cached version
        
        Returns:
            PromptTemplate instance
        """
        if use_cache and template_name in self._cache:
            return self._cache[template_name]
        
        template = PromptTemplate.load(template_name, self.prompts_dir)
        self._cache[template_name] = template
        return template
    
    def list_templates(self) -> List[str]:
        """
        List all available template names.
        
        Returns:
            List of template names (without .yaml extension)
        """
        prompts_path = Path(self.prompts_dir)
        if not prompts_path.exists():
            return []
        
        return [
            p.stem for p in prompts_path.glob("*.yaml")
        ]
    
    def clear_cache(self):
        """Clear template cache."""
        self._cache.clear()
    
    def reload(self, template_name: str) -> PromptTemplate:
        """
        Reload template from disk (bypassing cache).
        
        Args:
            template_name: Name of template to reload
        
        Returns:
            Freshly loaded PromptTemplate
        """
        if template_name in self._cache:
            del self._cache[template_name]
        return self.get(template_name, use_cache=False)


# Global registry instance
_default_registry = None

def get_registry(prompts_dir: str = "prompts") -> PromptRegistry:
    """
    Get global prompt registry instance.
    
    Args:
        prompts_dir: Directory containing prompts
    
    Returns:
        PromptRegistry singleton
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = PromptRegistry(prompts_dir)
    return _default_registry
