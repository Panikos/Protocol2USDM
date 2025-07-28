#!/usr/bin/env python3
"""Light-weight structural validator for SoA / USDM timeline linkage.

Checks the parent-child relationships that are not enforced by the
OpenAPI schema itself:

Epoch  ─┬─ Encounter (encounter.epochId)
        └─ PlannedTimepoint (plannedTimepoint.encounterId)

Encounter ─┬─ ScheduledActivityInstance (instance.encounterId)
           └─ (indirect via PT → encounterId)

Activity  ─┬─ ActivityTimepoint (activityTimepoint.activityId)
           └─ ScheduledActivityInstance.activityIds

PlannedTimepoint ─ ActivityTimepoint.plannedTimepointId

The script prints a summary and exits 0 if no linkage errors were found,
otherwise exits 2.
"""
from __future__ import annotations

import argparse
import logging
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class LinkError(str):
    """String subclass to mark validation errors."""


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_components(soa: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Return core timeline component arrays, tolerant of wrapper layouts."""
    # Common wrapper path: study.versions[0].timeline
    timeline = (
        soa.get("study", {})
        .get("versions", [{}])[0]
        .get("timeline", {})
    )

    # Some post-process scripts promote timeline under studyDesign → timeline
    if not timeline:
        timeline = (
            soa.get("studyDesign", {})
            .get("timeline", {})
        )

    return {
        "epochs": timeline.get("epochs", []),
        "encounters": timeline.get("encounters", []),
        "plannedTimepoints": timeline.get("plannedTimepoints", []),
        "activities": timeline.get("activities", []),
        "activityGroups": timeline.get("activityGroups", []),
        "activityTimepoints": timeline.get("activityTimepoints", []),
        "scheduleTimelines": timeline.get("scheduleTimelines", []),
    }


def validate_links(components: Dict[str, List[Dict[str, Any]]]) -> List[LinkError]:
    errors: List[LinkError] = []

    # Build ID sets for quick look-ups, treating hyphen and underscore as equivalent
    def _norm(s: str | None) -> str | None:
        return s.replace('-', '_') if isinstance(s, str) else s
    epochs = {_norm(e.get("id")) for e in components["epochs"] if e.get("id")}
    encounters = {_norm(e.get("id")) for e in components["encounters"] if e.get("id")}
    pts = {_norm(pt.get("id")) for pt in components["plannedTimepoints"] if pt.get("id")}
    activities = {_norm(a.get("id")) for a in components["activities"] if a.get("id")}

    # 1. encounter.epochId exists
    for enc in components["encounters"]:
        eid = enc.get("id")
        pid = _norm(enc.get("epochId"))
        if pid and pid not in epochs:
            errors.append(LinkError(f"Encounter {eid} references missing epochId '{pid}'."))

    # 2. plannedTimepoint.encounterId exists
    for pt in components["plannedTimepoints"]:
        ptid = pt.get("id")
        enc_id = _norm(pt.get("encounterId"))
        if enc_id and enc_id not in encounters:
            errors.append(LinkError(f"PlannedTimepoint {ptid} references missing encounterId '{enc_id}'."))

    # 3. activityTimepoint links exist
    for at in components["activityTimepoints"]:
        act_id = _norm(at.get("activityId"))
        pt_id = _norm(at.get("plannedTimepointId"))
        if act_id and act_id not in activities:
            errors.append(LinkError(f"ActivityTimepoint references unknown activityId '{act_id}'."))
        if pt_id and pt_id not in pts:
            errors.append(LinkError(f"ActivityTimepoint references unknown plannedTimepointId '{pt_id}'."))

    # 4. scheduleTimelines instances activities/encounters exist
    for timeline in components["scheduleTimelines"]:
        for inst in timeline.get("instances", []):
            if inst.get("instanceType") != "ScheduledActivityInstance":
                continue
            enc_id = _norm(inst.get("encounterId"))
            if enc_id and enc_id not in encounters:
                errors.append(LinkError(f"ScheduledActivityInstance references unknown encounterId '{enc_id}'."))
            for act_id_raw in inst.get("activityIds", []):
                act_id = _norm(act_id_raw)
                if act_id not in activities:
                    errors.append(LinkError(f"ScheduledActivityInstance references unknown activityId '{act_id}'."))

    return errors


def completeness_metrics(components: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    # Simple counts that we can log for pipeline monitoring
    return {k: len(v) for k, v in components.items() if isinstance(v, list)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate parent–child linkage in an SoA JSON file.")
    parser.add_argument("soa_file", help="Path to SoA JSON file.")
    args = parser.parse_args()

    soa_path = Path(args.soa_file)
    if not soa_path.exists():
        logger.error("File not found: %s", soa_path)
        sys.exit(1)

    try:
        soa_json = load_json(soa_path)
    except Exception as exc:
        logger.error("Could not parse JSON: %s", exc)
        sys.exit(1)

    components = get_components(soa_json)

    errs = validate_links(components)
    metrics = completeness_metrics(components)

    logger.info("[STRUCTURE VALIDATION] Entity counts:")
    for k, v in metrics.items():
        logger.info("  - %s: %s", k, v)

    if errs:
        logger.warning("[LINKAGE ERRORS] Detected:")
        for e in errs:
            logger.warning("  • %s", e)
        sys.exit(2)

    logger.info("All parent–child linkages are consistent.")


if __name__ == "__main__":
    main()
