"""Tests for ADB client — uses mocks, no physical device required."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.app.services.adb_client import AdbClient, AdbError


@pytest.fixture
def adb():
    """AdbClient with a fake but 'existing' binary path."""
    with patch.object(Path, "is_file", return_value=True):
        return AdbClient(adb_path=Path("/fake/adb.exe"), timeout=5)


def test_is_available_true(adb):
    with patch.object(Path, "is_file", return_value=True):
        assert adb.is_available() is True


def test_is_available_false():
    client = AdbClient(adb_path=Path("/nonexistent/path/adb"))
    assert client.is_available() is False


@patch("subprocess.run")
def test_get_version(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Android Debug Bridge version 1.0.41\nVersion 37.0.1-12345\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        version = adb.get_version()
        assert version in ("1.0.41", "37.0.1")  # Either version pattern is valid


@patch("subprocess.run")
def test_list_devices_empty(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="List of devices attached\n\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        devices = adb.list_devices()
        assert devices == []


@patch("subprocess.run")
def test_list_devices_one_connected(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="List of devices attached\nABC123   device model:Pixel_6\n\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        devices = adb.list_devices()
        assert len(devices) == 1
        assert devices[0]["serial"] == "ABC123"
        assert devices[0]["state"] == "device"
        assert devices[0]["model"] == "Pixel_6"


@patch("subprocess.run")
def test_list_devices_unauthorized(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="List of devices attached\nXYZ789   unauthorized\n\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        devices = adb.list_devices()
        assert len(devices) == 1
        assert devices[0]["state"] == "unauthorized"


@patch("subprocess.run")
def test_list_devices_offline(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="List of devices attached\nDEF456   offline\n\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        devices = adb.list_devices()
        assert devices[0]["state"] == "offline"


@patch("subprocess.run")
def test_list_devices_multiple(mock_run, adb):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="List of devices attached\nAAA   device\nBBB   device\n\n",
        stderr="",
    )
    with patch.object(Path, "is_file", return_value=True):
        devices = adb.list_devices()
        assert len(devices) == 2


def test_disallowed_shell_command(adb):
    with patch.object(Path, "is_file", return_value=True):
        with pytest.raises(AdbError, match="not in allowlist"):
            adb.get_device_property("ABC", "rm -rf /")


@patch("subprocess.run")
def test_timeout_raises(mock_run, adb):
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="adb", timeout=5)
    with patch.object(Path, "is_file", return_value=True):
        with pytest.raises(AdbError, match="timed out"):
            adb.get_version()
