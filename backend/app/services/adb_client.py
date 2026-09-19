"""S*EntryTrace — ADB Client.

A safe, read-only wrapper around the ``adb`` command-line tool.
All interactions use explicit argument lists (never ``shell=True``),
enforce timeouts, and are limited to an allowlist of read-only commands.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from backend.app.config import settings

log = logging.getLogger("ste.adb")

# ── Allowlisted safe ADB sub-commands ──────────────────────────────────
# Only these are permitted.  Nothing outside this set can be executed.
_ALLOWED_ADB_COMMANDS: set[str] = {
    "version",
    "devices",
    "start-server",
    "get-state",
    "get-serialno",
    "shell",          # gated separately by _ALLOWED_SHELL_COMMANDS
}

# Shell commands that are safe to run on-device (read-only property reads).
_ALLOWED_SHELL_COMMANDS: set[str] = {
    "getprop ro.build.display.id",
    "getprop ro.product.model",
    "getprop ro.product.manufacturer",
    "getprop ro.build.version.release",
    "getprop ro.build.version.sdk",
    "getprop ro.build.version.security_patch",
    "getprop ro.build.fingerprint",
    "getprop ro.build.description",
    "which su",
}


class AdbError(Exception):
    """Raised when an ADB operation fails in a controlled way."""


class AdbClient:
    """Read-only interface to Android Debug Bridge.

    Parameters
    ----------
    adb_path : Path, optional
        Explicit path to the ``adb`` binary.  Falls back to
        ``settings.adb_path``.
    timeout : int, optional
        Maximum seconds for any subprocess call.
    """

    def __init__(
        self,
        adb_path: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self._adb = adb_path or settings.adb_path
        self._timeout = timeout or settings.subprocess_timeout

    # ── Public helpers ─────────────────────────────────────────────────

    @property
    def adb_path(self) -> Optional[Path]:
        return self._adb

    def is_available(self) -> bool:
        """Return ``True`` if the ADB binary exists on disk."""
        return self._adb is not None and self._adb.is_file()

    def get_version(self) -> str:
        """Return the ADB version string (e.g. ``'37.0.1'``)."""
        output = self._run(["version"])
        match = re.search(r"(\d+\.\d+\.\d+)", output)
        if match:
            return match.group(1)
        raise AdbError(f"Could not parse ADB version from: {output[:120]}")

    def ensure_server(self) -> None:
        """Start the ADB daemon if it is not already running."""
        self._run(["start-server"])

    def list_devices_raw(self) -> str:
        """Run ``adb devices -l`` and return the raw output."""
        return self._run(["devices", "-l"])

    def list_devices(self) -> list[dict[str, str]]:
        """Parse ``adb devices -l`` into a list of device dicts.

        Each dict contains at minimum ``serial`` and ``state``.
        Additional keys (``model``, ``device``, ``transport_id``, etc.)
        are included when ADB reports them.
        """
        raw = self.list_devices_raw()
        devices: list[dict[str, str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("List of") or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]  # "device", "unauthorized", "offline", …
            info: dict[str, str] = {"serial": serial, "state": state}
            # Parse key:value tokens like model:Pixel_6
            for token in parts[2:]:
                if ":" in token:
                    key, _, value = token.partition(":")
                    info[key] = value
            devices.append(info)
        return devices

    def get_device_property(self, serial: str, prop_cmd: str) -> Optional[str]:
        """Run a safe ``adb -s <serial> shell <prop_cmd>`` command.

        The command must be in the allowlist.  Returns the trimmed
        stdout or ``None`` on failure.
        """
        if prop_cmd not in _ALLOWED_SHELL_COMMANDS:
            raise AdbError(f"Shell command not in allowlist: {prop_cmd!r}")
        try:
            output = self._run(["-s", serial, "shell"] + prop_cmd.split())
            value = output.strip()
            return value if value else None
        except AdbError:
            return None

    def get_device_state(self, serial: str) -> str:
        """Return the state string for a specific device serial."""
        try:
            return self._run(["-s", serial, "get-state"]).strip()
        except AdbError:
            return "error"

    # ── Internal ───────────────────────────────────────────────────────

    def _run(self, args: list[str]) -> str:
        """Execute an ADB command safely.

        Raises ``AdbError`` on missing binary, timeout, or non-zero exit.
        """
        if not self.is_available():
            raise AdbError(
                "ADB executable not found. "
                "Ensure platform-tools is downloaded or ADB is on PATH."
            )

        # Validate the sub-command against the allowlist
        subcmd = args[0] if args else ""
        # For "-s serial <subcmd>" patterns, extract the real sub-command
        effective_cmd = subcmd
        if subcmd == "-s" and len(args) >= 3:
            effective_cmd = args[2]

        if effective_cmd not in _ALLOWED_ADB_COMMANDS:
            raise AdbError(f"ADB sub-command not allowed: {effective_cmd!r}")

        cmd = [str(self._adb)] + args
        log.debug("ADB exec: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise AdbError(
                f"ADB command timed out after {self._timeout}s: {' '.join(args)}"
            )
        except FileNotFoundError:
            raise AdbError(f"ADB binary not found at: {self._adb}")
        except OSError as exc:
            raise AdbError(f"ADB execution error: {exc}")

        if result.returncode != 0:
            stderr = result.stderr.strip()[:200] if result.stderr else "unknown error"
            raise AdbError(f"ADB command failed (rc={result.returncode}): {stderr}")

        return result.stdout
