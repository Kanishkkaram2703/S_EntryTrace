"""Tests for scan service — validates request handling."""

import pytest
from unittest.mock import MagicMock, patch

from backend.app.services.scan_service import ScanService


def test_scan_service_no_device():
    """Starting a scan with a non-existent device returns an error."""
    svc = ScanService()
    # Mock the device manager to raise
    with patch.object(svc._dm, "get_device_info", side_effect=Exception("Device 'FAKE' not found")):
        result = svc.start_rapid_triage("FAKE")
        assert result["status"] == "failed"
        assert "error" in result
