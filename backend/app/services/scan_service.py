"""S*EntryTrace — Scan orchestration service.

Implements the Rapid Triage workflow:
1. Validate device
2. Create evidence directory
3. Collect bugreport via ADB
4. Run MVT analysis on collected artifact
5. Parse findings
6. Generate hashes and manifest
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.models.device import DeviceState
from backend.app.models.scan import ScanStatus
from backend.app.services.adb_client import AdbClient, AdbError
from backend.app.services.device_manager import DeviceManager
from backend.app.services.evidence_service import EvidenceService
from backend.app.services.mvt_engine import MVTEngine
from backend.app.utils.subprocess_utils import run_safe

log = logging.getLogger("ste.scan")

# ── In-memory scan state (MVP; not production-grade) ──────────────────
_scans: dict[str, dict] = {}
_scan_lock = threading.Lock()


def _get_scan(scan_id: str) -> Optional[dict]:
    with _scan_lock:
        return _scans.get(scan_id)


def _set_scan(scan_id: str, data: dict) -> None:
    with _scan_lock:
        _scans[scan_id] = data


class ScanService:
    """Orchestrates forensic scans using MVT and ADB."""

    def __init__(self) -> None:
        self._adb = AdbClient()
        self._dm = DeviceManager(adb_client=self._adb)
        self._evidence = EvidenceService()
        self._engine = MVTEngine()

    # ── Public API ─────────────────────────────────────────────────────

    def list_scans(self) -> list[dict]:
        """List all scans (in-memory + on-disk)."""
        # Merge in-memory state with disk evidence
        disk_scans = {s["scan_id"]: s for s in self._evidence.list_scans()}
        with _scan_lock:
            for sid, data in _scans.items():
                if sid not in disk_scans:
                    disk_scans[sid] = {
                        "scan_id": sid,
                        "status": data.get("status", "unknown"),
                        "device_serial": data.get("device_serial", ""),
                    }
                else:
                    disk_scans[sid]["status"] = data.get("status", disk_scans[sid].get("status"))
        return list(disk_scans.values())

    def get_scan(self, scan_id: str) -> Optional[dict]:
        """Get full scan state."""
        return _get_scan(scan_id)

    def get_scan_logs(self, scan_id: str) -> str:
        """Get scan stdout log content."""
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            return ""
        stdout_path = scan_dir / "stdout.log"
        if stdout_path.is_file():
            return stdout_path.read_text(encoding="utf-8", errors="replace")
        return _get_scan(scan_id).get("log", "") if _get_scan(scan_id) else ""

    def get_manifest(self, scan_id: str) -> Optional[dict]:
        """Get the evidence manifest for a scan."""
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            return None
        manifest_path = scan_dir / "manifest.json"
        if manifest_path.is_file():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return None

    def start_rapid_triage(self, device_serial: str) -> dict:
        """Start a Rapid Triage scan on the specified device.

        This is the primary scan workflow for the MVP.  It:
        1. Validates the device is connected and authorized
        2. Creates a scan evidence directory
        3. Runs the scan in a background thread
        4. Returns immediately with the scan ID
        """
        # Validate device
        try:
            device_info = self._dm.get_device_info(device_serial)
        except Exception as exc:
            return {"error": str(exc), "status": ScanStatus.FAILED.value}

        if device_info.state != DeviceState.CONNECTED:
            return {
                "error": f"Device '{device_serial}' is not in connected state "
                         f"(current: {device_info.state.value}). "
                         "Ensure USB debugging is authorized.",
                "status": ScanStatus.FAILED.value,
            }

        # Generate scan ID and create evidence directory
        scan_id = f"triage-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        scan_dir = self._evidence.create_scan_directory(scan_id)

        scan_state = {
            "scan_id": scan_id,
            "device_serial": device_serial,
            "device": device_info.model_dump(),
            "scan_profile": "rapid_triage",
            "status": ScanStatus.RUNNING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "mvt_version": self._engine.get_version(),
            "adb_version": None,
            "current_operation": "Initializing scan...",
            "log": "",
            "warnings": [],
            "errors": [],
            "findings_count": 0,
        }

        try:
            scan_state["adb_version"] = self._adb.get_version()
        except AdbError:
            pass

        # Save initial metadata
        self._evidence.save_metadata(scan_id, scan_state)
        _set_scan(scan_id, scan_state)

        # Run scan in background thread
        thread = threading.Thread(
            target=self._execute_rapid_triage,
            args=(scan_id, device_serial, scan_dir),
            daemon=True,
        )
        thread.start()

        return {"scan_id": scan_id, "status": ScanStatus.RUNNING.value}

    def cancel_scan(self, scan_id: str) -> dict:
        """Attempt to cancel a running scan."""
        scan = _get_scan(scan_id)
        if not scan:
            return {"error": "Scan not found"}
        if scan.get("status") != ScanStatus.RUNNING.value:
            return {"error": f"Scan is not running (status: {scan.get('status')})"}

        # Set cancellation flag — the background thread checks this
        scan["_cancel_requested"] = True
        _set_scan(scan_id, scan)
        return {"message": "Cancellation requested", "scan_id": scan_id}

    # ── Internal scan execution ────────────────────────────────────────

    def _execute_rapid_triage(
        self, scan_id: str, serial: str, scan_dir: Path
    ) -> None:
        """Execute the Rapid Triage scan in a background thread.

        Steps:
        1. Collect bugreport via ADB
        2. Analyze with MVT check-bugreport
        3. Parse output for findings
        4. Generate evidence hashes and manifest
        """
        scan = _get_scan(scan_id)
        if not scan:
            return
        all_log = ""

        try:
            # Step 1: Collect bugreport
            self._update_scan(scan_id, "Collecting bugreport from device...")
            bugreport_path = scan_dir / "artifacts"

            adb_path = str(self._adb.adb_path)
            result = run_safe(
                [adb_path, "-s", serial, "bugreport", str(bugreport_path)],
                timeout=settings.subprocess_timeout * 10,  # bugreport can be slow
            )

            all_log += f"=== ADB BUGREPORT ===\n{result.stdout}\n{result.stderr}\n"
            self._evidence.save_stdout(scan_id, all_log)

            if self._is_cancelled(scan_id):
                self._finalize_scan(scan_id, ScanStatus.CANCELLED, all_log)
                return

            if not result.ok:
                self._update_scan(scan_id, "Bugreport collection failed")
                scan = _get_scan(scan_id)
                scan["errors"].append(f"ADB bugreport failed: {result.stderr[:200]}")
                scan["warnings"].append(
                    "Bugreport collection failed. This may be due to device "
                    "restrictions or insufficient permissions."
                )
                _set_scan(scan_id, scan)
                # Try to continue with whatever artifacts exist

            # Find the bugreport file
            bugreport_file = self._find_bugreport(bugreport_path)

            if bugreport_file:
                # Step 2: Run MVT analysis
                self._update_scan(scan_id, "Running MVT bugreport analysis...")
                mvt_output = scan_dir / "findings"

                mvt_cmd = [
                    str(settings.project_root / ".venv" / "Scripts" / "mvt-android.exe"),
                    "check-bugreport",
                    "--output", str(mvt_output),
                    str(bugreport_file),
                ]

                mvt_result = run_safe(mvt_cmd, timeout=settings.subprocess_timeout * 5)
                all_log += f"\n=== MVT ANALYSIS ===\n{mvt_result.stdout}\n{mvt_result.stderr}\n"
                self._evidence.save_stdout(scan_id, all_log)

                if mvt_result.stderr:
                    self._evidence.save_stderr(scan_id, mvt_result.stderr)
            else:
                all_log += "\n=== NO BUGREPORT FOUND ===\nNo bugreport ZIP found in artifacts.\n"
                scan = _get_scan(scan_id)
                scan["warnings"].append("No bugreport file found after collection.")
                _set_scan(scan_id, scan)

            if self._is_cancelled(scan_id):
                self._finalize_scan(scan_id, ScanStatus.CANCELLED, all_log)
                return

            # Step 3: Collect device properties as supplementary evidence
            self._update_scan(scan_id, "Collecting device properties...")
            props = self._collect_device_props(serial)
            props_path = scan_dir / "artifacts" / "device_properties.json"
            props_path.write_text(json.dumps(props, indent=2), encoding="utf-8")

            # Step 4: Generate hashes and manifest
            self._update_scan(scan_id, "Computing evidence hashes...")
            self._evidence.save_command_log(scan_id, all_log)
            self._evidence.save_stdout(scan_id, all_log)

            self._finalize_scan(scan_id, ScanStatus.COMPLETED, all_log)

        except Exception as exc:
            log.exception("Scan %s failed: %s", scan_id, exc)
            all_log += f"\n=== ERROR ===\n{exc}\n"
            scan = _get_scan(scan_id)
            if scan:
                scan["errors"].append(str(exc))
                _set_scan(scan_id, scan)
            self._finalize_scan(scan_id, ScanStatus.FAILED, all_log)

    def _finalize_scan(self, scan_id: str, status: ScanStatus, log_content: str) -> None:
        """Finalize scan: update status, compute hashes, generate manifest."""
        scan = _get_scan(scan_id)
        if not scan:
            return

        scan["status"] = status.value
        scan["completed_at"] = datetime.now(timezone.utc).isoformat()
        scan["current_operation"] = f"Scan {status.value}"
        _set_scan(scan_id, scan)

        # Save final metadata
        self._evidence.save_metadata(scan_id, scan)

        # Compute hashes and generate manifest
        try:
            self._evidence.generate_manifest(scan_id, scan)
        except Exception as exc:
            log.error("Failed to generate manifest for %s: %s", scan_id, exc)

    def _update_scan(self, scan_id: str, operation: str) -> None:
        """Update the current operation for a running scan."""
        scan = _get_scan(scan_id)
        if scan:
            scan["current_operation"] = operation
            scan["log"] = scan.get("log", "") + f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {operation}\n"
            _set_scan(scan_id, scan)
        log.info("[%s] %s", scan_id, operation)

    def _is_cancelled(self, scan_id: str) -> bool:
        scan = _get_scan(scan_id)
        return bool(scan and scan.get("_cancel_requested"))

    def _find_bugreport(self, artifacts_dir: Path) -> Optional[Path]:
        """Find the bugreport ZIP file in artifacts."""
        if not artifacts_dir.is_dir():
            return None
        for f in artifacts_dir.iterdir():
            if f.suffix == ".zip" and "bugreport" in f.name.lower():
                return f
        # Also check if it's a directory
        for f in artifacts_dir.iterdir():
            if f.is_dir() and "bugreport" in f.name.lower():
                return f
        return None

    def _collect_device_props(self, serial: str) -> dict:
        """Collect device properties for evidence record."""
        props = {}
        prop_cmds = {
            "model": "getprop ro.product.model",
            "manufacturer": "getprop ro.product.manufacturer",
            "android_version": "getprop ro.build.version.release",
            "sdk_level": "getprop ro.build.version.sdk",
            "security_patch": "getprop ro.build.version.security_patch",
            "build_fingerprint": "getprop ro.build.fingerprint",
            "build_description": "getprop ro.build.description",
        }
        for key, cmd in prop_cmds.items():
            try:
                val = self._adb.get_device_property(serial, cmd)
                props[key] = val
            except AdbError:
                props[key] = None
        return props
