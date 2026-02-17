"""
Code Verification Service — EVS-backed validation and auto-population of CT codes.

Validates every code in the CodeRegistry against the NCI EVS REST API,
detects mismatches (code exists but maps to wrong concept), and can
auto-populate supplementary codelists from their parent concept codes.

Inspired by the unified terminology service in USDM2Synthetic.

Architecture
------------
1. Each supplementary codelist has a **parent concept code** in EVS
   (e.g. the "Intervention Type" codelist lives under a parent NCIt
   concept whose children are the valid values).
2. ``verify_registry()`` checks every code→decode pair in the registry
   against the live EVS API.
3. ``populate_from_evs()`` fetches children of a parent concept and
   builds a fresh CodeList — replacing hardcoded guesses with
   EVS-verified truth.
4. Results are cached locally so verification can run offline after
   the first fetch.

Usage
-----
    # One-shot verification (CI / pre-commit)
    python -m core.code_verification --verify

    # Auto-populate a codelist from its EVS parent
    python -m core.code_verification --populate interventionType

    # Full audit report
    python -m core.code_verification --report
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EVS REST API helpers (lightweight, no dependency on evs_client.py)
# ---------------------------------------------------------------------------

_EVS_BASE = "https://api-evsrest.nci.nih.gov/api/v1"
_CACHE_DIR = Path(__file__).parent / "evs_cache" / "verification"

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


def _evs_get(path: str, params: Optional[dict] = None, timeout: int = 15) -> Optional[dict]:
    """HTTP GET against EVS REST API with error handling."""
    if _requests is None:
        logger.warning("requests not installed — EVS verification unavailable")
        return None
    try:
        resp = _requests.get(f"{_EVS_BASE}{path}", params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("EVS request failed %s: %s", path, e)
        return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Result of verifying a single code against EVS."""
    code: str
    expected_decode: str
    evs_name: Optional[str]
    status: str  # "OK", "MISMATCH", "NOT_FOUND", "SKIP"
    detail: str = ""


@dataclass
class CodelistVerificationReport:
    """Verification report for a whole codelist."""
    key: str
    results: List[VerificationResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == "OK")

    @property
    def mismatch_count(self) -> int:
        return sum(1 for r in self.results if r.status == "MISMATCH")

    @property
    def not_found_count(self) -> int:
        return sum(1 for r in self.results if r.status == "NOT_FOUND")

    @property
    def passed(self) -> bool:
        return self.mismatch_count == 0 and self.not_found_count == 0


# ---------------------------------------------------------------------------
# Parent concept codes for supplementary codelists
#
# These are the NCIt concept codes whose *children* form the valid values
# for each codelist.  When a parent code is known, we can auto-populate
# the codelist from EVS instead of hardcoding individual codes.
#
# Pattern borrowed from USDM2Synthetic/terminology/nci_evs_service.py
# ---------------------------------------------------------------------------

CODELIST_PARENTS: Dict[str, str] = {
    # USDM CT codelists (parent = codelist concept code from USDM_CT.xlsx)
    # These are already loaded from the XLSX; parents here are for
    # supplementary codelists that have no XLSX entry.
    #
    # NOTE: StudyIntervention.type is NOT here because C98747
    # ("Intervention Type") children in NCIt are clinical subtypes
    # (e.g. "Interventional Procedure Type"), not the ICH M11 values
    # (Drug, Biological, Device, etc.).  Those ICH M11 values are
    # individual concepts from different NCIt hierarchies, linked via
    # ICH source synonyms.  Use EVS_VERIFIED_CODES instead.
}

# ---------------------------------------------------------------------------
# ICH M11 source-verified codes
#
# For codelists where the parent→children hierarchy in NCIt doesn't
# perfectly match what we need (e.g. the decode we display differs from
# the NCIt preferred name), we store the EVS-verified mapping here.
#
# Each entry: code → (decode_for_display, evs_preferred_name)
# These were verified against api-evsrest.nci.nih.gov on 2026-02-11.
# ---------------------------------------------------------------------------

EVS_VERIFIED_CODES: Dict[str, Dict[str, Tuple[str, str]]] = {
    "StudyIntervention.type": {
        "C1909":  ("DRUG",               "Pharmacologic Substance"),
        "C307":   ("BIOLOGICAL",          "Biological Agent"),
        "C16830": ("Device",              "Medical Device"),
        "C1505":  ("Dietary Supplement",  "Dietary Supplement"),
        "C15329": ("Procedure",           "Surgical Procedure"),
        "C15313": ("Radiation",           "Radiation Therapy"),
        "C17649": ("Other",               "Other"),
    },
}


# ---------------------------------------------------------------------------
# Verification service
# ---------------------------------------------------------------------------

class CodeVerificationService:
    """
    Validates CodeRegistry entries against the NCI EVS REST API.

    Can run in two modes:
    1. **Verify** — check every code→decode pair in the registry
    2. **Populate** — fetch children of a parent concept to build a
       fresh codelist (replaces hardcoded guesses)
    """

    def __init__(self, cache_dir: Path = _CACHE_DIR):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._concept_cache: Dict[str, dict] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_path(self, code: str) -> Path:
        return self._cache_dir / f"{code}.json"

    def _load_cache(self) -> None:
        for p in self._cache_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._concept_cache[p.stem] = data
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Ignoring invalid EVS cache file %s: %s", p, exc)

    def _save_to_cache(self, code: str, data: dict) -> None:
        data["_cached_at"] = time.time()
        self._concept_cache[code] = data
        try:
            self._cache_path(code).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.debug("Cache write failed for %s: %s", code, e)

    # ------------------------------------------------------------------
    # EVS lookups
    # ------------------------------------------------------------------

    def fetch_concept(self, code: str) -> Optional[dict]:
        """Fetch a single NCIt concept (cached)."""
        cached = self._concept_cache.get(code)
        if cached and (time.time() - cached.get("_cached_at", 0)) < 30 * 86400:
            return cached

        data = _evs_get(f"/concept/ncit/{code}", params={"include": "summary"})
        if data:
            self._save_to_cache(code, data)
        return data

    def fetch_children(self, parent_code: str) -> List[dict]:
        """Fetch children of a concept (the members of a codelist)."""
        cache_key = f"{parent_code}_children"
        cached = self._concept_cache.get(cache_key)
        if cached and (time.time() - cached.get("_cached_at", 0)) < 30 * 86400:
            return cached.get("children", [])

        data = _evs_get(f"/concept/ncit/{parent_code}/children")
        if data and isinstance(data, list):
            self._save_to_cache(cache_key, {"children": data})
            return data
        return []

    def fetch_concept_with_synonyms(self, code: str) -> Optional[dict]:
        """Fetch concept with full synonym detail (for ICH M11 source matching)."""
        cache_key = f"{code}_full"
        cached = self._concept_cache.get(cache_key)
        if cached and (time.time() - cached.get("_cached_at", 0)) < 30 * 86400:
            return cached

        data = _evs_get(
            f"/concept/ncit/{code}",
            params={"include": "summary,synonyms"},
        )
        if data:
            self._save_to_cache(cache_key, data)
        return data

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_code(self, code: str, expected_decode: str) -> VerificationResult:
        """Verify a single code against EVS."""
        concept = self.fetch_concept(code)
        if concept is None:
            return VerificationResult(
                code=code,
                expected_decode=expected_decode,
                evs_name=None,
                status="NOT_FOUND",
                detail=f"Code {code} not found in NCI EVS",
            )

        evs_name = concept.get("name", "")

        # Check if the expected decode matches EVS name or any synonym
        if self._names_match(expected_decode, evs_name):
            return VerificationResult(
                code=code,
                expected_decode=expected_decode,
                evs_name=evs_name,
                status="OK",
            )

        # Check synonyms
        synonyms = [s.get("name", "") for s in concept.get("synonyms", [])]
        for syn in synonyms:
            if self._names_match(expected_decode, syn):
                return VerificationResult(
                    code=code,
                    expected_decode=expected_decode,
                    evs_name=evs_name,
                    status="OK",
                    detail=f"Matched via synonym '{syn}'",
                )

        # Check if this code has an ICH M11 source synonym that matches
        ich_syns = [
            s.get("name", "")
            for s in concept.get("synonyms", [])
            if s.get("source") == "ICH"
        ]
        for syn in ich_syns:
            if self._names_match(expected_decode, syn):
                return VerificationResult(
                    code=code,
                    expected_decode=expected_decode,
                    evs_name=evs_name,
                    status="OK",
                    detail=f"Matched via ICH synonym '{syn}'",
                )

        return VerificationResult(
            code=code,
            expected_decode=expected_decode,
            evs_name=evs_name,
            status="MISMATCH",
            detail=f"Expected '{expected_decode}', EVS name is '{evs_name}'",
        )

    def verify_registry(self) -> List[CodelistVerificationReport]:
        """Verify all codes in the CodeRegistry against EVS."""
        from core.code_registry import registry

        reports: List[CodelistVerificationReport] = []

        for key in registry.keys():
            cl = registry.get_codelist(key)
            if cl is None:
                continue

            report = CodelistVerificationReport(key=key)
            for term in cl.terms:
                # Use EVS_VERIFIED_CODES if available for this codelist
                if key in EVS_VERIFIED_CODES:
                    verified = EVS_VERIFIED_CODES[key]
                    if term.code in verified:
                        display, evs_name = verified[term.code]
                        if self._names_match(term.decode, display):
                            report.results.append(VerificationResult(
                                code=term.code,
                                expected_decode=term.decode,
                                evs_name=evs_name,
                                status="OK",
                                detail="Matched via EVS_VERIFIED_CODES",
                            ))
                        else:
                            report.results.append(VerificationResult(
                                code=term.code,
                                expected_decode=term.decode,
                                evs_name=evs_name,
                                status="MISMATCH",
                                detail=f"Expected '{term.decode}', verified display is '{display}'",
                            ))
                        continue
                    # Code not in verified set — this code shouldn't be here
                    report.results.append(VerificationResult(
                        code=term.code,
                        expected_decode=term.decode,
                        evs_name=None,
                        status="MISMATCH",
                        detail=f"Code {term.code} not in EVS_VERIFIED_CODES for {key}",
                    ))
                    continue

                # Fall back to live EVS verification
                result = self.verify_code(term.code, term.decode)
                report.results.append(result)

            reports.append(report)

        return reports

    def verify_codelist(self, key: str) -> CodelistVerificationReport:
        """Verify a single codelist by key or alias."""
        from core.code_registry import registry

        cl = registry.get_codelist(key)
        report = CodelistVerificationReport(key=key)
        if cl is None:
            return report

        for term in cl.terms:
            result = self.verify_code(term.code, term.decode)
            report.results.append(result)

        return report

    # ------------------------------------------------------------------
    # Auto-population from EVS parent concepts
    # ------------------------------------------------------------------

    def populate_from_parent(self, key: str) -> Optional[List[dict]]:
        """
        Fetch children of a codelist's parent concept from EVS.

        Returns a list of {code, decode} dicts that should replace the
        hardcoded terms in the supplementary codelist.
        """
        parent_code = CODELIST_PARENTS.get(key)
        if not parent_code:
            logger.warning("No parent concept code for codelist %s", key)
            return None

        children = self.fetch_children(parent_code)
        if not children:
            logger.warning("No children found for parent %s (%s)", parent_code, key)
            return None

        terms = []
        for child in children:
            code = child.get("code", "")
            name = child.get("name", "")
            terms.append({"code": code, "decode": name})

        return terms

    def get_verified_terms(self, key: str) -> Optional[List[dict]]:
        """
        Get EVS-verified terms for a codelist.

        Prefers EVS_VERIFIED_CODES (manually curated with display names),
        falls back to populate_from_parent (auto-discovered).
        """
        if key in EVS_VERIFIED_CODES:
            return [
                {"code": code, "decode": display}
                for code, (display, _evs_name) in EVS_VERIFIED_CODES[key].items()
            ]
        return self.populate_from_parent(key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _names_match(a: str, b: str) -> bool:
        """Case-insensitive match with common synonym handling."""
        if not a or not b:
            return False
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()
        if a_lower == b_lower:
            return True
        # Partial containment
        if a_lower in b_lower or b_lower in a_lower:
            return True
        return False

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(self, reports: List[CodelistVerificationReport]) -> str:
        """Generate a human-readable verification report."""
        lines = [
            "=" * 70,
            "Code Registry Verification Report",
            "=" * 70,
            "",
        ]

        total_ok = 0
        total_mismatch = 0
        total_not_found = 0

        for report in reports:
            if not report.results:
                continue

            total_ok += report.ok_count
            total_mismatch += report.mismatch_count
            total_not_found += report.not_found_count

            if report.passed:
                lines.append(f"  [PASS] {report.key} ({report.ok_count} codes)")
            else:
                lines.append(f"  [FAIL] {report.key}")
                for r in report.results:
                    if r.status == "OK":
                        continue
                    marker = "MISMATCH" if r.status == "MISMATCH" else "NOT_FOUND"
                    lines.append(f"         [{marker}] {r.code}: {r.detail}")

        lines.extend([
            "",
            "-" * 70,
            f"Total: {total_ok} OK, {total_mismatch} MISMATCH, {total_not_found} NOT_FOUND",
            "-" * 70,
        ])

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Code Registry Verification")
    parser.add_argument("--verify", action="store_true", help="Verify all registry codes")
    parser.add_argument("--verify-codelist", type=str, help="Verify a single codelist")
    parser.add_argument("--populate", type=str, help="Populate codelist from EVS parent")
    parser.add_argument("--report", action="store_true", help="Full audit report")
    args = parser.parse_args()

    svc = CodeVerificationService()

    if args.verify or args.report:
        reports = svc.verify_registry()
        print(svc.generate_report(reports))
        failed = sum(r.mismatch_count + r.not_found_count for r in reports)
        sys.exit(1 if failed > 0 else 0)

    elif args.verify_codelist:
        report = svc.verify_codelist(args.verify_codelist)
        print(svc.generate_report([report]))
        sys.exit(0 if report.passed else 1)

    elif args.populate:
        terms = svc.get_verified_terms(args.populate)
        if terms:
            print(f"Verified terms for {args.populate}:")
            for t in terms:
                print(f"  {t['code']}: {t['decode']}")
        else:
            print(f"No terms found for {args.populate}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
