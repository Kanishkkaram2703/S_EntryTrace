"""Tests for DeviceManager — uses mocks, no physical device required."""

import pytest
from unittest.mock import MagicMock, patch

from backend.app.models.device import DeviceState
from backend.app.services.device_manager import DeviceManager, DeviceNotFoundError


def _make_dm(devices_raw=None, adb_available=True):
    """Create a DeviceManager with a mocked AdbClient."""
    mock_adb = MagicMock()
    mock_adb.is_available.return_value = adb_available
    mock_adb.ensure_server.return_value = None
    mock_adb.get_version.return_value = "37.0.1"
    mock_adb.list_devices.return_value = devices_raw or []
    mock_adb.get_device_property.return_value = None
    return DeviceManager(adb_client=mock_adb)


def test_no_devices():
    dm = _make_dm([])
    devices = dm.list_devices()
    assert devices == []


def test_one_connected():
    dm = _make_dm([{"serial": "A1", "state": "device"}])
    devices = dm.list_devices()
    assert len(devices) == 1
    assert devices[0].serial == "A1"
    assert devices[0].state == DeviceState.CONNECTED


def test_unauthorized():
    dm = _make_dm([{"serial": "B2", "state": "unauthorized"}])
    devices = dm.list_devices()
    assert devices[0].state == DeviceState.UNAUTHORIZED


def test_offline():
    dm = _make_dm([{"serial": "C3", "state": "offline"}])
    devices = dm.list_devices()
    assert devices[0].state == DeviceState.OFFLINE


def test_get_connected_device_single():
    dm = _make_dm([{"serial": "D4", "state": "device"}])
    device = dm.get_connected_device()
    assert device.serial == "D4"


def test_get_connected_device_none():
    dm = _make_dm([])
    with pytest.raises(DeviceNotFoundError, match="No Android device"):
        dm.get_connected_device()


def test_get_connected_device_unauthorized():
    dm = _make_dm([{"serial": "E5", "state": "unauthorized"}])
    with pytest.raises(DeviceNotFoundError, match="unauthorized"):
        dm.get_connected_device()


def test_get_connected_device_multiple():
    dm = _make_dm([
        {"serial": "F6", "state": "device"},
        {"serial": "G7", "state": "device"},
    ])
    with pytest.raises(DeviceNotFoundError, match="Multiple"):
        dm.get_connected_device()


def test_adb_not_available():
    dm = _make_dm(adb_available=False)
    devices = dm.list_devices()
    assert devices == []


def test_adb_status():
    dm = _make_dm(adb_available=True)
    status = dm.get_adb_status()
    assert status["available"] is True
    assert status["version"] == "37.0.1"
