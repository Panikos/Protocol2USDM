# Prompts Directory

This directory contains version-tracked YAML templates for all LLM prompts used in the SoA extraction pipeline.

---

## Available Templates

### 1. `soa_extraction.yaml` (v2.0)
**Purpose:** Extract Schedule of Activities from protocol text  
**Used by:** `send_pdf_to_llm.py`  
**Model:** Gemini 2.5 Pro (default) or GPT-4/5  
**Key features:**
- Complete USDM schema embedded
- Comprehensive PlannedTimepoint guidance
- Encounter.type guidance
- Step-by-step extraction process

### 2. `vision_soa_extraction.yaml` (v2.0)
**Purpose:** Extract SoA from table images  
**Used by:** `extraction/structure.py`, `extraction/validator.py`  
**Model:** Gemini 2.5 Pro (default) or GPT-4o/5.1  
**Key features:**
- Vision-specific instructions
- Footnote marker handling
- Header structure integration
- Unified for both Gemini and OpenAI

### 3. `soa_reconciliation.yaml` (v2.0)
**Purpose:** Reconcile text and vision extractions  
**Used by:** Legacy (archived)  
**Note:** Reconciliation now handled programmatically in `extraction/pipeline.py`

### 4. `find_soa_pages.yaml` (v2.0)
**Purpose:** Identify which pages contain SoA tables  
**Used by:** `extraction/pipeline.py`  
**Model:** Any GPT or Gemini model  
**Key features:**
- Binary classification (yes/no)
- False positive reduction
- Table of Contents filtering

---

## Template Structure

All templates follow this format:

```yaml
metadata:
  name: template_name
  version: "2.0"
  description: "What this template does"
  task_type: extraction | reconciliation | classification
  model_hints:
    temperature: 0.0
    max_tokens: 16384
  variables:
    var1: "Description"
    var2: "Description"
  changelog:
    - version: "2.0"
      date: "2025-10-05"
      changes: "What changed in this version"

system_prompt: |
  Instructions for the LLM system role...

user_prompt: |
  Instructions for the user message...
  Can include {variables} for substitution.
```

---

## How to Use

### Loading a Template

```python
from prompt_templates import PromptTemplate

# Load template
template = PromptTemplate.load("soa_extraction", "prompts")

# Render with variables
messages = template.render(
    protocol_text="...",
    usdm_schema_text="..."
)

# Use messages
print(messages[0]["content"])  # System prompt
print(messages[1]["content"])  # User prompt
```

### Checking Version

Templates automatically log their version when loaded:

```
[INFO] Loaded text extraction template v2.0
```

---

## How to Edit

### Making an Improvement

1. **Edit the YAML file**
   ```bash
   vim prompts/vision_soa_extraction.yaml
   ```

2. **Increment version number**
   ```yaml
   metadata:
     version: "2.1"  # Was 2.0
   ```

3. **Add changelog entry**
   ```yaml
   changelog:
     - version: "2.1"
       date: "2025-10-06"
       changes: "Added explicit field validation checklist"
   ```

4. **Test your change**
   ```bash
   python benchmark_prompts.py --test-set test_data/
   ```

5. **Compare to previous version**
   - Did metrics improve?
   - Any regressions?
   - Accept, reject, or iterate

6. **Commit if accepted**
   ```bash
   git add prompts/vision_soa_extraction.yaml
   git commit -m "feat: improve vision extraction guidance (v2.1)"
   ```

---

## Version History

Track all versions in `VERSION_HISTORY.md` (create as needed):

```markdown
## vision_soa_extraction.yaml

### v2.1 (2025-10-06)
- Added field validation checklist
- Impact: Field population 79% → 86% (+7%)

### v2.0 (2025-10-05)
- Migrated from hardcoded Python strings to YAML
- Unified Gemini and OpenAI prompts
```

---

## Best Practices

### ✅ DO
- Always increment version when changing content
- Add detailed changelog entries
- Test changes with benchmark tool
- Document why you made the change
- Keep prompts focused on one task

### ❌ DON'T
- Change version without changing content
- Skip changelog entries
- Deploy without testing
- Make multiple changes at once
- Mix different tasks in one prompt

---

## Benchmarking

### Quick Test
```bash
# Test one PDF
python main_v2.py input/protocol.pdf --model gemini-2.5-pro
```

### Model Comparison
```bash
# Compare models across all input protocols
python benchmark_models.py --models gpt-5.1 gemini-3-pro-preview
```

---

## Metrics to Track

When optimizing prompts, track these metrics:

1. **Completeness Score** - % of expected entities extracted
2. **Field Population Rate** - % of required fields filled
3. **Linkage Accuracy** - % of cross-references correct
4. **Schema Validation** - Does output validate?
5. **Execution Time** - How long does it take?
6. **Error Rate** - How often does it fail?

---

## Troubleshooting

### Want to see what version is being used?
Check logs for:
```
[INFO] Loaded <template_name> v<version>
```

### Need to rollback?
```bash
git checkout HEAD~1 prompts/<template_name>.yaml
```

---

## Documentation

- **Main Docs:** `../README.md`, `../USER_GUIDE.md`
- **Quick Reference:** `../QUICK_REFERENCE.md`

---

**Last Updated:** 2025-11-28  
**System Version:** 2.0 (YAML-based templates)  
**Pipeline Version:** 6.1.2  
**Status:** Production Ready ✅
