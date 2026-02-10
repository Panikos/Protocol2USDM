"""
Tests for E22: Chunked EVS cache (per-code files instead of single JSON).

Validates:
- _key_to_filename() produces safe filenames
- Per-code file creation on _save_entry()
- Loading from per-code files
- Legacy monolithic cache auto-migration
- clear_cache() removes per-code files
- get_cache_stats() reports disk_files
- update_cache() deletes old per-code file before refresh
- Backward compatibility: cache still works end-to-end
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.evs_client import (
    EVSClient,
    _key_to_filename,
    CACHE_TTL_SECONDS,
)


# ── _key_to_filename ─────────────────────────────────────────────────

class TestKeyToFilename:

    def test_ncit_key(self):
        assert _key_to_filename("ncit:C85826") == "ncit_C85826.json"

    def test_ct_key(self):
        assert _key_to_filename("ct:phase i trial") == "ct_phase_i_trial.json"

    def test_slashes(self):
        assert _key_to_filename("a/b:c") == "a_b_c.json"

    def test_empty(self):
        assert _key_to_filename("") == ".json"


# ── Per-code file operations ──────────────────────────────────────────

class TestPerCodeFiles:

    def test_save_entry_creates_file(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        entry = {"_cached_at": time.time(), "data": {"code": "C123"}}
        client._save_entry("ncit:C123", entry)

        code_file = tmp_path / "codes" / "ncit_C123.json"
        assert code_file.exists()
        with open(code_file) as f:
            saved = json.load(f)
        assert saved["_key"] == "ncit:C123"
        assert saved["data"]["code"] == "C123"

    def test_save_entry_updates_memory(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        entry = {"_cached_at": time.time(), "data": {"code": "C456"}}
        client._save_entry("ncit:C456", entry)
        assert "ncit:C456" in client.cache
        assert client.cache["ncit:C456"]["data"]["code"] == "C456"

    def test_load_reads_per_code_files(self, tmp_path):
        codes_dir = tmp_path / "codes"
        codes_dir.mkdir(parents=True)

        # Write a per-code file
        entry = {"_key": "ncit:C789", "_cached_at": time.time(), "data": {"code": "C789"}}
        with open(codes_dir / "ncit_C789.json", "w") as f:
            json.dump(entry, f)

        client = EVSClient(cache_dir=tmp_path)
        assert "ncit:C789" in client.cache
        assert client.cache["ncit:C789"]["data"]["code"] == "C789"

    def test_corrupt_file_skipped(self, tmp_path):
        codes_dir = tmp_path / "codes"
        codes_dir.mkdir(parents=True)
        (codes_dir / "bad.json").write_text("not json{{{")

        client = EVSClient(cache_dir=tmp_path)
        assert len(client.cache) == 0  # corrupt file skipped


# ── Legacy migration ──────────────────────────────────────────────────

class TestLegacyMigration:

    def test_migrates_monolithic_to_per_code(self, tmp_path):
        # Create legacy monolithic file
        legacy = {
            "ncit:C100": {"_cached_at": time.time(), "data": {"code": "C100"}},
            "ncit:C200": {"_cached_at": time.time(), "data": {"code": "C200"}},
        }
        legacy_file = tmp_path / "nci_codes.json"
        with open(legacy_file, "w") as f:
            json.dump(legacy, f)

        client = EVSClient(cache_dir=tmp_path)

        # Legacy file renamed
        assert not legacy_file.exists()
        assert (tmp_path / "nci_codes.json.migrated").exists()

        # Per-code files created
        codes_dir = tmp_path / "codes"
        assert (codes_dir / "ncit_C100.json").exists()
        assert (codes_dir / "ncit_C200.json").exists()

        # Memory cache populated
        assert "ncit:C100" in client.cache
        assert "ncit:C200" in client.cache

    def test_migration_does_not_rerun(self, tmp_path):
        # Create legacy file
        legacy = {"ncit:C300": {"_cached_at": time.time(), "data": {"code": "C300"}}}
        with open(tmp_path / "nci_codes.json", "w") as f:
            json.dump(legacy, f)

        # First load migrates
        client1 = EVSClient(cache_dir=tmp_path)
        assert not (tmp_path / "nci_codes.json").exists()

        # Second load doesn't crash (no legacy file)
        client2 = EVSClient(cache_dir=tmp_path)
        assert "ncit:C300" in client2.cache

    def test_migration_skips_existing_per_code_files(self, tmp_path):
        codes_dir = tmp_path / "codes"
        codes_dir.mkdir(parents=True)

        # Pre-existing per-code file
        existing = {"_key": "ncit:C400", "_cached_at": time.time(), "data": {"code": "C400", "extra": True}}
        with open(codes_dir / "ncit_C400.json", "w") as f:
            json.dump(existing, f)

        # Legacy file with same key but different data
        legacy = {"ncit:C400": {"_cached_at": time.time(), "data": {"code": "C400"}}}
        with open(tmp_path / "nci_codes.json", "w") as f:
            json.dump(legacy, f)

        client = EVSClient(cache_dir=tmp_path)
        # Should keep the pre-existing file (has "extra": True)
        assert client.cache["ncit:C400"]["data"].get("extra") is True


# ── clear_cache ───────────────────────────────────────────────────────

class TestClearCache:

    def test_clears_memory_and_disk(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        client._save_entry("ncit:C500", {"_cached_at": time.time(), "data": {"code": "C500"}})
        assert len(client.cache) == 1

        client.clear_cache()
        assert len(client.cache) == 0
        assert len(list((tmp_path / "codes").glob("*.json"))) == 0


# ── get_cache_stats ───────────────────────────────────────────────────

class TestCacheStats:

    def test_reports_disk_files(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        client._save_entry("ncit:C600", {"_cached_at": time.time(), "data": {}})
        client._save_entry("ncit:C601", {"_cached_at": time.time(), "data": {}})

        stats = client.get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["disk_files"] == 2
        assert stats["fresh_entries"] == 2
        assert stats["stale_entries"] == 0

    def test_stale_entries(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        # Entry from the past (stale)
        client._save_entry("ncit:C700", {"_cached_at": 0, "data": {}})

        stats = client.get_cache_stats()
        assert stats["stale_entries"] == 1
        assert stats["fresh_entries"] == 0


# ── update_cache deletes old file ─────────────────────────────────────

class TestUpdateCache:

    def test_deletes_old_per_code_file(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        client._save_entry("ncit:C800", {"_cached_at": time.time(), "data": {"code": "C800"}})
        code_file = tmp_path / "codes" / "ncit_C800.json"
        assert code_file.exists()

        # Mock HTTP to return None (simulating offline)
        with patch.object(client, '_http_get', return_value=None):
            client.update_cache(["C800"])

        # Old file should be deleted (refresh failed, so no new file)
        assert not code_file.exists()
        assert "ncit:C800" not in client.cache


# ── End-to-end backward compat ────────────────────────────────────────

class TestBackwardCompat:

    def test_fetch_and_retrieve(self, tmp_path):
        """Simulate fetch → cache → retrieve cycle."""
        client = EVSClient(cache_dir=tmp_path)

        # Manually populate cache (simulating a successful API fetch)
        entry = {
            "_cached_at": time.time(),
            "data": {
                "id": "C15600",
                "code": "C15600",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "decode": "Phase I Trial",
                "instanceType": "Code",
            },
        }
        client._save_entry("ncit:C15600", entry)

        # Retrieve from cache
        result = client.cache.get("ncit:C15600")
        assert result is not None
        assert result["data"]["decode"] == "Phase I Trial"

        # Verify file on disk
        code_file = tmp_path / "codes" / "ncit_C15600.json"
        assert code_file.exists()

    def test_is_fresh_check(self, tmp_path):
        client = EVSClient(cache_dir=tmp_path)
        fresh_entry = {"_cached_at": time.time(), "data": {}}
        stale_entry = {"_cached_at": 0, "data": {}}

        assert client._is_fresh(fresh_entry) is True
        assert client._is_fresh(stale_entry) is False
