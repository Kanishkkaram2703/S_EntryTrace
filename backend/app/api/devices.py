"""S*EntryTrace — Device API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.services.adb_client import AdbClient
from backend.app.services.device_manager import DeviceManager, DeviceNotFoundError

router = APIRouter(prefix="/api/devices", tags=["devices"])

# Shared instances (stateless — safe to reuse)
_adb = AdbClient()
_dm = DeviceManager(adb_client=_adb)


@router.get("")
def list_devices():
    """List all ADB-visible devices with basic metadata."""
    devices = _dm.list_devices()
    return {
        "count": len(devices),
        "devices": [d.model_dump() for d in devices],
    }


@router.get("/{serial}")
def get_device(serial: str):
    """Return detailed metadata for a specific device."""
    try:
        info = _dm.get_device_info(serial)
        return info.model_dump()
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/status/adb")
def adb_status():
    """Return ADB executable status."""
    return _dm.get_adb_status()
