---
description: Step-by-step guide to add a new extraction phase to the pipeline
---

## Steps

1. **Create the extraction module** — create directory `extraction/<phase_name>/` with:
   - `__init__.py` — re-export key symbols
   - `schema.py` — Pydantic models for extracted data (match USDM entity structure)
   - `extractor.py` — async extraction function (LLM calls + parsing)
   - `prompts.py` — system and user prompt templates (use generic examples, no protocol-specific content)
   - `combiner.py` (optional) — merge extracted data into USDM JSON

2. **Create the pipeline phase** — create `pipeline/phases/<phase_name>.py`:
   ```python
   from pipeline.base_phase import BasePhase
   
   class MyPhase(BasePhase):
       name = "<phase_name>"
       dependencies = {"metadata"}  # declare upstream dependencies
       
       async def extract(self, context):
           from extraction.<phase_name>.extractor import extract_fn
           return await extract_fn(context)
       
       def combine(self, extracted, usdm):
           from extraction.<phase_name>.combiner import combine_fn
           return combine_fn(extracted, usdm)
   ```

3. **Register the phase** — add import and registration in `pipeline/phase_registry.py`

4. **Update M11 mapping** — if this phase populates a specific M11 section, update `core/m11_usdm_mapping.yaml`:
   - Set `extractor_phase` for the relevant section(s)
   - Add `usdm_entities` paths the phase writes to

5. **Add a composer** (if needed) — in `rendering/m11_renderer.py`:
   - Create `_compose_<section>(usdm: Dict) -> str`
   - Add to `entity_composers` dict in `render_m11_docx()`

6. **Add promotion rules** (if needed) — in `pipeline/orchestrator.py`:
   - Add a `_promote_<field>()` function
   - Wire into `_promote_extensions_to_usdm()`

7. **Write tests**:
   - Unit test in `tests/test_<phase_name>.py`
   - Add to regression test expectations in `tests/test_m11_regression.py`

8. **Verify**:
// turbo
   ```
   python -m pytest tests/ -v -k "<phase_name>"
   ```
