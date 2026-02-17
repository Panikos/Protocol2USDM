"""Summarize pipeline run results for review."""
import json, os, sys

protocols = [
    ("Wilson's Disease", "NCT04573309_Wilsons_v717"),
    ("DAPA-HF", "NCT03057977_DAPA_HF_v717"),
    ("ADAURA", "NCT03036124_ADAURA_v717"),
]

for name, dir_name in protocols:
    base = f"output/{dir_name}"
    print(f"\n{'='*60}")
    print(f"  {name} ({dir_name})")
    print(f"{'='*60}")

    # Entity stats
    es_path = f"{base}/entity_stats.json"
    if os.path.exists(es_path):
        es = json.load(open(es_path))
        by_type = es.get("totalByType", es.get("byInstanceType", {}))
        total = sum(by_type.values()) if isinstance(by_type, dict) else "?"
        print(f"  Total entities:  {total}")
        if isinstance(by_type, dict):
            top = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:8]
            print(f"  Top types:       {', '.join(f'{k}={v}' for k,v in top)}")

    # USDM validation
    uv_path = f"{base}/usdm_validation.json"
    if os.path.exists(uv_path):
        uv = json.load(open(uv_path))
        schema_ok = uv.get("schema_validation", {}).get("valid", "?")
        semantic_ok = uv.get("semantic_validation", {}).get("valid", "?")
        missing = len(uv.get("semantic_validation", {}).get("missing_relationships", []))
        print(f"  Schema:          {'PASS' if schema_ok else 'FAIL'}")
        print(f"  Semantic:        {'PASS' if semantic_ok else 'FAIL'} ({missing} missing rels)")

    # M11 conformance
    mc_path = f"{base}/m11_conformance_report.json"
    if os.path.exists(mc_path):
        mc = json.load(open(mc_path))
        score = mc.get("overallScore", mc.get("overall_score", "?"))
        req = mc.get("totalRequiredPresent", mc.get("required_fields_present", "?"))
        req_total = mc.get("totalRequired", mc.get("required_fields_total", "?"))
        issues = mc.get("issues", [])
        print(f"  M11 conformance: {req}/{req_total} required ({score})")
        print(f"  M11 issues:      {len(issues)}")

    # M11 DOCX
    docx_path = f"{base}/m11_protocol.docx"
    if os.path.exists(docx_path):
        sz = os.path.getsize(docx_path)
        print(f"  M11 DOCX:        {sz // 1024}KB")
    else:
        print(f"  M11 DOCX:        NOT GENERATED")

    # Token usage
    tu_path = f"{base}/token_usage.json"
    if os.path.exists(tu_path):
        tu = json.load(open(tu_path))
        calls = tu.get("call_count", tu.get("total_calls", "?"))
        tokens = tu.get("total_tokens", "?")
        inp = tu.get("total_input_tokens", 0)
        out = tu.get("total_output_tokens", 0)
        cost = round(inp * 0.5 / 1_000_000 + out * 3.0 / 1_000_000, 2)
        print(f"  LLM calls:       {calls}")
        print(f"  Total tokens:    {tokens:,}" if isinstance(tokens, int) else f"  Total tokens:    {tokens}")
        print(f"  Cost:            ${cost}")

    # Integrity
    ir_path = f"{base}/integrity_report.json"
    if os.path.exists(ir_path):
        ir = json.load(open(ir_path))
        errs = ir.get("error_count", 0)
        warns = ir.get("warning_count", 0)
        print(f"  Integrity:       {errs} errors, {warns} warnings")

    # CDISC CORE
    core_path = f"{base}/core_conformance.json"
    if os.path.exists(core_path):
        core = json.load(open(core_path))
        print(f"  CDISC CORE:      {core.get('summary', '?')}")

    # Key SoA stats from the final SoA
    soa_path = f"{base}/9_final_soa.json"
    if os.path.exists(soa_path):
        soa = json.load(open(soa_path))
        acts = len(soa.get("activities", []))
        encs = len(soa.get("encounters", soa.get("timepoints", [])))
        eps = len(soa.get("epochs", []))
        print(f"  SoA:             {acts} activities, {encs} encounters, {eps} epochs")

print(f"\n{'='*60}")
print("  All runs complete.")
print(f"{'='*60}")
