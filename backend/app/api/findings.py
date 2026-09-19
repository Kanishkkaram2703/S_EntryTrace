"""S*EntryTrace — Findings API endpoints."""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from backend.app.services.evidence_service import EvidenceService
from backend.app.services.finding_service import FindingService

router = APIRouter(prefix="/api/scans", tags=["findings"])

_evidence = EvidenceService()
_finding_svc = FindingService()


@router.get("/{scan_id}/findings")
def get_scan_findings(scan_id: str):
    """Get parsed findings for a scan."""
    scan_dir = _evidence.get_scan_directory(scan_id)
    if not scan_dir:
        raise HTTPException(404, f"Scan '{scan_id}' not found")

    findings_dir = scan_dir / "findings"
    summary = _finding_svc.parse_scan_findings(scan_id, findings_dir)
    return summary.model_dump()
