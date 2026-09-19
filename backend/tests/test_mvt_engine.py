"""Tests for MVT engine wrapper."""

import pytest
from backend.app.services.mvt_engine import MVTEngine


def test_mvt_available():
    engine = MVTEngine()
    assert engine.is_available() is True


def test_mvt_version():
    engine = MVTEngine()
    version = engine.get_version()
    assert version is not None
    assert "." in version  # e.g. "2.0.0"


def test_engine_status():
    engine = MVTEngine()
    status = engine.get_engine_status()
    assert status.available is True
    assert status.module_count > 0
    assert status.modules_loaded is True


def test_module_categories():
    engine = MVTEngine()
    cats = engine.get_module_categories()
    assert "bugreport" in cats
    assert "androidqf" in cats
    assert len(cats["bugreport"]) > 0


def test_validate_module():
    engine = MVTEngine()
    assert engine.validate_module("DumpsysPackages") is True
    assert engine.validate_module("NonExistentModule") is False


def test_prepare_scan_invalid_type():
    from backend.app.models.scan import ScanRequest, ScanStatus
    engine = MVTEngine()
    req = ScanRequest(device_serial="ABC", scan_type="invalid_type")
    result = engine.prepare_scan_request(req)
    assert result.status == ScanStatus.FAILED
