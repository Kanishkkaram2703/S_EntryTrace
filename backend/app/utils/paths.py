"""S*EntryTrace — Utility path helpers."""

from pathlib import Path

from backend.app.config import settings


def evidence_path_for_device(serial: str) -> Path:
    """Return the evidence sub-directory for a given device serial."""
    safe_serial = "".join(c if c.isalnum() or c in "-_" else "_" for c in serial)
    path = settings.evidence_dir / safe_serial
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_path_for_device(serial: str) -> Path:
    """Return the reports sub-directory for a given device serial."""
    safe_serial = "".join(c if c.isalnum() or c in "-_" else "_" for c in serial)
    path = settings.reports_dir / safe_serial
    path.mkdir(parents=True, exist_ok=True)
    return path
