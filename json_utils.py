def clean_llm_json(raw):
    raw = raw.strip()
    # Remove code block markers
    if raw.startswith('```json'):
        raw = raw[7:]
    if raw.startswith('```'):
        raw = raw[3:]
    if raw.endswith('```'):
        raw = raw[:-3]
    # Remove anything after the last closing brace
    last_brace = raw.rfind('}')
    if last_brace != -1:
        raw = raw[:last_brace+1]
    return raw
