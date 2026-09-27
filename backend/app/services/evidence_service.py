"""S*EntryTrace — Evidence management service.

Creates structured evidence directories, calculates SHA-256 hashes,
and generates machine-readable manifests for each scan.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.app.config import settings
from backend.app.utils.hashing import hash_directory, sha256_file

log = logging.getLogger("ste.evidence")


class EvidenceService:
    """Manages evidence storage, hashing, and manifest creation."""

    def __init__(self) -> None:
        self._base = settings.evidence_dir / "scans"

    def create_scan_directory(self, scan_id: str) -> Path:
        """Create the evidence directory structure for a scan."""
        scan_dir = self._base / scan_id
        for sub in ("artifacts", "findings", "hashes", "logs", "report"):
            (scan_dir / sub).mkdir(parents=True, exist_ok=True)
        return scan_dir

    def get_scan_directory(self, scan_id: str) -> Optional[Path]:
        """Return the scan directory if it exists."""
        d = self._base / scan_id
        return d if d.is_dir() else None

    # ── Metadata persistence ──────────────────────────────────────────

    def save_metadata(self, scan_id: str, metadata: dict) -> Path:
        """Save scan metadata JSON."""
        scan_dir = self._base / scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        path = scan_dir / "metadata.json"
        # Remove internal fields before persisting
        clean = {k: v for k, v in metadata.items() if not k.startswith("_")}
        path.write_text(json.dumps(clean, indent=2, default=str), encoding="utf-8")
        return path

    def load_metadata(self, scan_id: str) -> Optional[dict]:
        """Load scan metadata from disk."""
        scan_dir = self._base / scan_id
        meta_path = scan_dir / "metadata.json"
        if meta_path.is_file():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_device_snapshot(self, scan_id: str, device_data: dict) -> Path:
        """Persist device metadata snapshot at examination start time."""
        scan_dir = self._base / scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        path = scan_dir / "device.json"
        path.write_text(json.dumps(device_data, indent=2, default=str), encoding="utf-8")
        return path

    def save_timeline(self, scan_id: str, timeline: list[dict]) -> Path:
        """Persist structured activity timeline."""
        scan_dir = self._base / scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        path = scan_dir / "timeline.json"
        path.write_text(json.dumps(timeline, indent=2, default=str), encoding="utf-8")
        return path

    def load_timeline(self, scan_id: str) -> list[dict]:
        """Load activity timeline from disk."""
        scan_dir = self._base / scan_id
        path = scan_dir / "timeline.json"
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    # ── Log persistence ───────────────────────────────────────────────

    def save_command_log(self, scan_id: str, content: str) -> Path:
        """Save the command execution log."""
        path = self._base / scan_id / "logs" / "commands.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        # Also save to legacy location for backward compatibility
        legacy = self._base / scan_id / "command_log.txt"
        legacy.write_text(content, encoding="utf-8")
        return path

    def save_stdout(self, scan_id: str, content: str) -> Path:
        path = self._base / scan_id / "logs" / "stdout.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        # Also save to legacy location
        legacy = self._base / scan_id / "stdout.log"
        legacy.write_text(content, encoding="utf-8")
        return path

    def save_stderr(self, scan_id: str, content: str) -> Path:
        path = self._base / scan_id / "logs" / "stderr.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def save_examination_log(self, scan_id: str, content: str) -> Path:
        """Save the human-readable examination log."""
        path = self._base / scan_id / "logs" / "examination.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    # ── Hashing & Manifests ───────────────────────────────────────────

    def compute_hashes(self, scan_id: str) -> list[dict]:
        """Calculate SHA-256 hashes for all files in the scan directory."""
        scan_dir = self._base / scan_id
        if not scan_dir.is_dir():
            return []
        hashes = hash_directory(scan_dir)
        # Save hash manifest
        hash_path = scan_dir / "hashes" / "sha256_manifest.json"
        hash_path.parent.mkdir(parents=True, exist_ok=True)
        hash_path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
        log.info("Computed %d file hashes for scan %s", len(hashes), scan_id)
        return hashes

    def generate_manifest(self, scan_id: str, scan_meta: dict) -> dict:
        """Generate a complete evidence manifest."""
        scan_dir = self._base / scan_id
        hashes = self.compute_hashes(scan_id)

        total_bytes = sum(h.get("size_bytes", 0) for h in hashes)

        manifest = {
            "scan_id": scan_id,
            "device": scan_meta.get("device", {}),
            "mvt_version": scan_meta.get("mvt_version"),
            "adb_version": scan_meta.get("adb_version"),
            "scan_profile": scan_meta.get("scan_profile", ""),
            "collection_start": scan_meta.get("started_at"),
            "collection_end": scan_meta.get("completed_at"),
            "collection_status": scan_meta.get("status", "unknown"),
            "file_count": len(hashes),
            "total_bytes": total_bytes,
            "files": hashes,
            "warnings": scan_meta.get("warnings", []),
            "errors": scan_meta.get("errors", []),
            "limitations": [
                "Evidence collected via ADB read-only commands only.",
                "MVT coverage is limited to supported artifacts and indicators.",
                "Not a complete forensic acquisition.",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        manifest_path = scan_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )
        log.info("Manifest generated: %s", manifest_path)
        return manifest

    # ── Report path helpers ───────────────────────────────────────────

    def get_report_path(self, scan_id: str) -> Optional[Path]:
        """Return the report PDF path if it exists."""
        scan_dir = self._base / scan_id
        if not scan_dir:
            return None
        # Check new location first, then legacy
        new_path = scan_dir / "report" / "report.pdf"
        if new_path.is_file():
            return new_path
        legacy = scan_dir / "report.pdf"
        if legacy.is_file():
            return legacy
        return None

    # ── Listing ───────────────────────────────────────────────────────

    def list_scans(self) -> list[dict]:
        """List all scan directories with enriched info from metadata."""
        if not self._base.is_dir():
            return []
        scans = []
        for d in sorted(self._base.iterdir()):
            if d.is_dir():
                meta_path = d / "metadata.json"
                meta = {}
                if meta_path.is_file():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass
                device = meta.get("device", {})
                scans.append({
                    "scan_id": d.name,
                    "has_manifest": (d / "manifest.json").is_file(),
                    "has_report": (d / "report" / "report.pdf").is_file() or (d / "report.pdf").is_file(),
                    "status": meta.get("status", "unknown"),
                    "device_serial": meta.get("device_serial", ""),
                    "device_model": device.get("model"),
                    "device_manufacturer": device.get("manufacturer"),
                    "started_at": meta.get("started_at"),
                    "completed_at": meta.get("completed_at"),
                    "findings_count": meta.get("findings_count", 0),
                })
        return scans
