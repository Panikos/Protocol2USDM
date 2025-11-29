"""
Unit tests for prompt template system.
Tests template loading, rendering, validation, and YAML handling.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from pathlib import Path
import tempfile
import shutil
from prompt_templates import (
    PromptTemplate,
    PromptMetadata,
    PromptSection,
    PromptRegistry,
    get_registry
)


class TestPromptMetadata:
    """Test suite for PromptMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating metadata."""
        metadata = PromptMetadata(
            name="test_prompt",
            version="1.0",
            description="Test prompt",
            task_type="extraction"
        )
        assert metadata.name == "test_prompt"
        assert metadata.version == "1.0"
        assert metadata.task_type == "extraction"


class TestPromptTemplate:
    """Test suite for PromptTemplate class."""
    
    def test_init(self):
        """Test template initialization."""
        template = PromptTemplate(
            name="test",
            system_prompt="You are a helpful assistant.",
            user_prompt="Please help with {task}"
        )
        assert template.name == "test"
        assert "helpful" in template.system_prompt
    
    def test_render_simple(self):
        """Test rendering template with variables."""
        template = PromptTemplate(
            name="test",
            system_prompt="You are an expert.",
            user_prompt="Extract {data_type} from: {text}"
        )
        
        messages = template.render(data_type="activities", text="protocol text")
        
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert "activities" in messages[1]['content']
        assert "protocol text" in messages[1]['content']
    
    def test_render_with_defaults(self):
        """Test variable substitution with defaults."""
        template = PromptTemplate(
            name="test",
            system_prompt="Role: {role:assistant}",
            user_prompt="Task: {task}"
        )
        
        # Without providing 'role', should use default
        messages = template.render(task="extract data")
        assert "assistant" in messages[0]['content']
    
    def test_missing_required_variable_raises_error(self):
        """Test that missing required variables raise ValueError."""
        template = PromptTemplate(
            name="test",
            system_prompt="System",
            user_prompt="Process {required_var}"
        )
        
        with pytest.raises(ValueError, match="Missing required variables"):
            template.render()  # No variables provided
    
    def test_get_required_variables(self):
        """Test getting list of required variables."""
        template = PromptTemplate(
            name="test",
            system_prompt="You are a {role:expert}",
            user_prompt="Extract {data} from {source}"
        )
        
        required = template.get_required_variables()
        assert "data" in required
        assert "source" in required
        assert "role" not in required  # Has default
    
    def test_validate_structure(self):
        """Test structure validation."""
        # Good template
        good_template = PromptTemplate(
            name="good",
            system_prompt="""
            Objective: Extract data
            Output: Return JSON format
            Example: {"field": "value"}
            Do not invent data.
            """ * 5,  # Make it long enough
            user_prompt="Process this"
        )
        
        issues = good_template.validate_structure()
        assert len(issues) == 0
        
        # Bad template (too short, missing elements)
        bad_template = PromptTemplate(
            name="bad",
            system_prompt="Extract data",
            user_prompt="Do it"
        )
        
        issues = bad_template.validate_structure()
        assert len(issues) > 0
    
    def test_save_and_load(self):
        """Test saving and loading templates to/from YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create template
            template = PromptTemplate(
                name="test_save",
                system_prompt="System: {role}",
                user_prompt="User: {task}",
                metadata=PromptMetadata(
                    name="test_save",
                    version="1.5",
                    description="Test template",
                    task_type="test"
                )
            )
            
            # Save
            saved_path = template.save(tmpdir)
            assert saved_path.exists()
            
            # Load
            loaded = PromptTemplate.load("test_save", tmpdir)
            assert loaded.name == "test_save"
            assert loaded.metadata.version == "1.5"
            assert "{role}" in loaded.system_prompt
            assert "{task}" in loaded.user_prompt
    
    def test_load_nonexistent_raises_error(self):
        """Test loading non-existent template raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                PromptTemplate.load("does_not_exist", tmpdir)
    
    def test_repr(self):
        """Test string representation."""
        template = PromptTemplate(
            name="test",
            system_prompt="System",
            user_prompt="User with {var1} and {var2}"
        )
        
        repr_str = repr(template)
        assert "test" in repr_str
        assert "vars=2" in repr_str


class TestPromptRegistry:
    """Test suite for PromptRegistry."""
    
    def test_init(self):
        """Test registry initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(tmpdir)
            assert registry.prompts_dir == tmpdir
            assert len(registry._cache) == 0
    
    def test_get_template(self):
        """Test getting template from registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test template
            template = PromptTemplate(
                name="reg_test",
                system_prompt="System",
                user_prompt="User"
            )
            template.save(tmpdir)
            
            # Get from registry
            registry = PromptRegistry(tmpdir)
            loaded = registry.get("reg_test")
            
            assert loaded.name == "reg_test"
    
    def test_caching(self):
        """Test that registry caches templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create template
            template = PromptTemplate(name="cached", system_prompt="S", user_prompt="U")
            template.save(tmpdir)
            
            registry = PromptRegistry(tmpdir)
            
            # First get
            t1 = registry.get("cached")
            assert "cached" in registry._cache
            
            # Second get (should be cached)
            t2 = registry.get("cached")
            assert t1 is t2  # Same object
    
    def test_list_templates(self):
        """Test listing available templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple templates
            for name in ["temp1", "temp2", "temp3"]:
                t = PromptTemplate(name=name, system_prompt="S", user_prompt="U")
                t.save(tmpdir)
            
            registry = PromptRegistry(tmpdir)
            templates = registry.list_templates()
            
            assert len(templates) == 3
            assert "temp1" in templates
            assert "temp2" in templates
            assert "temp3" in templates
    
    def test_clear_cache(self):
        """Test clearing registry cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template = PromptTemplate(name="clear_test", system_prompt="S", user_prompt="U")
            template.save(tmpdir)
            
            registry = PromptRegistry(tmpdir)
            registry.get("clear_test")
            
            assert len(registry._cache) > 0
            registry.clear_cache()
            assert len(registry._cache) == 0
    
    def test_reload(self):
        """Test reloading template from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and load template
            template = PromptTemplate(name="reload_test", system_prompt="Original", user_prompt="U")
            template.save(tmpdir)
            
            registry = PromptRegistry(tmpdir)
            t1 = registry.get("reload_test")
            assert "Original" in t1.system_prompt
            
            # Modify template file
            template2 = PromptTemplate(name="reload_test", system_prompt="Modified", user_prompt="U")
            template2.save(tmpdir)
            
            # Reload
            t2 = registry.reload("reload_test")
            assert "Modified" in t2.system_prompt


class TestPromptSection:
    """Test suite for PromptSection."""
    
    def test_section_creation(self):
        """Test creating a prompt section."""
        section = PromptSection(
            name="objective",
            content="Extract clinical trial data",
            required_vars=["data_type"],
            optional_vars=["format"]
        )
        
        assert section.name == "objective"
        assert "clinical trial" in section.content
        assert "data_type" in section.required_vars


class TestIntegration:
    """Integration tests for template system."""
    
    def test_full_workflow(self):
        """Test complete workflow: create, save, load, render."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create template
            template = PromptTemplate(
                name="workflow_test",
                system_prompt="Role: {role}\nObjective: {objective}",
                user_prompt="Task: {task}\nData: {data}",
                metadata=PromptMetadata(
                    name="workflow_test",
                    version="2.0",
                    description="Test workflow",
                    task_type="test"
                )
            )
            
            # Save
            template.save(tmpdir)
            
            # Load via registry
            registry = PromptRegistry(tmpdir)
            loaded = registry.get("workflow_test")
            
            # Render
            messages = loaded.render(
                role="expert",
                objective="extract data",
                task="analyze",
                data="sample data"
            )
            
            assert len(messages) == 2
            assert "expert" in messages[0]['content']
            assert "extract data" in messages[0]['content']
            assert "analyze" in messages[1]['content']
            assert "sample data" in messages[1]['content']


class TestRealPrompts:
    """Test loading and validating real prompt files."""
    
    def test_load_soa_extraction_template(self):
        """Test loading the actual soa_extraction.yaml template."""
        # This assumes the prompts/ directory exists
        if Path("prompts/soa_extraction.yaml").exists():
            template = PromptTemplate.load("soa_extraction")
            
            assert template.name == "soa_extraction"
            assert str(template.metadata.version) == "2.0"  # YAML may load as float
            assert template.metadata.task_type == "extraction"
            
            # Check required variables
            required_vars = template.get_required_variables()
            assert "protocol_text" in required_vars
            assert "usdm_schema_text" in required_vars
            
            # Validate structure
            issues = template.validate_structure()
            # Should have minimal issues (it's optimized)
            assert len(issues) <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
