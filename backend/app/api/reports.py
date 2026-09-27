"""S*EntryTrace — Report API endpoints.

Author: Kanishk Karam
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.services.evidence_service import EvidenceService
from backend.app.services.finding_service import FindingService
from backend.app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])

_evidence = EvidenceService()
_finding_svc = FindingService()
_report_svc = ReportService()


class ReportStatusResponse(BaseModel):
    scan_id: str
    exists: bool
    status: str = "unknown"  # not_generated | generating | available | failed
    size_bytes: int = 0
    error: str = ""


@router.get("/{scan_id}/status")
def get_report_status(scan_id: str):
    """Check whether a report PDF exists for this examination."""
    scan_dir = _evidence.get_scan_directory(scan_id)
    if not scan_dir:
        raise HTTPException(404, detail={
            "code": "EXAMINATION_NOT_FOUND",
            "message": f"Examination '{scan_id}' not found.",
        })
    report_path = _report_svc.get_report_path(scan_id)
    if report_path and report_path.is_file() and report_path.stat().st_size > 0:
        return ReportStatusResponse(
            scan_id=scan_id,
            exists=True,
            status="available",
            size_bytes=report_path.stat().st_size,
        )
    return ReportStatusResponse(
        scan_id=scan_id,
        exists=False,
        status="not_generated",
    )


@router.post("/{scan_id}/generate")
def generate_report(scan_id: str):
    """Force (re)generation of the PDF report for an examination."""
    scan_dir = _evidence.get_scan_directory(scan_id)
    if not scan_dir:
        raise HTTPException(404, detail={
            "code": "EXAMINATION_NOT_FOUND",
            "message": f"Examination '{scan_id}' not found.",
        })

    manifest_path = scan_dir / "manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(404, detail={
            "code": "MANIFEST_NOT_FOUND",
            "message": "Examination evidence manifest not found. The examination may not have completed.",
        })

    # Parse findings
    findings_dir = scan_dir / "findings"
    findings = _finding_svc.parse_scan_findings(scan_id, findings_dir)

    # Generate (or regenerate) the report
    try:
        report_path = _report_svc.generate_report(scan_id, findings, regenerate=True)
    except Exception as exc:
        raise HTTPException(500, detail={
            "code": "REPORT_RENDER_ERROR",
            "message": f"Report generation failed: {str(exc)[:300]}",
        })

    if not report_path:
        raise HTTPException(500, detail={
            "code": "REPORT_RENDER_ERROR",
            "message": "Report generation returned no output.",
        })

    size_bytes = report_path.stat().st_size if report_path.is_file() else 0
    return {
        "scan_id": scan_id,
        "status": "available",
        "message": "Report generated successfully.",
        "size_bytes": size_bytes,
    }


@router.get("/{scan_id}/pdf")
def get_report_pdf(scan_id: str):
    """Serve the generated PDF file directly. Same as GET /{scan_id} but explicit."""
    return _serve_pdf(scan_id)


@router.get("/{scan_id}")
def get_report(scan_id: str):
    """Generate and return the PDF report for a scan.

    If the report doesn't exist yet, it is generated on demand.
    """
    return _serve_pdf(scan_id)


def _serve_pdf(scan_id: str) -> FileResponse:
    """Serve the PDF for the given examination."""
    scan_dir = _evidence.get_scan_directory(scan_id)
    if not scan_dir:
        raise HTTPException(404, detail={
            "code": "EXAMINATION_NOT_FOUND",
            "message": f"Examination '{scan_id}' not found.",
        })

    # Check if report already exists
    report_path = _report_svc.get_report_path(scan_id)
    if report_path and report_path.is_file() and report_path.stat().st_size > 0:
        return FileResponse(
            str(report_path),
            media_type="application/pdf",
            filename=f"S_EntryTrace_Report_{scan_id}.pdf",
        )

    # Check for manifest and generate on demand
    manifest_path = scan_dir / "manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(404, detail={
            "code": "MANIFEST_NOT_FOUND",
            "message": "Examination evidence manifest not found. The examination may not have completed.",
        })

    findings_dir = scan_dir / "findings"
    findings = _finding_svc.parse_scan_findings(scan_id, findings_dir)

    try:
        report_path = _report_svc.generate_report(scan_id, findings)
    except Exception as exc:
        raise HTTPException(500, detail={
            "code": "REPORT_RENDER_ERROR",
            "message": f"Report generation failed: {str(exc)[:300]}",
        })

    if not report_path or not report_path.is_file():
        raise HTTPException(500, detail={
            "code": "REPORT_RENDER_ERROR",
            "message": "Report generation returned no output.",
        })

    return FileResponse(
        str(report_path),
        media_type="application/pdf",
        filename=f"S_EntryTrace_Report_{scan_id}.pdf",
    )
