"""S*EntryTrace — PDF Report Generation Service.

Generates forensic audit reports using fpdf2.
Never creates a fake report when no scan data exists.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from backend.app.models.finding import FindingSummary
from backend.app.services.evidence_service import EvidenceService

log = logging.getLogger("ste.report")


class ReportService:
    """Generate PDF forensic audit reports."""

    def __init__(self) -> None:
        self._evidence = EvidenceService()

    def generate_report(
        self,
        scan_id: str,
        findings: Optional[FindingSummary] = None,
    ) -> Optional[Path]:
        """Generate a PDF report for a completed scan.

        Returns the path to the generated PDF, or None if the scan
        does not exist or has no manifest.
        """
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            log.warning("No evidence directory for scan %s", scan_id)
            return None

        manifest_path = scan_dir / "manifest.json"
        if not manifest_path.is_file():
            log.warning("No manifest for scan %s — cannot generate report", scan_id)
            return None

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Load metadata
        meta_path = scan_dir / "metadata.json"
        meta = {}
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        pdf_path = scan_dir / "report.pdf"
        self._build_pdf(pdf_path, scan_id, manifest, meta, findings)
        log.info("Report generated: %s", pdf_path)
        return pdf_path

    def get_report_path(self, scan_id: str) -> Optional[Path]:
        """Return the report PDF path if it exists."""
        scan_dir = self._evidence.get_scan_directory(scan_id)
        if not scan_dir:
            return None
        path = scan_dir / "report.pdf"
        return path if path.is_file() else None

    def _build_pdf(
        self,
        output_path: Path,
        scan_id: str,
        manifest: dict,
        meta: dict,
        findings: Optional[FindingSummary],
    ) -> None:
        """Build the actual PDF document."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # ── Title ──────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 22)
        pdf.cell(0, 15, "S*EntryTrace", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, "Forensic Audit Report - Evidence Integrity Documentation",
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        pdf.set_draw_color(100, 100, 100)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(8)

        # ── Report Metadata ───────────────────────────────────────
        self._section(pdf, "Report Information")
        self._kv(pdf, "Report ID", f"RPT-{scan_id}")
        self._kv(pdf, "Scan ID", scan_id)
        self._kv(pdf, "Generated At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        self._kv(pdf, "Scan Profile", meta.get("scan_profile", "N/A"))
        self._kv(pdf, "Status", meta.get("status", "unknown"))

        # ── Device Information ─────────────────────────────────────
        device = meta.get("device", {})
        self._section(pdf, "Device Information")
        self._kv(pdf, "Serial", self._mask_serial(device.get("serial", "N/A")))
        self._kv(pdf, "Model", device.get("model", "N/A"))
        self._kv(pdf, "Manufacturer", device.get("manufacturer", "N/A"))
        self._kv(pdf, "Android Version", device.get("android_version", "N/A"))
        self._kv(pdf, "SDK Level", device.get("sdk_level", "N/A"))
        self._kv(pdf, "Security Patch", device.get("security_patch", "N/A"))
        self._kv(pdf, "Root Status", str(device.get("is_rooted", "Unknown")))

        # ── Collection Information ─────────────────────────────────
        self._section(pdf, "Collection Information")
        self._kv(pdf, "MVT Version", meta.get("mvt_version", "N/A"))
        self._kv(pdf, "ADB Version", meta.get("adb_version", "N/A"))
        self._kv(pdf, "Collection Start", meta.get("started_at", "N/A"))
        self._kv(pdf, "Collection End", meta.get("completed_at", "N/A"))
        self._kv(pdf, "Evidence Files", str(manifest.get("file_count", 0)))
        self._kv(pdf, "Total Size (bytes)", str(manifest.get("total_bytes", 0)))

        # ── Evidence Files ─────────────────────────────────────────
        files = manifest.get("files", [])
        if files:
            self._section(pdf, f"Evidence Files ({len(files)})")
            pdf.set_font("Courier", "", 7)
            for finfo in files[:50]:  # Limit to first 50
                line = f'{finfo.get("relative_path", "?")}  |  {finfo.get("sha256", "?")[:16]}..  |  {finfo.get("size_bytes", 0)} bytes'
                pdf.cell(0, 4, line, new_x="LMARGIN", new_y="NEXT")
            if len(files) > 50:
                pdf.cell(0, 4, f"... and {len(files) - 50} more files", new_x="LMARGIN", new_y="NEXT")

        # ── Findings ───────────────────────────────────────────────
        self._section(pdf, "Findings")
        if findings and findings.total > 0:
            pdf.set_font("Helvetica", "", 9)
            self._kv(pdf, "Total Findings", str(findings.total))
            for cat, count in findings.by_category.items():
                self._kv(pdf, f"  {cat}", str(count))
            pdf.ln(3)
            for f in findings.findings[:20]:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 5, f"[{f.severity.value.upper()}] {f.title}",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 4, f"  Category: {f.category.value} | Module: {f.source_module}")
                if f.description:
                    pdf.multi_cell(0, 4, f"  {f.description[:200]}")
                pdf.ln(2)
        else:
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(0, 6, "No findings detected by MVT analysis.",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, "This does NOT guarantee the device is safe.",
                     new_x="LMARGIN", new_y="NEXT")

        # ── Warnings ──────────────────────────────────────────────
        warnings = meta.get("warnings", []) + manifest.get("warnings", [])
        if warnings:
            self._section(pdf, "Warnings")
            pdf.set_font("Helvetica", "", 8)
            for w in warnings:
                pdf.multi_cell(0, 4, f"- {w}")

        # ── Limitations ───────────────────────────────────────────
        self._section(pdf, "Limitations and Disclaimer")
        pdf.set_font("Helvetica", "", 8)
        for lim in manifest.get("limitations", []):
            pdf.multi_cell(0, 4, f"- {lim}")
        pdf.ln(3)
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(0, 4,
            "This report documents forensic evidence collected by S*EntryTrace "
            "using the Mobile Verification Toolkit (MVT). Results are limited "
            "to the artifacts and indicators supported by MVT. This report does "
            "not guarantee device safety nor constitute a complete forensic "
            "examination. MVT coverage is limited to supported artifacts and "
            "publicly available indicators of compromise."
        )

        pdf.output(str(output_path))

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _section(pdf: FPDF, title: str) -> None:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(180, 180, 180)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

    @staticmethod
    def _kv(pdf: FPDF, key: str, value: str) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(55, 5, key + ":", new_x="RIGHT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, value, new_x="LMARGIN", new_y="NEXT")

    @staticmethod
    def _mask_serial(serial: str) -> str:
        """Partially mask device serial for report privacy."""
        if len(serial) <= 4:
            return serial
        return serial[:4] + "*" * (len(serial) - 4)
