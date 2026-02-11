"""
Tests for CodeVerificationService and CodeRegistry code correctness.

These tests validate that all supplementary codelist codes in the
CodeRegistry match the EVS-verified truth in code_verification.py.
No network access required — uses the curated EVS_VERIFIED_CODES mapping.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.code_registry import registry, CodeTerm
from core.code_verification import (
    CodeVerificationService,
    EVS_VERIFIED_CODES,
    VerificationResult,
)


class TestInterventionTypeCodes:
    """Verify StudyIntervention.type codes match EVS-verified values."""

    EXPECTED = {
        "C1909": "Drug",
        "C307": "Biological",
        "C16830": "Device",
        "C1505": "Dietary Supplement",
        "C15329": "Procedure",
        "C15313": "Radiation",
        "C17649": "Other",
    }

    def test_registry_has_intervention_type(self):
        cl = registry.get_codelist("StudyIntervention.type")
        assert cl is not None, "StudyIntervention.type codelist missing from registry"

    def test_intervention_type_code_count(self):
        cl = registry.get_codelist("StudyIntervention.type")
        assert len(cl.terms) == 7, f"Expected 7 terms, got {len(cl.terms)}"

    @pytest.mark.parametrize("code,decode", list(EXPECTED.items()))
    def test_intervention_type_code(self, code, decode):
        cl = registry.get_codelist("StudyIntervention.type")
        term = next((t for t in cl.terms if t.code == code), None)
        assert term is not None, f"Code {code} not found in StudyIntervention.type"
        assert term.decode == decode, (
            f"Code {code}: expected decode '{decode}', got '{term.decode}'"
        )

    def test_no_old_wrong_codes(self):
        """Ensure the previously-wrong codes are no longer present."""
        cl = registry.get_codelist("StudyIntervention.type")
        codes = {t.code for t in cl.terms}
        wrong_codes = {"C1261", "C16203", "C64858", "C15692", "C17998"}
        overlap = codes & wrong_codes
        assert not overlap, f"Old wrong codes still present: {overlap}"


class TestEVSVerifiedCodesConsistency:
    """Ensure EVS_VERIFIED_CODES and CodeRegistry stay in sync."""

    def test_all_verified_keys_exist_in_registry(self):
        for key in EVS_VERIFIED_CODES:
            cl = registry.get_codelist(key)
            assert cl is not None, f"EVS_VERIFIED_CODES key '{key}' not in registry"

    def test_registry_codes_match_verified(self):
        for key, verified in EVS_VERIFIED_CODES.items():
            cl = registry.get_codelist(key)
            if cl is None:
                continue
            registry_codes = {t.code: t.decode for t in cl.terms}
            for code, (display, _evs_name) in verified.items():
                assert code in registry_codes, (
                    f"{key}: verified code {code} not in registry"
                )
                assert registry_codes[code] == display, (
                    f"{key}: code {code} decode mismatch — "
                    f"registry='{registry_codes[code]}', verified='{display}'"
                )


class TestCodeVerificationService:
    """Test the verification service itself."""

    def test_verify_ok(self):
        svc = CodeVerificationService()
        result = svc.verify_code("C1909", "Pharmacologic Substance")
        assert result.status == "OK"

    def test_verify_mismatch(self):
        svc = CodeVerificationService()
        result = svc.verify_code("C1909", "Totally Wrong Name")
        # Will be MISMATCH or NOT_FOUND depending on cache state
        assert result.status in ("MISMATCH", "NOT_FOUND")

    def test_names_match_case_insensitive(self):
        assert CodeVerificationService._names_match("Drug", "drug")
        assert CodeVerificationService._names_match("Biological", "BIOLOGICAL")

    def test_names_match_partial(self):
        assert CodeVerificationService._names_match("Drug", "Pharmacologic Substance Drug")
        assert CodeVerificationService._names_match("Biological", "Biological Agent")

    def test_names_match_empty(self):
        assert not CodeVerificationService._names_match("", "something")
        assert not CodeVerificationService._names_match("something", "")

    def test_get_verified_terms(self):
        svc = CodeVerificationService()
        terms = svc.get_verified_terms("StudyIntervention.type")
        assert terms is not None
        assert len(terms) == 7
        codes = {t["code"] for t in terms}
        assert "C1909" in codes
        assert "C307" in codes

    def test_generate_report(self):
        from core.code_verification import CodelistVerificationReport
        report = CodelistVerificationReport(key="test", results=[
            VerificationResult("C1", "A", "A", "OK"),
            VerificationResult("C2", "B", "X", "MISMATCH", "wrong"),
        ])
        svc = CodeVerificationService()
        text = svc.generate_report([report])
        assert "MISMATCH" in text
        assert "1 OK" in text
        assert "1 MISMATCH" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
