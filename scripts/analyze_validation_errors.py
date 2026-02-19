#!/usr/bin/env python
"""Aggregate and analyze validation errors across all trial outputs.

Reads 5 validation files per trial:
  - schema_validation.json   (JSON Schema conformance)
  - usdm_validation.json     (USDM structural rules)
  - integrity_report.json    (Referential integrity)
  - conformance_report.json  (CDISC CORE rules)
  - compliance_log.json      (Non-USDM property audit)
"""

import json
import glob
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parent.parent / "output"


def load_json_safe(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def normalize_msg(msg):
    """Normalize a message for grouping: strip UUIDs, indices, long values."""
    msg = re.sub(r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'", "'<UUID>'", msg)
    msg = re.sub(r"\[\d+\]", "[N]", msg)
    msg = re.sub(r"'[^']{50,}'", "'<value>'", msg)
    return msg


# ── Collectors ─────────────────────────────────────────────────────────────


def collect_schema_validation(trials):
    """schema_validation.json → {valid, issues[{severity, message, path, ...}]}"""
    all_issues = []
    stats = {}
    for d in trials:
        sv = load_json_safe(os.path.join(d, "schema_validation.json"))
        if not sv:
            continue
        t = os.path.basename(d)
        issues = sv.get("issues", [])
        stats[t] = {"valid": sv.get("valid"), "count": len(issues),
                     "summary": sv.get("summary", {})}
        for iss in issues:
            all_issues.append({
                "trial": t,
                "severity": iss.get("severity", "error"),
                "message": iss.get("message", ""),
                "path": iss.get("path", ""),
                "schema_path": iss.get("schema_path", ""),
                "validator": iss.get("validator", ""),
            })
    return all_issues, stats


def collect_usdm_validation(trials):
    """usdm_validation.json → {valid, error_count, warning_count, issues[]}"""
    all_issues = []
    stats = {}
    for d in trials:
        uv = load_json_safe(os.path.join(d, "usdm_validation.json"))
        if not uv:
            continue
        t = os.path.basename(d)
        issues = uv.get("issues", [])
        stats[t] = {"valid": uv.get("valid"), "errors": uv.get("error_count", 0),
                     "warnings": uv.get("warning_count", 0)}
        for iss in issues:
            all_issues.append({
                "trial": t,
                "severity": iss.get("severity", "error"),
                "message": iss.get("message", ""),
                "path": iss.get("path", iss.get("location", "")),
                "rule": iss.get("rule", ""),
                "entity_type": iss.get("entity_type", ""),
            })
    return all_issues, stats


def collect_integrity(trials):
    """integrity_report.json → {summary, findings[{rule, severity, message, ...}]}"""
    all_findings = []
    stats = {}
    for d in trials:
        ir = load_json_safe(os.path.join(d, "integrity_report.json"))
        if not ir:
            continue
        t = os.path.basename(d)
        findings = ir.get("findings", [])
        stats[t] = ir.get("summary", {})
        for f in findings:
            all_findings.append({
                "trial": t,
                "severity": f.get("severity", "ERROR"),
                "rule": f.get("rule", ""),
                "message": f.get("message", ""),
                "entity_type": f.get("entity_type", ""),
                "entity_ids": f.get("entity_ids", []),
                "details": f.get("details", {}),
            })
    return all_findings, stats


def collect_core_compliance(trials):
    """compliance_log.json → {mode, stats, findings[]}"""
    all_findings = []
    stats = {}
    for d in trials:
        cl = load_json_safe(os.path.join(d, "compliance_log.json"))
        if not cl:
            continue
        t = os.path.basename(d)
        findings = cl.get("findings", []) if isinstance(cl, dict) else cl
        cl_stats = cl.get("stats", {}) if isinstance(cl, dict) else {}
        stats[t] = cl_stats
        for f in findings:
            if isinstance(f, dict):
                all_findings.append({
                    "trial": t,
                    "pass_name": f.get("pass_name", ""),
                    "entity_type": f.get("entity_type", ""),
                    "property": f.get("property", ""),
                    "action": f.get("action", ""),
                    "message": f.get("message", ""),
                    "old_value": f.get("old_value", ""),
                    "new_value": f.get("new_value", ""),
                })
    return all_findings, stats


# ── Groupers ───────────────────────────────────────────────────────────────


def group_by_pattern(items, key_fn, example_fn, max_examples=3):
    patterns = defaultdict(lambda: {"count": 0, "trials": set(), "examples": []})
    for item in items:
        key = key_fn(item)
        patterns[key]["count"] += 1
        patterns[key]["trials"].add(item["trial"])
        if len(patterns[key]["examples"]) < max_examples:
            patterns[key]["examples"].append(example_fn(item))
    return dict(sorted(patterns.items(), key=lambda x: -x[1]["count"]))


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    trials = sorted(glob.glob(str(OUTPUT_ROOT / "*_v800")))
    trials = [d for d in trials if os.path.exists(os.path.join(d, "protocol_usdm.json"))]
    print(f"Analyzing {len(trials)} trial outputs\n")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. SCHEMA VALIDATION
    # ═══════════════════════════════════════════════════════════════════════
    print("=" * 90)
    print("1. SCHEMA VALIDATION (JSON Schema conformance)")
    print("=" * 90)
    schema_issues, schema_stats = collect_schema_validation(trials)
    n_valid = sum(1 for s in schema_stats.values() if s.get("valid"))
    n_invalid = sum(1 for s in schema_stats.values() if not s.get("valid"))
    print(f"\nTrials: {n_valid} valid, {n_invalid} invalid")
    print(f"Total issues: {len(schema_issues)}")
    if schema_issues:
        print(f"Avg per trial: {len(schema_issues)/len(trials):.1f}")
        patterns = group_by_pattern(
            schema_issues,
            key_fn=lambda e: normalize_msg(e["message"]),
            example_fn=lambda e: {"trial": e["trial"], "path": e["path"][:120],
                                   "message": e["message"][:200], "validator": e["validator"]},
        )
        print(f"\n{len(patterns)} unique patterns:\n")
        for i, (pattern, data) in enumerate(patterns.items(), 1):
            if i > 40:
                print(f"  ... and {len(patterns)-40} more patterns")
                break
            print(f"  S{i:02d}. [{data['count']:4d} hits, {len(data['trials']):2d}/34 trials] {pattern[:130]}")
            ex = data["examples"][0]
            if ex.get("path"):
                print(f"       path: {ex['path'][:120]}")

    # ═══════════════════════════════════════════════════════════════════════
    # 2. USDM VALIDATION
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("2. USDM VALIDATION (Structural rules)")
    print("=" * 90)
    usdm_issues, usdm_stats = collect_usdm_validation(trials)
    total_errors = sum(s.get("errors", 0) for s in usdm_stats.values())
    total_warnings = sum(s.get("warnings", 0) for s in usdm_stats.values())
    n_valid_u = sum(1 for s in usdm_stats.values() if s.get("valid"))
    print(f"\nTrials: {n_valid_u} valid, {len(usdm_stats)-n_valid_u} invalid")
    print(f"Total: {total_errors} errors + {total_warnings} warnings = {len(usdm_issues)} issues")
    if usdm_issues:
        print(f"Avg per trial: {len(usdm_issues)/len(trials):.1f}")

        # Split by severity
        errs = [e for e in usdm_issues if e["severity"] == "error"]
        warns = [e for e in usdm_issues if e["severity"] == "warning"]

        for label, subset in [("ERRORS", errs), ("WARNINGS", warns)]:
            if not subset:
                continue
            patterns = group_by_pattern(
                subset,
                key_fn=lambda e: (e.get("rule", ""), normalize_msg(e["message"])),
                example_fn=lambda e: {"trial": e["trial"], "path": str(e.get("path", ""))[:120],
                                       "message": e["message"][:300], "entity_type": e.get("entity_type", "")},
            )
            print(f"\n  ── {label} ({len(subset)} total, {len(patterns)} patterns) ──\n")
            for i, ((rule, pattern), data) in enumerate(patterns.items(), 1):
                if i > 40:
                    print(f"    ... and {len(patterns)-40} more patterns")
                    break
                rule_str = f"[{rule}] " if rule else ""
                print(f"    U{i:02d}. [{data['count']:4d} hits, {len(data['trials']):2d}/34] {rule_str}{pattern[:120]}")
                ex = data["examples"][0]
                if ex.get("path"):
                    print(f"          path: {ex['path'][:100]}")

    # ═══════════════════════════════════════════════════════════════════════
    # 3. INTEGRITY REPORT
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("3. REFERENTIAL INTEGRITY")
    print("=" * 90)
    integrity_findings, integrity_stats = collect_integrity(trials)
    total_int_err = sum(s.get("errors", 0) for s in integrity_stats.values())
    total_int_warn = sum(s.get("warnings", 0) for s in integrity_stats.values())
    total_int_info = sum(s.get("info", 0) for s in integrity_stats.values())
    print(f"\nTotal: {total_int_err} errors, {total_int_warn} warnings, {total_int_info} info")
    if integrity_findings:
        patterns = group_by_pattern(
            integrity_findings,
            key_fn=lambda f: (f.get("rule", ""), f.get("severity", ""), normalize_msg(f["message"])),
            example_fn=lambda f: {"trial": f["trial"], "message": f["message"][:300],
                                   "entity_type": f.get("entity_type", ""),
                                   "entity_ids": f.get("entity_ids", [])[:3]},
        )
        print(f"{len(patterns)} patterns:\n")
        for i, ((rule, sev, pattern), data) in enumerate(patterns.items(), 1):
            if i > 40:
                print(f"  ... and {len(patterns)-40} more patterns")
                break
            print(f"  I{i:02d}. [{data['count']:4d} hits, {len(data['trials']):2d}/34] [{sev}] rule={rule}")
            print(f"       {pattern[:140]}")
            ex = data["examples"][0]
            if ex.get("entity_type"):
                print(f"       entity_type: {ex['entity_type']}")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. CORE COMPLIANCE (non-USDM properties)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("4. CORE COMPLIANCE (Non-USDM properties audit)")
    print("=" * 90)
    core_findings, core_stats = collect_core_compliance(trials)
    print(f"\nTotal findings: {len(core_findings)} across {len(core_stats)} trials")
    if core_findings:
        print(f"Avg per trial: {len(core_findings)/len(trials):.1f}")
        patterns = group_by_pattern(
            core_findings,
            key_fn=lambda f: (f.get("pass_name", ""), f.get("entity_type", ""),
                              f.get("property", ""), f.get("action", "")),
            example_fn=lambda f: {"trial": f["trial"],
                                   "old_value": str(f.get("old_value", ""))[:80],
                                   "new_value": str(f.get("new_value", ""))[:80],
                                   "message": f.get("message", "")[:200]},
        )
        print(f"{len(patterns)} patterns:\n")

        # Group by entity_type for cleaner output
        by_entity = defaultdict(list)
        for (pn, et, pr, ac), data in patterns.items():
            by_entity[et].append((pn, pr, ac, data))

        c_idx = 0
        for entity in sorted(by_entity.keys()):
            props = by_entity[entity]
            entity_total = sum(d["count"] for _, _, _, d in props)
            entity_trials = set()
            for _, _, _, d in props:
                entity_trials.update(d["trials"])
            print(f"\n  {entity} ({entity_total} hits, {len(entity_trials)} trials)")
            for pn, pr, ac, data in sorted(props, key=lambda x: -x[3]["count"]):
                c_idx += 1
                print(f"    C{c_idx:02d}. [{data['count']:4d}x, {len(data['trials']):2d}/34] .{pr}")
                ex = data["examples"][0]
                if ex.get("message"):
                    print(f"          {ex['message'][:120]}")

    # ── SAVE JSON REPORT ──────────────────────────────────────────────────
    report = {
        "summary": {
            "trials_analyzed": len(trials),
            "schema_issues": len(schema_issues),
            "usdm_issues": len(usdm_issues),
            "integrity_findings": len(integrity_findings),
            "core_findings": len(core_findings),
        },
    }
    report_path = OUTPUT_ROOT / "validation_error_analysis.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
