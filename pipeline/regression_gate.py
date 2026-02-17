"""
Regression Gate — Entity Count Comparison Between Runs

Saves entity counts after each pipeline run and compares against a baseline
(previous run) to detect significant drops that may indicate LLM variability
or code regressions.

Usage:
    from pipeline.regression_gate import check_regression, save_entity_stats

    stats = save_entity_stats(usdm_data, output_dir)
    warnings = check_regression(stats, baseline_dir, threshold=0.8)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def count_entities(data: Dict[str, Any]) -> Dict[str, int]:
    """
    Count entities by instanceType in a USDM JSON structure.

    Returns:
        Dict mapping instanceType → count
    """
    counts: Dict[str, int] = {}

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            inst = obj.get("instanceType")
            if inst:
                counts[inst] = counts.get(inst, 0) + 1
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return dict(sorted(counts.items()))


def count_key_entities(data: Dict[str, Any]) -> Dict[str, int]:
    """
    Count key USDM entities from known structural paths.

    More precise than instanceType counting — gives exact counts for
    entities the reviewer cares about.
    """
    counts: Dict[str, int] = {}

    try:
        sv = data.get("study", {}).get("versions", [{}])[0]
        sd = sv.get("studyDesigns", [{}])[0]

        counts["epochs"] = len(sd.get("epochs", []))
        counts["encounters"] = len(sd.get("encounters", []))
        counts["activities"] = len(sd.get("activities", []))
        counts["arms"] = len(sd.get("arms", []))
        counts["studyCells"] = len(sd.get("studyCells", []))
        counts["objectives"] = len(sd.get("objectives", []))
        counts["endpoints"] = sum(
            len(o.get("endpoints", []))
            for o in sd.get("objectives", []) if isinstance(o, dict)
        )
        counts["estimands"] = len(sd.get("estimands", []))
        counts["indications"] = len(sd.get("indications", []))
        counts["analysisPopulations"] = len(sd.get("analysisPopulations", []))

        pop = sd.get("population", {})
        criteria = pop.get("criteria", []) if pop else []
        counts["eligibilityCriteria"] = len(criteria)

        timelines = sd.get("scheduleTimelines", [])
        counts["scheduleTimelines"] = len(timelines)
        total_instances = sum(
            len(tl.get("instances", [])) for tl in timelines
        )
        counts["scheduledInstances"] = total_instances
        total_timings = sum(
            len(tl.get("timings", [])) for tl in timelines
        )
        counts["timings"] = total_timings

        counts["studyInterventions"] = len(sv.get("studyInterventions", []))
        counts["amendments"] = len(sv.get("amendments", []))
        counts["narrativeContentItems"] = len(
            sv.get("narrativeContentItems", [])
        )
        counts["abbreviations"] = len(sv.get("abbreviations", []))

    except (IndexError, KeyError, TypeError) as e:
        logger.warning(f"Error counting key entities: {e}")

    return counts


def save_entity_stats(
    data: Dict[str, Any], output_dir: str
) -> Dict[str, Any]:
    """
    Save entity statistics for the current run.

    Writes ``entity_stats.json`` to ``output_dir``.

    Returns:
        The stats dict that was saved.
    """
    stats = {
        "keyEntities": count_key_entities(data),
        "byInstanceType": count_entities(data),
        "totalByType": sum(count_entities(data).values()),
    }

    path = os.path.join(output_dir, "entity_stats.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    logger.info(f"  Entity stats saved to: {path}")

    return stats


def load_entity_stats(dir_path: str) -> Optional[Dict[str, Any]]:
    """Load entity_stats.json from a directory, or None if not found."""
    path = os.path.join(dir_path, "entity_stats.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_regression(
    current_stats: Dict[str, Any],
    baseline_dir: str,
    threshold: float = 0.80,
) -> List[Dict[str, Any]]:
    """
    Compare current entity counts against a baseline run.

    Args:
        current_stats: Stats from ``save_entity_stats``
        baseline_dir: Directory containing a previous ``entity_stats.json``
        threshold: Minimum ratio (current/baseline). Drops below this warn.

    Returns:
        List of warning dicts, each with ``entity``, ``current``, ``baseline``,
        ``ratio``, and ``severity`` keys. Empty list if no regressions.
    """
    baseline = load_entity_stats(baseline_dir)
    if baseline is None:
        logger.info(f"  No baseline entity_stats.json in {baseline_dir} — skipping regression check")
        return []

    warnings: List[Dict[str, Any]] = []

    cur_key = current_stats.get("keyEntities", {})
    base_key = baseline.get("keyEntities", {})

    for entity, base_count in base_key.items():
        cur_count = cur_key.get(entity, 0)
        if base_count == 0:
            continue
        ratio = cur_count / base_count

        if ratio < threshold:
            severity = "critical" if ratio < 0.5 else "warning"
            warnings.append({
                "entity": entity,
                "current": cur_count,
                "baseline": base_count,
                "ratio": round(ratio, 3),
                "severity": severity,
            })

    if warnings:
        logger.warning(
            f"  ⚠ REGRESSION GATE: {len(warnings)} entity count drops "
            f"detected (threshold={threshold:.0%})"
        )
        for w in warnings:
            icon = "🔴" if w["severity"] == "critical" else "🟡"
            logger.warning(
                f"    {icon} {w['entity']}: {w['baseline']} → {w['current']} "
                f"({w['ratio']:.0%})"
            )
    else:
        logger.info(
            f"  ✓ Regression gate passed — no entity count drops "
            f"below {threshold:.0%} threshold"
        )

    return warnings
