"""Tests for evidence and hashing services."""

import json
import pytest
import tempfile
from pathlib import Path

from backend.app.utils.hashing import sha256_file, hash_directory
from backend.app.services.evidence_service import EvidenceService


def test_sha256_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h = sha256_file(f)
    assert len(h) == 64
    assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_hash_directory(tmp_path):
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    results = hash_directory(tmp_path)
    assert len(results) == 2
    assert all(r["sha256"] != "ERROR" for r in results)


def test_create_scan_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.services.evidence_service.settings",
                        type("S", (), {"evidence_dir": tmp_path})())
    svc = EvidenceService()
    svc._base = tmp_path / "scans"
    d = svc.create_scan_directory("test-001")
    assert d.is_dir()
    assert (d / "artifacts").is_dir()
    assert (d / "findings").is_dir()
    assert (d / "hashes").is_dir()


def test_save_and_read_metadata(tmp_path):
    svc = EvidenceService()
    svc._base = tmp_path / "scans"
    svc.create_scan_directory("test-002")
    svc.save_metadata("test-002", {"status": "running", "device_serial": "X"})
    meta_path = svc._base / "test-002" / "metadata.json"
    assert meta_path.is_file()
    meta = json.loads(meta_path.read_text())
    assert meta["status"] == "running"
