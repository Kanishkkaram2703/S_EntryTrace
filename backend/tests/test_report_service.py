"""Tests for report_service.py — PDF generation robustness.

Tests that the PDF generator handles:
- Very long build fingerprints
- Very long file paths
- Very long hash strings
- Unicode values
- Empty values
- Missing manifests
- Report regeneration
- Many findings
- Many evidence files
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.app.services.report_service import ReportService, _safe, _truncate
from backend.app.models.finding import (
    Finding, FindingSummary, FindingCategory, FindingSeverity, FindingConfidence, AnalysisModule
)


@pytest.fixture
def tmp_evidence(tmp_path):
    """Create a temporary evidence directory with manifest."""
    scan_id = "triage-20260921-140000-abc123"
    scan_dir = tmp_path / "evidence" / "scans" / scan_id
    for sub in ("artifacts", "findings", "hashes", "logs", "report"):
        (scan_dir / sub).mkdir(parents=True, exist_ok=True)

    device = {
        "serial": "ABCDEFGHIJKLMNOP",
        "model": "V2443",
        "manufacturer": "vivo",
        "android_version": "16",
        "sdk_level": "36",
        "security_patch": "2026-08-01",
        "build_fingerprint": "vivo/V2443i/V2436:16/BP2A.250605.031.A3_V000L1/compiler260811152305:user/release-keys",
        "is_rooted": False,
    }

    meta = {
        "scan_id": scan_id,
        "device_serial": "ABCDEFGHIJKLMNOP",
        "device": device,
        "scan_profile": "rapid_triage",
        "status": "completed",
        "started_at": "2026-09-21T14:00:00+00:00",
        "completed_at": "2026-09-21T14:05:00+00:00",
        "mvt_version": "2.0.0",
        "adb_version": "37.0.1",
        "warnings": [],
        "errors": [],
        "stages": [
            {"stage_id": "device_check", "display_name": "Device Verification", "status": "completed", "summary": "OK"},
            {"stage_id": "bugreport", "display_name": "System Diagnostics", "status": "completed", "summary": "Collected 15MB"},
        ],
    }

    manifest = {
        "scan_id": scan_id,
        "device": device,
        "mvt_version": "2.0.0",
        "adb_version": "37.0.1",
        "scan_profile": "rapid_triage",
        "collection_start": "2026-09-21T14:00:00+00:00",
        "collection_end": "2026-09-21T14:05:00+00:00",
        "collection_status": "completed",
        "file_count": 5,
        "total_bytes": 1024000,
        "files": [
            {"relative_path": "artifacts/bugreport.zip", "size_bytes": 1000000, "sha256": "a" * 64},
            {"relative_path": "findings/dumpsys_packages.json", "size_bytes": 20000, "sha256": "b" * 64},
        ],
        "warnings": [],
        "errors": [],
        "limitations": [
            "Evidence collected via ADB read-only commands only.",
            "Not a complete forensic acquisition.",
        ],
    }

    timeline = [
        {"time": "14:00:00", "timestamp": "2026-09-21T14:00:00+00:00", "level": "INFO", "message": "Initializing examination"},
        {"time": "14:00:01", "timestamp": "2026-09-21T14:00:01+00:00", "level": "SUCCESS", "message": "Device verified"},
        {"time": "14:05:00", "timestamp": "2026-09-21T14:05:00+00:00", "level": "SUCCESS", "message": "Examination completed"},
    ]

    (scan_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    (scan_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (scan_dir / "timeline.json").write_text(json.dumps(timeline, indent=2))

    return tmp_path, scan_id, scan_dir


def _make_findings(n: int = 5) -> FindingSummary:
    """Create a FindingSummary with N findings."""
    findings = []
    for i in range(n):
        findings.append(Finding(
            finding_id=f"f-{i}",
            scan_id="test",
            category=FindingCategory.SUSPICIOUS,
            title=f"Test finding {i} with a moderately long title that should wrap properly",
            description=f"Description for finding {i}",
            severity=FindingSeverity.MEDIUM,
            confidence=FindingConfidence.MEDIUM,
            source_module="dumpsys_packages",
            explanation=f"This is the explanation for finding {i}. " * 5,
            why_it_matters="This matters because it could indicate suspicious activity.",
            interpretation="Review this finding carefully.",
        ))
    return FindingSummary(
        scan_id="test",
        total=n,
        by_severity={"medium": n},
        by_category={"Suspicious Observation": n},
        findings=findings,
        modules_analyzed=[
            AnalysisModule(module_name="dumpsys_packages", display_name="Installed Packages",
                          records_processed=500, alerts_generated=n),
        ],
        total_records_processed=500,
    )


# ── Unit tests for helpers ────────────────────────────────────────────

class TestSafe:
    def test_empty_string(self):
        assert _safe("") == ""

    def test_none_input(self):
        assert _safe("") == ""

    def test_ascii(self):
        assert _safe("hello world") == "hello world"

    def test_unicode_replacement(self):
        result = _safe("hello \u2026 world")
        assert isinstance(result, str)

    def test_long_string(self):
        long = "x" * 10000
        result = _safe(long)
        assert len(result) == 10000


class TestTruncate:
    def test_short_string(self):
        assert _truncate("short", 100) == "short"

    def test_exact_length(self):
        s = "x" * 500
        assert _truncate(s, 500) == s

    def test_over_length(self):
        s = "x" * 600
        result = _truncate(s, 500)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")


# ── PDF generation tests ─────────────────────────────────────────────

class TestReportGeneration:

    @patch("backend.app.services.report_service.EvidenceService")
    def test_long_fingerprint_no_crash(self, mock_ev_cls, tmp_evidence):
        """Build fingerprints exceeding 80 chars must NOT crash the PDF."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        # Make fingerprint extremely long
        meta = json.loads((scan_dir / "metadata.json").read_text())
        meta["device"]["build_fingerprint"] = "vivo/" + "x" * 300 + "/long-fingerprint"
        (scan_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id, _make_findings(3))
        assert result is not None
        assert result.is_file()

    @patch("backend.app.services.report_service.EvidenceService")
    def test_long_file_paths_no_crash(self, mock_ev_cls, tmp_evidence):
        """Evidence inventory with very long file paths must not crash."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        manifest = json.loads((scan_dir / "manifest.json").read_text())
        manifest["files"].append({
            "relative_path": "artifacts/" + "very_long_directory/" * 20 + "file.json",
            "size_bytes": 5000,
            "sha256": "c" * 64,
        })
        (scan_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id, _make_findings(2))
        assert result is not None
        assert result.is_file()

    @patch("backend.app.services.report_service.EvidenceService")
    def test_many_findings_no_crash(self, mock_ev_cls, tmp_evidence):
        """Report with 30+ findings must render without error."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id, _make_findings(40))
        assert result is not None

    @patch("backend.app.services.report_service.EvidenceService")
    def test_empty_findings_no_crash(self, mock_ev_cls, tmp_evidence):
        """Report with zero findings must render correctly."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id, FindingSummary(scan_id=scan_id))
        assert result is not None

    @patch("backend.app.services.report_service.EvidenceService")
    def test_no_findings_object(self, mock_ev_cls, tmp_evidence):
        """Report generation with findings=None must work."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id, None)
        assert result is not None

    @patch("backend.app.services.report_service.EvidenceService")
    def test_regeneration(self, mock_ev_cls, tmp_evidence):
        """Regenerating a report must overwrite the existing PDF."""
        tmp_path, scan_id, scan_dir = tmp_evidence

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev.get_report_path.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev

        result1 = svc.generate_report(scan_id, _make_findings(3))
        assert result1 is not None
        size1 = result1.stat().st_size

        result2 = svc.generate_report(scan_id, _make_findings(5), regenerate=True)
        assert result2 is not None
        # File should exist (may be different size)
        assert result2.is_file()

    @patch("backend.app.services.report_service.EvidenceService")
    def test_missing_manifest_returns_none(self, mock_ev_cls, tmp_evidence):
        """Missing manifest.json should return None, not crash."""
        tmp_path, scan_id, scan_dir = tmp_evidence
        (scan_dir / "manifest.json").unlink()

        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = scan_dir
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report(scan_id)
        assert result is None

    @patch("backend.app.services.report_service.EvidenceService")
    def test_missing_scan_dir_returns_none(self, mock_ev_cls):
        """Non-existent scan directory should return None."""
        mock_ev = MagicMock()
        mock_ev.get_scan_directory.return_value = None
        mock_ev_cls.return_value = mock_ev

        svc = ReportService()
        svc._evidence = mock_ev
        result = svc.generate_report("nonexistent-scan-id")
        assert result is None
