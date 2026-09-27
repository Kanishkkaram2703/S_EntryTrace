"""S*EntryTrace — Scan API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.scan_service import ScanService

router = APIRouter(prefix="/api/scans", tags=["scans"])
_scan_svc = ScanService()


class StartScanRequest(BaseModel):
    device_serial: str
    scan_profile: str = "rapid_triage"


@router.post("")
def start_scan(req: StartScanRequest):
    """Start a forensic scan on the specified device."""
    if req.scan_profile != "rapid_triage":
        raise HTTPException(400, f"Unsupported scan profile: {req.scan_profile}. Only 'rapid_triage' is available.")
    result = _scan_svc.start_rapid_triage(req.device_serial)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("")
def list_scans():
    """List all scans with enriched metadata."""
    scans = _scan_svc.list_scans()
    return {"count": len(scans), "scans": scans}


@router.get("/{scan_id}")
def get_scan(scan_id: str):
    """Get scan status and details (checks memory then disk)."""
    scan = _scan_svc.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, f"Scan '{scan_id}' not found")
    # Return a safe subset (exclude internal fields)
    return {k: v for k, v in scan.items() if not k.startswith("_")}


@router.get("/{scan_id}/logs")
def get_scan_logs(scan_id: str):
    """Get scan log output."""
    logs = _scan_svc.get_scan_logs(scan_id)
    return {"scan_id": scan_id, "logs": logs}


@router.get("/{scan_id}/timeline")
def get_scan_timeline(scan_id: str):
    """Get structured activity timeline for an examination."""
    timeline = _scan_svc.get_timeline(scan_id)
    return {"scan_id": scan_id, "timeline": timeline}


@router.get("/{scan_id}/manifest")
def get_scan_manifest(scan_id: str):
    """Get the evidence manifest for a scan."""
    manifest = _scan_svc.get_manifest(scan_id)
    if not manifest:
        raise HTTPException(404, "Manifest not found for this scan")
    return manifest


@router.post("/{scan_id}/cancel")
def cancel_scan(scan_id: str):
    """Request cancellation of a running scan."""
    result = _scan_svc.cancel_scan(scan_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
