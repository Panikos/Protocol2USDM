---
description: Generate M11 DOCX from a USDM JSON file and verify formatting
---

## Steps

1. Identify the USDM JSON to render. Typical locations:
   - Pipeline output: `output/<protocol_id>/protocol_usdm.json`
   - Published via web UI: `semantic/<protocol_id>/history/*.json`

2. Generate the DOCX:
// turbo
```
python -c "import json; from pathlib import Path; from rendering.m11_renderer import render_m11_docx; usdm = json.loads(Path(r'<path_to_usdm_json>').read_text(encoding='utf-8')); Path('output').mkdir(exist_ok=True); r = render_m11_docx(usdm, 'output/test_m11.docx'); print(f'Success: {r.success}'); print(f'Error: {r.error}'); print(f'Sections: {r.sections_rendered}'); print(f'With content: {r.sections_with_content}'); print(f'Words: {r.total_words}')"
```

3. Open `output/test_m11.docx` in Word and verify:
   - Title page: CONFIDENTIAL header, full title, metadata table
   - TOC field present (right-click → Update Field)
   - Heading hierarchy: L1=14pt ALL CAPS, L2=14pt bold, L3/L4/L5=12pt bold
   - Body text: 11pt Times New Roman, 1.15 line spacing
   - SoA table in §1.3 (may be landscape section)
   - Synopsis table in §1.1.2
   - Page breaks between §1–§11, appendices flow continuously
   - Headers/footers on all pages

4. Run the regression test suite:
```
python -m pytest tests/test_m11_regression.py -v
```
