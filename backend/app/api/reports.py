"""S*EntryTrace — Report API endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.services.evidence_service import EvidenceService
from backend.app.services.finding_service import FindingService
from backend.app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])

_evidence = EvidenceService()
_finding_svc = FindingService()
_report_svc = ReportService()


@router.get("/{scan_id}")
def get_report(scan_id: str):
    """Generate and return the PDF report for a scan.

    If the report doesn't exist yet, it is generated on demand.
    """
    # Check if report already exists
    report_path = _report_svc.get_report_path(scan_id)
    if report_path:
        return FileResponse(
            str(report_path),
            media_type="application/pdf",
            filename=f"SEntryTrace_Report_{scan_id}.pdf",
        )

    # Generate it
    scan_dir = _evidence.get_scan_directory(scan_id)
    if not scan_dir:
        raise HTTPException(404, f"Scan '{scan_id}' not found")

    findings_dir = scan_dir / "findings"
    findings = _finding_svc.parse_scan_findings(scan_id, findings_dir)
    report_path = _report_svc.generate_report(scan_id, findings)

    if not report_path:
        raise HTTPException(500, "Failed to generate report. Ensure the scan has a manifest.")

    return FileResponse(
        str(report_path),
        media_type="application/pdf",
        filename=f"SEntryTrace_Report_{scan_id}.pdf",
    )
