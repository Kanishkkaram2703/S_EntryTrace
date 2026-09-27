"""S*EntryTrace — Device Manager.

High-level service that orchestrates ADB device discovery and metadata
collection.  Delegates all ADB I/O to :class:`AdbClient`.

KEY DESIGN: Never overwrites a valid cached value with None on a
temporary ADB failure. Maintains a 'last verified' metadata cache.
"""

import logging
from datetime import datetime
from typing import Optional

from backend.app.models.device import DeviceInfo, DeviceState, MetadataState
from backend.app.services.adb_client import AdbClient, AdbError

log = logging.getLogger("ste.device_manager")

# Properties that can be read from the device
_PROPERTY_MAP = {
    "model": "getprop ro.product.model",
    "manufacturer": "getprop ro.product.manufacturer",
    "android_version": "getprop ro.build.version.release",
    "sdk_level": "getprop ro.build.version.sdk",
    "security_patch": "getprop ro.build.version.security_patch",
    "build_fingerprint": "getprop ro.build.fingerprint",
}


# Module-level singleton metadata cache shared across all DeviceManager instances.
# This ensures that device metadata cached by one API route (e.g. /api/devices)
# is available to another (e.g. scan_service) without re-querying ADB.
_shared_metadata_cache: dict[str, DeviceInfo] = {}


class DeviceManager:
    """Manage Android device discovery and metadata via ADB.

    Parameters
    ----------
    adb_client : AdbClient, optional
        Inject a custom client (useful for testing).
    """

    def __init__(self, adb_client: Optional[AdbClient] = None) -> None:
        self._adb = adb_client or AdbClient()
        # Use module-level shared cache so all instances see same metadata
        self._metadata_cache = _shared_metadata_cache

    # ── Public API ─────────────────────────────────────────────────────

    def get_adb_status(self) -> dict:
        """Return ADB availability and version information."""
        available = self._adb.is_available()
        version: Optional[str] = None
        error: Optional[str] = None

        if available:
            try:
                version = self._adb.get_version()
            except AdbError as exc:
                error = str(exc)

        return {
            "available": available,
            "version": version,
            "adb_path": str(self._adb.adb_path) if self._adb.adb_path else None,
            "error": error,
        }

    def list_devices(self) -> list[DeviceInfo]:
        """Discover all ADB-visible devices and return their metadata.

        Merges freshly discovered state with cached metadata so that
        previously verified properties are preserved even when ADB
        temporarily cannot read them.
        """
        if not self._adb.is_available():
            log.warning("ADB not available — returning empty device list")
            return []

        try:
            self._adb.ensure_server()
            raw_devices = self._adb.list_devices()
        except AdbError as exc:
            log.error("Failed to list devices: %s", exc)
            return []

        devices: list[DeviceInfo] = []
        for raw in raw_devices:
            serial = raw["serial"]
            adb_state = raw.get("state", "")
            state = self._map_state(adb_state)

            # Start from cache if available
            cached = self._metadata_cache.get(serial)
            if cached:
                info = cached.model_copy()
                info.state = state
            else:
                info = DeviceInfo(serial=serial, state=state, model=raw.get("model"))

            # Try to enrich with full properties if connected
            if state == DeviceState.CONNECTED:
                self._enrich_metadata(info)

            # Set ADB version
            try:
                info.adb_version = self._adb.get_version()
            except AdbError:
                pass

            # Update cache
            self._metadata_cache[serial] = info
            devices.append(info)

        return devices

    def get_device_info(self, serial: str) -> "DeviceInfo":
        """Collect detailed metadata for a specific device.

        Uses cached values as a baseline and only updates fields that
        can be successfully read. Never overwrites a valid value with
        None due to a temporary failure.

        Raises ``DeviceNotFoundError`` when the serial is not visible.
        """
        if not self._adb.is_available():
            raise DeviceNotFoundError(
                "ADB is not available. Cannot query device info."
            )

        # Verify device is visible
        raw_devices = self._adb.list_devices()
        match = None
        for raw in raw_devices:
            if raw["serial"] == serial:
                match = raw
                break

        if match is None:
            # Device not visible — return stale cache if available
            cached = self._metadata_cache.get(serial)
            if cached:
                stale = cached.model_copy()
                stale.state = DeviceState.UNAVAILABLE
                stale.metadata_state = MetadataState.STALE
                return stale
            raise DeviceNotFoundError(
                f"Device '{serial}' not found in ADB device list."
            )

        adb_state = match.get("state", "")
        state = self._map_state(adb_state)

        # Start from cache if available
        cached = self._metadata_cache.get(serial)
        if cached:
            info = cached.model_copy()
            info.state = state
        else:
            info = DeviceInfo(serial=serial, state=state)

        # Only read properties from fully connected devices
        if state == DeviceState.CONNECTED:
            self._enrich_metadata(info)

        try:
            info.adb_version = self._adb.get_version()
        except AdbError:
            pass

        # Update cache
        self._metadata_cache[serial] = info
        return info

    def get_connected_device(self) -> "DeviceInfo":
        """Return the single connected device, or raise an error.

        Raises ``DeviceNotFoundError`` if zero or multiple devices.
        """
        devices = self.list_devices()
        connected = [d for d in devices if d.state == DeviceState.CONNECTED]

        if len(connected) == 0:
            # Provide user-friendly guidance based on what IS visible
            unauthorized = [d for d in devices if d.state == DeviceState.UNAUTHORIZED]
            offline = [d for d in devices if d.state == DeviceState.OFFLINE]

            if unauthorized:
                raise DeviceNotFoundError(
                    f"Device '{unauthorized[0].serial}' is unauthorized. "
                    "Please check the device screen and tap 'Allow USB debugging'."
                )
            if offline:
                raise DeviceNotFoundError(
                    f"Device '{offline[0].serial}' is offline. "
                    "Try reconnecting the USB cable or restarting ADB."
                )
            raise DeviceNotFoundError(
                "No Android device connected. "
                "Connect a device via USB and enable USB debugging."
            )

        if len(connected) > 1:
            serials = [d.serial for d in connected]
            raise DeviceNotFoundError(
                f"Multiple devices connected: {serials}. "
                "Specify a device serial explicitly."
            )

        return connected[0]

    def refresh_devices(self) -> list[DeviceInfo]:
        """Force-refresh the device list (cache is preserved for merge)."""
        return self.list_devices()

    # ── Internal helpers ───────────────────────────────────────────────

    def _enrich_metadata(self, info: DeviceInfo) -> None:
        """Read device properties and merge into info, preserving cached values.

        Only overwrites a field if the new value is non-null.
        """
        success_count = 0
        total = len(_PROPERTY_MAP)

        for field_name, prop_cmd in _PROPERTY_MAP.items():
            new_value = self._prop(info.serial, prop_cmd)
            if new_value is not None:
                setattr(info, field_name, new_value)
                success_count += 1
            # If new_value is None, we keep whatever was already set (cached)

        # Check root status
        root_val = self._check_root(info.serial)
        if root_val is not None:
            info.is_rooted = root_val

        # Set metadata freshness
        if success_count == total:
            info.metadata_state = MetadataState.VERIFIED
            info.last_verified_at = datetime.utcnow()
        elif success_count > 0:
            info.metadata_state = MetadataState.STALE
            # partial success — keep last_verified_at from before
        else:
            info.metadata_state = MetadataState.ERROR

    @staticmethod
    def _map_state(adb_state: str) -> DeviceState:
        """Map raw ADB state strings to our ``DeviceState`` enum."""
        mapping = {
            "device": DeviceState.CONNECTED,
            "unauthorized": DeviceState.UNAUTHORIZED,
            "offline": DeviceState.OFFLINE,
            "no permissions": DeviceState.ERROR,
        }
        return mapping.get(adb_state, DeviceState.UNAVAILABLE)

    def _prop(self, serial: str, cmd: str) -> Optional[str]:
        """Read a single device property, swallowing errors."""
        try:
            return self._adb.get_device_property(serial, cmd)
        except AdbError:
            return None

    def _check_root(self, serial: str) -> Optional[bool]:
        """Safely check if ``su`` exists on the device.

        Returns ``True`` if ``which su`` prints a path,
        ``False`` if it returns empty, ``None`` on error.
        """
        result = self._prop(serial, "which su")
        if result is None:
            return None
        return bool(result.strip())


class DeviceNotFoundError(Exception):
    """Raised when a requested device is not available."""
