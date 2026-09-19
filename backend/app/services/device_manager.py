"""S*EntryTrace — Device Manager.

High-level service that orchestrates ADB device discovery and metadata
collection.  Delegates all ADB I/O to :class:`AdbClient`.
"""

import logging
from typing import Optional

from backend.app.models.device import DeviceInfo, DeviceState
from backend.app.services.adb_client import AdbClient, AdbError

log = logging.getLogger("ste.device_manager")


class DeviceManager:
    """Manage Android device discovery and metadata via ADB.

    Parameters
    ----------
    adb_client : AdbClient, optional
        Inject a custom client (useful for testing).
    """

    def __init__(self, adb_client: Optional[AdbClient] = None) -> None:
        self._adb = adb_client or AdbClient()
        self._devices_cache: list[DeviceInfo] = []

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
        """Discover all ADB-visible devices and return their basic info.

        Returns an empty list when ADB is unavailable or no devices are
        attached — never raises unhandled exceptions.
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

            info = DeviceInfo(
                serial=serial,
                state=state,
                model=raw.get("model"),
            )

            # Attempt to read ADB version once
            try:
                info.adb_version = self._adb.get_version()
            except AdbError:
                pass

            devices.append(info)

        self._devices_cache = devices
        return devices

    def get_device_info(self, serial: str) -> DeviceInfo:
        """Collect detailed metadata for a specific device.

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
            raise DeviceNotFoundError(
                f"Device '{serial}' not found in ADB device list."
            )

        adb_state = match.get("state", "")
        state = self._map_state(adb_state)

        info = DeviceInfo(serial=serial, state=state)

        # Only read properties from fully connected devices
        if state == DeviceState.CONNECTED:
            info.model = self._prop(serial, "getprop ro.product.model")
            info.manufacturer = self._prop(serial, "getprop ro.product.manufacturer")
            info.android_version = self._prop(
                serial, "getprop ro.build.version.release"
            )
            info.sdk_level = self._prop(serial, "getprop ro.build.version.sdk")
            info.security_patch = self._prop(
                serial, "getprop ro.build.version.security_patch"
            )
            info.build_fingerprint = self._prop(
                serial, "getprop ro.build.fingerprint"
            )
            info.is_rooted = self._check_root(serial)

        try:
            info.adb_version = self._adb.get_version()
        except AdbError:
            pass

        return info

    def get_connected_device(self) -> DeviceInfo:
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
        """Force-refresh the device list (clears cache)."""
        self._devices_cache.clear()
        return self.list_devices()

    # ── Internal helpers ───────────────────────────────────────────────

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
