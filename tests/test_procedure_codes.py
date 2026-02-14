"""Tests for core.procedure_codes — Procedure Code Enrichment Service."""
import pytest
from unittest.mock import patch, MagicMock
from core.procedure_codes import (
    ProcedureCodeService,
    ProcedureCodeEntry,
    enrich_procedure_codes,
    _PROCEDURE_DB,
)


class TestEmbeddedDatabase:
    """Test the embedded procedure code database."""

    def test_db_has_entries(self):
        assert len(_PROCEDURE_DB) > 0, "Embedded DB should not be empty"

    @pytest.mark.parametrize("name", [
        "venipuncture", "blood draw", "ecg", "electrocardiogram",
        "mri", "ct scan", "physical examination", "vital signs",
        "complete blood count", "cbc", "biopsy", "infusion",
        "injection", "urinalysis", "hba1c", "pregnancy test",
    ])
    def test_common_procedures_exist(self, name):
        assert name in _PROCEDURE_DB, f"'{name}' should be in embedded DB"

    def test_entry_has_nci_code(self):
        entries = _PROCEDURE_DB["venipuncture"]
        nci = [e for e in entries if e.code_system == "NCI"]
        assert len(nci) == 1
        assert nci[0].code == "C28221"

    def test_entry_has_snomed_code(self):
        entries = _PROCEDURE_DB["venipuncture"]
        snomed = [e for e in entries if e.code_system == "SNOMED"]
        assert len(snomed) == 1
        assert snomed[0].code == "82078001"

    def test_entry_has_cpt_code(self):
        entries = _PROCEDURE_DB["venipuncture"]
        cpt = [e for e in entries if e.code_system == "CPT"]
        assert len(cpt) == 1
        assert cpt[0].code == "36415"

    def test_ecg_has_loinc(self):
        entries = _PROCEDURE_DB["ecg"]
        loinc = [e for e in entries if e.code_system == "LOINC"]
        assert len(loinc) == 1
        assert loinc[0].code == "11524-6"

    def test_entry_to_dict(self):
        entry = ProcedureCodeEntry("C28221", "NCI", "Venipuncture", "https://example.com")
        d = entry.to_dict()
        assert d["code"] == "C28221"
        assert d["codeSystem"] == "NCI"
        assert d["decode"] == "Venipuncture"
        assert d["url"] == "https://example.com"

    def test_entry_to_dict_no_url(self):
        entry = ProcedureCodeEntry("36415", "CPT", "Venipuncture")
        d = entry.to_dict()
        assert "url" not in d


class TestProcedureCodeService:
    """Test the ProcedureCodeService resolution logic."""

    def setup_method(self):
        self.svc = ProcedureCodeService(use_evs=False)

    def test_exact_match(self):
        codes = self.svc.resolve("Venipuncture")
        assert len(codes) >= 3  # NCI, SNOMED, CPT at minimum
        systems = {c["codeSystem"] for c in codes}
        assert "NCI" in systems
        assert "SNOMED" in systems

    def test_case_insensitive(self):
        codes = self.svc.resolve("VENIPUNCTURE")
        assert len(codes) >= 3

    def test_alias_match(self):
        """'blood draw' should resolve to venipuncture codes."""
        codes = self.svc.resolve("blood draw")
        assert len(codes) >= 3
        nci = next(c for c in codes if c["codeSystem"] == "NCI")
        assert nci["code"] == "C28221"

    def test_partial_match(self):
        """'12-lead ECG' should resolve via fuzzy match."""
        codes = self.svc.resolve("12-lead ECG")
        assert len(codes) >= 3
        systems = {c["codeSystem"] for c in codes}
        assert "NCI" in systems

    def test_suffix_stripping(self):
        """'blood pressure measurement' should match 'blood pressure'."""
        codes = self.svc.resolve("blood pressure measurement")
        assert len(codes) >= 2

    def test_unknown_procedure_returns_empty(self):
        codes = self.svc.resolve("xylophone tuning")
        assert codes == []

    def test_empty_name_returns_empty(self):
        codes = self.svc.resolve("")
        assert codes == []


class TestEnrichProcedureCodes:
    """Test the enrich_procedure_codes function."""

    def test_enriches_known_procedure(self):
        proc = {
            "id": "proc_1",
            "name": "Venipuncture",
            "code": {"id": "c1", "code": "36415", "codeSystem": "CPT", "decode": "Venipuncture"},
            "extensionAttributes": [],
        }
        enrich_procedure_codes(proc)
        
        # Should have x-procedureCodes extension
        ext = next(
            e for e in proc["extensionAttributes"]
            if e["url"].endswith("x-procedureCodes")
        )
        assert len(ext["value"]) >= 3
        
        # Primary code should be upgraded to NCI
        assert proc["code"]["code"] == "C28221"
        assert "NCI" in proc["code"]["codeSystem"] or "nci" in proc["code"]["codeSystem"].lower()

    def test_preserves_nci_primary_code(self):
        """If primary code is already NCI, it should not be overwritten."""
        proc = {
            "id": "proc_2",
            "name": "Electrocardiogram",
            "code": {
                "id": "c2",
                "code": "C168186",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "decode": "Electrocardiogram",
            },
            "extensionAttributes": [],
        }
        enrich_procedure_codes(proc)
        
        # Primary code should remain NCI C168186
        assert proc["code"]["code"] == "C168186"

    @patch("core.procedure_codes._service", ProcedureCodeService(use_evs=False))
    def test_no_enrichment_for_unknown(self):
        proc = {
            "id": "proc_3",
            "name": "Zylathrix Q29 phantasmal test",
            "code": {"id": "c3", "code": "", "codeSystem": "", "decode": ""},
        }
        enrich_procedure_codes(proc)
        
        # Should not add extension
        exts = proc.get("extensionAttributes", [])
        assert not any(e.get("url", "").endswith("x-procedureCodes") for e in exts)

    def test_no_duplicate_enrichment(self):
        proc = {
            "id": "proc_4",
            "name": "Venipuncture",
            "extensionAttributes": [{
                "id": "existing",
                "url": "https://protocol2usdm.io/extensions/x-procedureCodes",
                "value": [{"code": "C28221", "codeSystem": "NCI"}],
            }],
        }
        enrich_procedure_codes(proc)
        
        # Should still have only one x-procedureCodes extension
        count = sum(
            1 for e in proc["extensionAttributes"]
            if e["url"].endswith("x-procedureCodes")
        )
        assert count == 1

    def test_empty_name_skipped(self):
        proc = {"id": "proc_5", "name": ""}
        enrich_procedure_codes(proc)
        assert "extensionAttributes" not in proc or len(proc.get("extensionAttributes", [])) == 0

    def test_creates_extension_attributes_if_missing(self):
        proc = {
            "id": "proc_6",
            "name": "CBC",
        }
        enrich_procedure_codes(proc)
        assert "extensionAttributes" in proc
        ext = next(
            (e for e in proc["extensionAttributes"] if e["url"].endswith("x-procedureCodes")),
            None,
        )
        assert ext is not None
        assert len(ext["value"]) >= 3

    def test_all_code_dicts_have_required_fields(self):
        proc = {"id": "proc_7", "name": "ECG"}
        enrich_procedure_codes(proc)
        ext = next(
            e for e in proc["extensionAttributes"]
            if e["url"].endswith("x-procedureCodes")
        )
        for code_dict in ext["value"]:
            assert "code" in code_dict
            assert "codeSystem" in code_dict
            assert "decode" in code_dict


class TestEVSFallback:
    """Test EVS API fallback (mocked)."""

    @patch("core.procedure_codes.ProcedureCodeService._lookup_evs")
    def test_evs_fallback_used_when_embedded_misses(self, mock_evs):
        mock_evs.return_value = [
            ProcedureCodeEntry("C99999", "NCI", "Rare Procedure", "https://example.com"),
        ]
        svc = ProcedureCodeService(use_evs=True)
        codes = svc.resolve("some rare procedure not in DB")
        assert len(codes) == 1
        assert codes[0]["code"] == "C99999"

    @patch("core.procedure_codes.ProcedureCodeService._lookup_evs")
    def test_evs_not_called_when_embedded_hits(self, mock_evs):
        svc = ProcedureCodeService(use_evs=True)
        codes = svc.resolve("Venipuncture")
        mock_evs.assert_not_called()
        assert len(codes) >= 3
