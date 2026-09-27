"""S*EntryTrace — Scan orchestration service.

Implements the Rapid Triage workflow with modular stages:
1. Device verification
2. Device metadata collection
3. Bugreport collection via ADB
4. MVT bugreport analysis
5. Device properties collection
6. Evidence hashing and manifest
7. IOC analysis
8. Findings generation
9. Report generation
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
from backend.app.models.scan import ScanStatus, ScanStage, StageStatus
from backend.app.services.adb_client import AdbClient, AdbError
from backend.app.services.device_manager import DeviceManager
from backend.app.services.evidence_service import EvidenceService
from backend.app.services.mvt_engine import MVTEngine
from backend.app.utils.subprocess_utils import run_safe

log = logging.getLogger("ste.scan")

# ── In-memory scan state (supplemented by disk persistence) ──────────
_scans: dict[str, dict] = {}
_scan_lock = threading.Lock()

# Bugreport timeout: 600s (modern devices can take 5-10 minutes)
_BUGREPORT_TIMEOUT = 600


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
        disk_scans = {s["scan_id"]: s for s in self._evidence.list_scans()}
        with _scan_lock:
            for sid, data in _scans.items():
                if sid not in disk_scans:
                    device = data.get("device", {})
                    disk_scans[sid] = {
                        "scan_id": sid,
                        "status": data.get("status", "unknown"),
                        "device_serial": data.get("device_serial", ""),
                        "device_model": device.get("model"),
                        "device_manufacturer": device.get("manufacturer"),
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "findings_count": data.get("findings_count", 0),
                    }
                else:
                    # In-memory status is more current than disk
                    disk_scans[sid]["status"] = data.get("status", disk_scans[sid].get("status"))
        return list(disk_scans.values())

    def get_scan(self, scan_id: str) -> Optional[dict]:
        """Get full scan state — checks memory first, falls back to disk."""
        scan = _get_scan(scan_id)
        if scan:
            return scan
        # Fall back to disk — load persisted metadata
        meta = self._evidence.load_metadata(scan_id)
        if meta:
            # Cache it in memory for future access
            _set_scan(scan_id, meta)
            return meta
        return None

    def get_scan_logs(self, scan_id: str) -> str:
        """Get scan stdout log content."""
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            return ""
        # Check new location first, then legacy
        for log_path in [scan_dir / "logs" / "stdout.log", scan_dir / "stdout.log"]:
            if log_path.is_file():
                return log_path.read_text(encoding="utf-8", errors="replace")
        scan = self.get_scan(scan_id)
        return scan.get("log", "") if scan else ""

    def get_manifest(self, scan_id: str) -> Optional[dict]:
        """Get the evidence manifest for a scan."""
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            return None
        manifest_path = scan_dir / "manifest.json"
        if manifest_path.is_file():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return None

    def get_timeline(self, scan_id: str) -> list[dict]:
        """Get the structured activity timeline for a scan."""
        scan = self.get_scan(scan_id)
        if scan and "timeline" in scan:
            return scan["timeline"]
        return self._evidence.load_timeline(scan_id)

    def start_rapid_triage(self, device_serial: str) -> dict:
        """Start a Rapid Triage scan on the specified device."""
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

        # Define stages
        stages = [
            ScanStage(stage_id="device_check", display_name="Device Verification"),
            ScanStage(stage_id="device_metadata", display_name="Device Information"),
            ScanStage(stage_id="bugreport", display_name="System Diagnostic Collection"),
            ScanStage(stage_id="mvt_analysis", display_name="Forensic Analysis"),
            ScanStage(stage_id="device_properties", display_name="Device Properties"),
            ScanStage(stage_id="evidence_hashing", display_name="Evidence Integrity"),
            ScanStage(stage_id="ioc_analysis", display_name="Threat Indicator Analysis"),
            ScanStage(stage_id="findings_generation", display_name="Findings Generation"),
            ScanStage(stage_id="report_generation", display_name="Report Generation"),
        ]

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
            "current_operation": "Initializing examination...",
            "log": "",
            "timeline": [],
            "warnings": [],
            "errors": [],
            "findings_count": 0,
            "stages": [s.model_dump() for s in stages],
        }

        try:
            scan_state["adb_version"] = self._adb.get_version()
        except AdbError:
            pass

        # Save device snapshot and initial metadata
        self._evidence.save_device_snapshot(scan_id, device_info.model_dump())
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

        scan["_cancel_requested"] = True
        _set_scan(scan_id, scan)
        return {"message": "Cancellation requested", "scan_id": scan_id}

    # ── Internal scan execution ────────────────────────────────────────

    def _execute_rapid_triage(
        self, scan_id: str, serial: str, scan_dir: Path
    ) -> None:
        """Execute the Rapid Triage scan in a background thread."""
        scan = _get_scan(scan_id)
        if not scan:
            return
        all_log = ""
        bugreport_succeeded = False
        mvt_succeeded = False
        has_warnings = False

        try:
            # ── Stage 1: Device Verification ──
            self._begin_stage(scan_id, "device_check")
            self._update_scan(scan_id, "Verifying device connection...", "INFO")
            try:
                device_info = self._dm.get_device_info(serial)
                if device_info.state == DeviceState.CONNECTED:
                    self._complete_stage(scan_id, "device_check",
                        f"Device {device_info.model or serial} verified and connected")
                    self._log_event(scan_id, "SUCCESS", f"Device {device_info.model or serial} authorized and connected")
                else:
                    self._fail_stage(scan_id, "device_check",
                        f"Device state: {device_info.state.value}")
                    self._log_event(scan_id, "ERROR", f"Device not connected (state: {device_info.state.value})")
                    self._finalize_scan(scan_id, ScanStatus.FAILED, all_log)
                    return
            except Exception as exc:
                self._fail_stage(scan_id, "device_check", str(exc))
                self._log_event(scan_id, "ERROR", f"Device verification failed: {exc}")
                self._finalize_scan(scan_id, ScanStatus.FAILED, all_log)
                return

            if self._is_cancelled(scan_id):
                self._log_event(scan_id, "WARN", "Examination cancelled by user")
                self._finalize_scan(scan_id, ScanStatus.CANCELLED, all_log)
                return

            # ── Stage 2: Device Metadata ──
            self._begin_stage(scan_id, "device_metadata")
            self._update_scan(scan_id, "Collecting device information...", "INFO")
            try:
                model = device_info.model or "Unknown"
                mfr = device_info.manufacturer or "Unknown"
                android = device_info.android_version or "Unknown"
                patch = device_info.security_patch or "Unknown"
                self._complete_stage(scan_id, "device_metadata",
                    f"Collected: {mfr} {model}, Android {android}, patch {patch}")
                self._log_event(scan_id, "SUCCESS", f"{mfr} {model} identified")
                self._log_event(scan_id, "SUCCESS", f"Android {android} detected")
                if patch != "Unknown":
                    self._log_event(scan_id, "SUCCESS", f"Security patch: {patch}")
            except Exception as exc:
                self._warn_stage(scan_id, "device_metadata",
                    f"Partial metadata collected: {exc}")
                self._log_event(scan_id, "WARN", f"Partial device metadata: {exc}")
                has_warnings = True

            # ── Stage 3: Bugreport Collection ──
            self._begin_stage(scan_id, "bugreport")
            self._update_scan(scan_id, "Collecting system diagnostics from device...", "INFO")
            self._log_event(scan_id, "INFO", "Starting system diagnostic collection (this may take several minutes)")
            bugreport_path = scan_dir / "artifacts"

            adb_path = str(self._adb.adb_path)
            result = run_safe(
                [adb_path, "-s", serial, "bugreport", str(bugreport_path)],
                timeout=_BUGREPORT_TIMEOUT,
            )

            all_log += f"=== ADB BUGREPORT ===\n{result.stdout}\n{result.stderr}\n"
            self._evidence.save_stdout(scan_id, all_log)

            if self._is_cancelled(scan_id):
                self._log_event(scan_id, "WARN", "Examination cancelled by user")
                self._finalize_scan(scan_id, ScanStatus.CANCELLED, all_log)
                return

            bugreport_file = self._find_bugreport(bugreport_path)

            if result.ok and bugreport_file:
                size_mb = bugreport_file.stat().st_size / (1024 * 1024)
                self._complete_stage(scan_id, "bugreport",
                    f"System diagnostic collected ({size_mb:.1f} MB)")
                bugreport_succeeded = True
                self._log_event(scan_id, "SUCCESS", f"System diagnostic collected ({size_mb:.1f} MB)")
            elif bugreport_file:
                size_mb = bugreport_file.stat().st_size / (1024 * 1024)
                self._warn_stage(scan_id, "bugreport",
                    f"Collection completed with warnings ({size_mb:.1f} MB)")
                bugreport_succeeded = True
                has_warnings = True
                scan = _get_scan(scan_id)
                scan["warnings"].append("System diagnostic collection completed with warnings")
                _set_scan(scan_id, scan)
                self._log_event(scan_id, "WARN", f"Diagnostic collected with warnings ({size_mb:.1f} MB)")
            else:
                error_msg = result.stderr[:200] if result.stderr else "No diagnostic file produced"
                self._fail_stage(scan_id, "bugreport",
                    f"Collection failed: {error_msg}")
                has_warnings = True
                scan = _get_scan(scan_id)
                scan["warnings"].append(f"System diagnostic collection failed: {error_msg}")
                _set_scan(scan_id, scan)
                self._log_event(scan_id, "ERROR", f"System diagnostic collection failed: {error_msg[:100]}")

            # ── Stage 4: MVT Analysis ──
            if bugreport_succeeded and bugreport_file:
                self._begin_stage(scan_id, "mvt_analysis")
                self._update_scan(scan_id, "Running forensic analysis...", "INFO")
                self._log_event(scan_id, "INFO", "Starting MVT forensic analysis")
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

                # Count alerts from output
                alert_count = all_log.count("MEDIUM ALERT") + all_log.count("HIGH ALERT") + all_log.count("CRITICAL ALERT")

                if mvt_result.ok or mvt_output.is_dir():
                    mvt_succeeded = True
                    file_count = len(list(mvt_output.glob("*.json"))) if mvt_output.is_dir() else 0
                    self._complete_stage(scan_id, "mvt_analysis",
                        f"Analysis complete: {file_count} output files, {alert_count} alerts")
                    scan = _get_scan(scan_id)
                    scan["findings_count"] = alert_count
                    _set_scan(scan_id, scan)
                    self._log_event(scan_id, "SUCCESS", f"Forensic analysis complete: {file_count} modules, {alert_count} alerts")
                else:
                    self._fail_stage(scan_id, "mvt_analysis",
                        f"Analysis failed: {mvt_result.stderr[:200]}")
                    has_warnings = True
                    self._log_event(scan_id, "ERROR", f"Forensic analysis failed")
            else:
                self._skip_stage(scan_id, "mvt_analysis",
                    "Skipped — system diagnostic was not available")
                self._log_event(scan_id, "WARN", "Forensic analysis skipped (no diagnostic data)")

            if self._is_cancelled(scan_id):
                self._log_event(scan_id, "WARN", "Examination cancelled by user")
                self._finalize_scan(scan_id, ScanStatus.CANCELLED, all_log)
                return

            # ── Stage 5: Device Properties ──
            self._begin_stage(scan_id, "device_properties")
            self._update_scan(scan_id, "Collecting device properties...", "INFO")
            try:
                props = self._collect_device_props(serial)
                props_path = scan_dir / "artifacts" / "device_properties.json"
                props_path.write_text(json.dumps(props, indent=2), encoding="utf-8")
                prop_count = sum(1 for v in props.values() if v is not None)
                self._complete_stage(scan_id, "device_properties",
                    f"Collected {prop_count} device properties")
                self._log_event(scan_id, "SUCCESS", f"Collected {prop_count} device properties")
            except Exception as exc:
                self._fail_stage(scan_id, "device_properties", str(exc))
                has_warnings = True
                self._log_event(scan_id, "WARN", f"Device properties collection issue: {exc}")

            # ── Stage 6: Evidence Hashing & Manifest ──
            self._begin_stage(scan_id, "evidence_hashing")
            self._update_scan(scan_id, "Computing evidence integrity hashes...", "INFO")
            self._log_event(scan_id, "INFO", "Calculating SHA-256 hashes for all evidence files")
            # Save logs before hashing so they're included in the manifest
            self._evidence.save_command_log(scan_id, all_log)
            self._evidence.save_stdout(scan_id, all_log)
            # Save current metadata and timeline so manifest has complete info
            scan = _get_scan(scan_id)
            self._evidence.save_metadata(scan_id, scan)
            self._evidence.save_timeline(scan_id, scan.get("timeline", []))
            try:
                manifest = self._evidence.generate_manifest(scan_id, scan)
                file_count = manifest.get("file_count", 0)
                total_mb = manifest.get("total_bytes", 0) / (1024 * 1024)
                self._complete_stage(scan_id, "evidence_hashing",
                    f"SHA-256 hashes computed for {file_count} files ({total_mb:.1f} MB)")
                self._log_event(scan_id, "SUCCESS", f"Evidence integrity verified: {file_count} files hashed")
            except Exception as exc:
                self._warn_stage(scan_id, "evidence_hashing", f"Hashing issue: {exc}")
                self._log_event(scan_id, "WARN", f"Evidence hashing issue: {exc}")
                has_warnings = True

            # ── Stage 7: IOC Analysis ──
            self._skip_stage(scan_id, "ioc_analysis",
                "No threat indicator database was configured for this examination")
            self._log_event(scan_id, "INFO", "No IOC indicator database configured — skipping threat matching")

            # ── Stage 8: Findings Generation ──
            self._begin_stage(scan_id, "findings_generation")
            self._update_scan(scan_id, "Generating examination findings...", "INFO")
            self._log_event(scan_id, "INFO", "Parsing analysis results into findings")
            findings_summary = None
            try:
                from backend.app.services.finding_service import FindingService
                finding_svc = FindingService()
                findings_dir = scan_dir / "findings"
                findings_summary = finding_svc.parse_scan_findings(scan_id, findings_dir)
                scan = _get_scan(scan_id)
                scan["findings_count"] = findings_summary.total
                _set_scan(scan_id, scan)
                self._complete_stage(scan_id, "findings_generation",
                    f"{findings_summary.total} observations identified from {len(findings_summary.modules_analyzed)} modules")
                self._log_event(scan_id, "SUCCESS", f"Generated {findings_summary.total} findings from {findings_summary.total_records_processed:,} records")
            except Exception as exc:
                self._warn_stage(scan_id, "findings_generation", f"Findings parsing issue: {exc}")
                self._log_event(scan_id, "WARN", f"Findings generation completed with issue: {exc}")
                has_warnings = True

            # ── Stage 9: Report Generation ──
            self._begin_stage(scan_id, "report_generation")
            self._update_scan(scan_id, "Generating forensic report...", "INFO")
            self._log_event(scan_id, "INFO", "Generating PDF forensic audit report")
            # Verify manifest exists before attempting report generation
            manifest_path = scan_dir / "manifest.json"
            if not manifest_path.is_file():
                self._warn_stage(scan_id, "report_generation",
                    "MANIFEST_NOT_FOUND — manifest.json was not created during evidence hashing")
                self._log_event(scan_id, "ERROR", "Report generation failed: manifest.json not found")
                has_warnings = True
            else:
                try:
                    # Verify manifest is readable and belongs to this examination
                    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest_data.get("scan_id") != scan_id:
                        self._warn_stage(scan_id, "report_generation",
                            "MANIFEST_EXAMINATION_MISMATCH — manifest belongs to a different examination")
                        self._log_event(scan_id, "ERROR", "Report failed: manifest scan_id mismatch")
                        has_warnings = True
                    else:
                        from backend.app.services.report_service import ReportService
                        report_svc = ReportService()
                        report_path = report_svc.generate_report(scan_id, findings_summary)
                        if report_path and report_path.is_file() and report_path.stat().st_size > 0:
                            size_kb = report_path.stat().st_size / 1024
                            self._complete_stage(scan_id, "report_generation",
                                f"PDF report generated ({size_kb:.0f} KB)")
                            self._log_event(scan_id, "SUCCESS", f"Forensic audit report generated ({size_kb:.0f} KB)")
                            # Record report info in scan state
                            scan = _get_scan(scan_id)
                            scan["report_path"] = str(report_path)
                            scan["report_generated_at"] = datetime.now(timezone.utc).isoformat()
                            _set_scan(scan_id, scan)
                        else:
                            self._warn_stage(scan_id, "report_generation",
                                "PDF_RENDER_ERROR — report file was not created or is empty")
                            self._log_event(scan_id, "ERROR", "Report generation produced no output")
                            has_warnings = True
                except json.JSONDecodeError:
                    self._warn_stage(scan_id, "report_generation",
                        "MANIFEST_INVALID — manifest.json is not valid JSON")
                    self._log_event(scan_id, "ERROR", "Report failed: manifest.json is corrupt")
                    has_warnings = True
                except Exception as exc:
                    self._warn_stage(scan_id, "report_generation",
                        f"PDF_RENDER_ERROR — {str(exc)[:120]}")
                    self._log_event(scan_id, "WARN", f"Report generation failed: {str(exc)[:100]}")
                    has_warnings = True

            # ── Determine overall status ──
            if bugreport_succeeded and mvt_succeeded and not has_warnings:
                final_status = ScanStatus.COMPLETED
            elif bugreport_succeeded and mvt_succeeded:
                final_status = ScanStatus.COMPLETED_WITH_WARNINGS
            elif bugreport_succeeded or mvt_succeeded:
                final_status = ScanStatus.PARTIALLY_COMPLETED
            else:
                final_status = ScanStatus.FAILED

            self._log_event(scan_id, "SUCCESS" if final_status in (ScanStatus.COMPLETED, ScanStatus.COMPLETED_WITH_WARNINGS) else "ERROR",
                f"Examination {final_status.value.replace('_', ' ')}")
            self._finalize_scan(scan_id, final_status, all_log)

        except Exception as exc:
            log.exception("Scan %s failed: %s", scan_id, exc)
            all_log += f"\n=== ERROR ===\n{exc}\n"
            scan = _get_scan(scan_id)
            if scan:
                scan["errors"].append(str(exc))
                _set_scan(scan_id, scan)
            self._log_event(scan_id, "ERROR", f"Examination failed: {exc}")
            self._finalize_scan(scan_id, ScanStatus.FAILED, all_log)

    def _finalize_scan(self, scan_id: str, status: ScanStatus, log_content: str) -> None:
        """Finalize scan: update status, persist final metadata and timeline.

        Manifest generation happens in stage 6 (evidence_hashing), not here.
        This only saves final metadata and timeline.
        """
        scan = _get_scan(scan_id)
        if not scan:
            return

        scan["status"] = status.value
        scan["completed_at"] = datetime.now(timezone.utc).isoformat()
        scan["current_operation"] = f"Examination {status.value.replace('_', ' ')}"
        _set_scan(scan_id, scan)

        # Save final metadata
        self._evidence.save_metadata(scan_id, scan)

        # Save final timeline
        self._evidence.save_timeline(scan_id, scan.get("timeline", []))

        # Save human-readable examination log
        readable_log = self._format_readable_log(scan.get("timeline", []))
        self._evidence.save_examination_log(scan_id, readable_log)

    # ── Structured timeline/logging helpers ─────────────────────────────

    def _log_event(self, scan_id: str, level: str, message: str) -> None:
        """Add a structured event to the examination timeline."""
        entry = {
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        scan = _get_scan(scan_id)
        if scan:
            if "timeline" not in scan:
                scan["timeline"] = []
            scan["timeline"].append(entry)
            # Also append to the legacy string log for backward compat
            level_tag = {"SUCCESS": "OK", "WARN": "WARN", "ERROR": "ERROR"}.get(level, "INFO")
            scan["log"] = scan.get("log", "") + f"[{entry['time']}] [{level_tag:5s}] {message}\n"
            _set_scan(scan_id, scan)

    def _format_readable_log(self, timeline: list[dict]) -> str:
        """Format timeline entries into a human-readable log string."""
        lines = ["=" * 60, "S*EntryTrace Examination Activity Log", "=" * 60, ""]
        for entry in timeline:
            level = entry.get("level", "INFO")
            time = entry.get("time", "??:??:??")
            msg = entry.get("message", "")
            lines.append(f"{time}  [{level:7s}]  {msg}")
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ── Stage management helpers ───────────────────────────────────────

    def _get_stage(self, scan_id: str, stage_id: str) -> Optional[dict]:
        scan = _get_scan(scan_id)
        if not scan:
            return None
        for s in scan.get("stages", []):
            if s["stage_id"] == stage_id:
                return s
        return None

    def _begin_stage(self, scan_id: str, stage_id: str) -> None:
        stage = self._get_stage(scan_id, stage_id)
        if stage:
            stage["status"] = StageStatus.RUNNING.value
            stage["started_at"] = datetime.now(timezone.utc).isoformat()
            scan = _get_scan(scan_id)
            _set_scan(scan_id, scan)

    def _complete_stage(self, scan_id: str, stage_id: str, summary: str) -> None:
        stage = self._get_stage(scan_id, stage_id)
        if stage:
            now = datetime.now(timezone.utc).isoformat()
            stage["status"] = StageStatus.COMPLETED.value
            stage["completed_at"] = now
            stage["summary"] = summary
            if stage.get("started_at"):
                try:
                    start = datetime.fromisoformat(stage["started_at"])
                    end = datetime.fromisoformat(now)
                    stage["duration_seconds"] = (end - start).total_seconds()
                except ValueError:
                    pass
            scan = _get_scan(scan_id)
            _set_scan(scan_id, scan)

    def _warn_stage(self, scan_id: str, stage_id: str, summary: str) -> None:
        stage = self._get_stage(scan_id, stage_id)
        if stage:
            stage["status"] = StageStatus.COMPLETED_WITH_WARNINGS.value
            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
            stage["summary"] = summary
            scan = _get_scan(scan_id)
            _set_scan(scan_id, scan)

    def _fail_stage(self, scan_id: str, stage_id: str, error: str) -> None:
        stage = self._get_stage(scan_id, stage_id)
        if stage:
            stage["status"] = StageStatus.FAILED.value
            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
            stage["error"] = error
            stage["summary"] = f"Failed: {error[:100]}"
            scan = _get_scan(scan_id)
            _set_scan(scan_id, scan)

    def _skip_stage(self, scan_id: str, stage_id: str, summary: str) -> None:
        stage = self._get_stage(scan_id, stage_id)
        if stage:
            stage["status"] = StageStatus.SKIPPED.value
            stage["summary"] = summary
            scan = _get_scan(scan_id)
            _set_scan(scan_id, scan)

    def _update_scan(self, scan_id: str, operation: str, level: str = "INFO") -> None:
        scan = _get_scan(scan_id)
        if scan:
            scan["current_operation"] = operation
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
