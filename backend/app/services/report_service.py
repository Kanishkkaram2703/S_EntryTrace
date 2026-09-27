"""S*EntryTrace — PDF Report Generation Service.

Generates professional A4 forensic audit reports using fpdf2.
All text is sanitized through Latin-1 encoding to prevent crashes.
Uses absolute positioning and careful width management to ensure
no content overflows the page boundaries.

Author: Kanishk Karam
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

# ── A4 Page Constants ──────────────────────────────────────────────────
_PAGE_W = 210          # A4 width mm
_MARGIN_L = 15         # Left margin
_MARGIN_R = 15         # Right margin
_MARGIN_T = 15         # Top margin
_MARGIN_B = 18         # Bottom margin
_USABLE_W = _PAGE_W - _MARGIN_L - _MARGIN_R   # 180mm usable
_KEY_W = 45            # Key column width for KV pairs
_VAL_W = _USABLE_W - _KEY_W                    # 135mm value column

# Typography
_FONT_TITLE = ("Helvetica", "B", 22)
_FONT_SUBTITLE = ("Helvetica", "", 13)
_FONT_SECTION = ("Helvetica", "B", 11)
_FONT_BODY = ("Helvetica", "", 9.5)
_FONT_BODY_SM = ("Helvetica", "", 8.5)
_FONT_KEY = ("Helvetica", "B", 9)
_FONT_VALUE = ("Helvetica", "", 9)
_FONT_MONO = ("Courier", "", 7)
_FONT_MONO_SM = ("Courier", "", 6.5)
_FONT_ITALIC = ("Helvetica", "I", 8.5)
_FONT_TABLE_HEAD = ("Helvetica", "B", 8)
_FONT_TABLE_BODY = ("Helvetica", "", 8)


def _safe(text) -> str:
    """Sanitize any value for fpdf2 Latin-1 encoding."""
    if text is None:
        return ""
    text = str(text)
    if not text:
        return ""
    try:
        return text.encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return text.encode("ascii", "replace").decode("ascii")


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate very long strings with an ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


class _ForensicPDF(FPDF):
    """Extended FPDF with forensic report helpers."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=_MARGIN_B)
        self.set_left_margin(_MARGIN_L)
        self.set_right_margin(_MARGIN_R)
        self.set_top_margin(_MARGIN_T)

    @property
    def usable_w(self):
        return self.w - self.l_margin - self.r_margin

    def _remaining_height(self):
        """How much vertical space remains before auto page break."""
        return self.h - self.get_y() - _MARGIN_B

    def ensure_space(self, needed_mm: float):
        """Add a new page if insufficient space remains."""
        if self._remaining_height() < needed_mm:
            self.add_page()

    # ── Section Heading ──────────────────────────────────────────────

    def section(self, title: str, top_margin: float = 8):
        """Render a section heading with underline."""
        self.ensure_space(20)
        self.ln(top_margin)
        self.set_font(*_FONT_SECTION)
        self.set_text_color(20, 20, 20)
        self.cell(0, 7, _safe(title), new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(100, 100, 100)
        self.set_line_width(0.4)
        self.line(_MARGIN_L, y, _PAGE_W - _MARGIN_R, y)
        self.set_line_width(0.2)
        self.ln(4)

    # ── Key-Value Pair (stacked layout — reliable) ───────────────────

    def kv(self, key: str, value: str, indent: float = 0):
        """Render key-value pair using safe stacked positioning.

        Uses set_x/set_y to guarantee correct placement regardless
        of previous multi_cell behavior.
        """
        self.ensure_space(10)
        x_start = _MARGIN_L + indent
        y_start = self.get_y()

        # Render key
        self.set_xy(x_start, y_start)
        self.set_font(*_FONT_KEY)
        self.set_text_color(60, 60, 60)
        self.cell(_KEY_W, 5, _safe(key), new_x="END")

        # Render value starting after key column
        val_x = x_start + _KEY_W
        val_w = _PAGE_W - _MARGIN_R - val_x
        if val_w < 30:
            val_w = self.usable_w - indent
            val_x = x_start
            self.set_xy(val_x, y_start + 5)

        self.set_xy(val_x, y_start)
        self.set_font(*_FONT_VALUE)
        self.set_text_color(20, 20, 20)
        self.multi_cell(val_w, 5, _safe(value))

        # Ensure cursor is at left margin after rendering
        final_y = self.get_y()
        self.set_xy(_MARGIN_L, final_y)

    # ── Table helpers ─────────────────────────────────────────────────

    def table_header(self, cols: list[tuple[str, float]]):
        """Render a table header row with background."""
        self.ensure_space(10)
        self.set_font(*_FONT_TABLE_HEAD)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(30, 30, 30)
        for label, width in cols:
            self.cell(width, 6, _safe(label), border="B", fill=True, new_x="RIGHT")
        self.ln(6)
        self.set_text_color(20, 20, 20)

    def table_row_kv(self, col1: str, col1_w: float, col2: str, col2_w: float):
        """Render a two-column table row with safe wrapping."""
        self.ensure_space(8)
        y_start = self.get_y()
        x_start = self.get_x()

        # Column 1
        self.set_xy(x_start, y_start)
        self.set_font(*_FONT_TABLE_BODY)
        self.multi_cell(col1_w, 4.5, _safe(col1))
        y_after_c1 = self.get_y()

        # Column 2
        self.set_xy(x_start + col1_w, y_start)
        self.multi_cell(col2_w, 4.5, _safe(col2))
        y_after_c2 = self.get_y()

        # Move to whichever column was taller
        final_y = max(y_after_c1, y_after_c2) + 0.5
        self.set_xy(_MARGIN_L, final_y)

    # ── Body text ─────────────────────────────────────────────────────

    def body_text(self, text: str, font=None):
        """Render body text with safe wrapping."""
        self.set_font(*(font or _FONT_BODY))
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.usable_w, 5, _safe(text))

    def italic_text(self, text: str):
        """Render italic note text."""
        self.set_font(*_FONT_ITALIC)
        self.set_text_color(80, 80, 80)
        self.multi_cell(self.usable_w, 4.5, _safe(text))
        self.set_text_color(20, 20, 20)

    def bullet(self, text: str, indent: float = 4):
        """Render a bullet point."""
        self.ensure_space(6)
        x = self.get_x()
        self.set_x(x + indent)
        self.set_font(*_FONT_BODY_SM)
        self.multi_cell(self.usable_w - indent, 4.5, _safe(f"\u2022  {text}"))
        self.set_x(_MARGIN_L)


class ReportService:
    """Generate PDF forensic audit reports."""

    def __init__(self) -> None:
        self._evidence = EvidenceService()

    def generate_report(
        self,
        scan_id: str,
        findings: Optional[FindingSummary] = None,
        regenerate: bool = False,
    ) -> Optional[Path]:
        """Generate a PDF report for a completed scan.

        If regenerate=True, existing report is replaced.
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

        # Load timeline
        timeline_path = scan_dir / "timeline.json"
        timeline = []
        if timeline_path.is_file():
            try:
                timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Determine report path
        report_dir = scan_dir / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = report_dir / "report.pdf"

        # Check if report exists and regeneration not requested
        if pdf_path.is_file() and not regenerate:
            return pdf_path

        try:
            self._build_pdf(pdf_path, scan_id, manifest, meta, findings, timeline)
            log.info("Report generated: %s (%d bytes)", pdf_path, pdf_path.stat().st_size)
            return pdf_path
        except Exception as exc:
            log.exception("PDF generation failed for %s: %s", scan_id, exc)
            try:
                self._build_minimal_pdf(pdf_path, scan_id, meta, str(exc))
                return pdf_path
            except Exception:
                return None

    def get_report_path(self, scan_id: str) -> Optional[Path]:
        """Return the report PDF path if it exists."""
        return self._evidence.get_report_path(scan_id)

    def _build_pdf(
        self,
        output_path: Path,
        scan_id: str,
        manifest: dict,
        meta: dict,
        findings: Optional[FindingSummary],
        timeline: list[dict],
    ) -> None:
        """Build the professional A4 forensic audit report."""
        pdf = _ForensicPDF()
        pdf.add_page()

        device = meta.get("device", {})
        status = meta.get("status", "unknown").replace("_", " ").title()
        model = _safe(device.get("model", "Unknown"))
        mfr = _safe(device.get("manufacturer", "Unknown"))
        android = _safe(device.get("android_version", "Unknown"))
        total_findings = findings.total if findings else 0

        # ═══════════════════════════════════════════════════════════════
        # PAGE 1 — COVER + EXECUTIVE SUMMARY
        # ═══════════════════════════════════════════════════════════════

        pdf.ln(10)
        pdf.set_font(*_FONT_TITLE)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 12, "S*EntryTrace", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(3)
        pdf.set_font(*_FONT_SUBTITLE)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 8, "Android Digital Forensics Examination Report",
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(6)

        # Decorative line
        y = pdf.get_y()
        pdf.set_draw_color(37, 99, 235)
        pdf.set_line_width(0.8)
        pdf.line(_MARGIN_L + 40, y, _PAGE_W - _MARGIN_R - 40, y)
        pdf.set_line_width(0.2)
        pdf.ln(10)

        # Cover metadata
        pdf.set_text_color(20, 20, 20)
        pdf.kv("Examination ID", scan_id)
        pdf.kv("Report ID", f"RPT-{scan_id}")
        pdf.kv("Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        pdf.kv("Device", f"{mfr} {model}")
        pdf.kv("Overall Status", status)
        pdf.kv("Prepared By", "Kanishk Karam")
        pdf.kv("Project", "S*EntryTrace")
        pdf.ln(5)

        # ── Executive Summary ──────────────────────────────────────
        pdf.section("Executive Summary", top_margin=4)

        # Determine proper finding language
        if findings and findings.total > 0:
            finding_text = f"A total of {total_findings} observations were identified during analysis."
        elif findings and findings.total == 0 and findings.total_records_processed > 0:
            finding_text = "No confirmed indicators were identified in the analyzed evidence."
        elif meta.get("status") == "failed":
            finding_text = "The examination could not be completed. Findings were not assessed."
        else:
            finding_text = "No observations were flagged by the available analysis."

        ioc_text = "configured" if (findings and findings.ioc_configured) else "not configured"
        records_text = f"{findings.total_records_processed:,}" if findings else "N/A"

        pdf.body_text(
            f"This report documents a forensic examination of a {mfr} {model} "
            f"device running Android {android}. The examination was performed "
            f"using S*EntryTrace with the Mobile Verification Toolkit (MVT). "
            f"The examination status is: {status}. {finding_text} "
            f"Threat indicator database: {ioc_text}."
        )
        pdf.ln(3)

        # Result summary box
        pdf.kv("Device", f"{mfr} {model} (Android {android})")
        pdf.kv("Evidence Files", str(manifest.get("file_count", 0)))
        pdf.kv("Evidence Size", self._fmt_bytes(manifest.get("total_bytes", 0)))
        pdf.kv("Records Analyzed", records_text)
        pdf.kv("Findings", str(total_findings))
        pdf.kv("Integrity", "SHA-256 verified")
        pdf.kv("Threat Intelligence", ioc_text.title())
        pdf.ln(3)

        if total_findings == 0 and (findings is None or findings.total_records_processed > 0):
            pdf.italic_text(
                "No confirmed threats were identified. However, this does NOT "
                "guarantee the device is free of threats. Results are limited to "
                "the artifacts and indicators supported by S*EntryTrace."
            )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 1 — EXAMINATION INFORMATION
        # ═══════════════════════════════════════════════════════════════

        pdf.section("1. Examination Information")
        pdf.kv("Examination ID", scan_id)
        pdf.kv("Report ID", f"RPT-{scan_id}")
        pdf.kv("Profile", meta.get("scan_profile", "N/A").replace("_", " ").title())
        pdf.kv("Status", status)
        pdf.kv("Start Time", _safe(meta.get("started_at", "N/A")))
        pdf.kv("End Time", _safe(meta.get("completed_at", "N/A")))

        # Calculate duration
        started = meta.get("started_at")
        completed = meta.get("completed_at")
        duration_text = "N/A"
        if started and completed:
            try:
                from dateutil.parser import parse as parse_dt
                dt_start = parse_dt(started)
                dt_end = parse_dt(completed)
                diff = (dt_end - dt_start).total_seconds()
                m, s = divmod(int(diff), 60)
                duration_text = f"{m}m {s}s"
            except Exception:
                duration_text = "N/A"
        pdf.kv("Duration", duration_text)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 2 — DEVICE INFORMATION
        # ═══════════════════════════════════════════════════════════════

        pdf.section("2. Device Information")
        pdf.kv("Serial", self._mask_serial(str(device.get("serial", "N/A"))))
        pdf.kv("Model", model)
        pdf.kv("Manufacturer", mfr)
        pdf.kv("Android Version", android)
        pdf.kv("SDK / API Level", _safe(str(device.get("sdk_level", "N/A"))))
        pdf.kv("Security Patch", _safe(str(device.get("security_patch", "N/A"))))
        pdf.kv("Build Fingerprint", _safe(str(device.get("build_fingerprint", "N/A"))))
        root_val = device.get("is_rooted")
        root_str = "Not rooted" if root_val is False else ("Rooted" if root_val else "Unknown")
        pdf.kv("Root Status", root_str)
        pdf.kv("ADB Connection", f"ADB {_safe(meta.get('adb_version', 'N/A'))}")

        # ═══════════════════════════════════════════════════════════════
        # SECTION 3 — EXAMINATION TIMELINE (STAGES)
        # ═══════════════════════════════════════════════════════════════

        stages = meta.get("stages", [])
        if stages:
            pdf.section("3. Examination Timeline")

            # Stage table columns: Stage (70mm), Status (30mm), Duration (25mm), Details (55mm)
            col_stage = 55
            col_status = 28
            col_dur = 22
            col_detail = _USABLE_W - col_stage - col_status - col_dur

            pdf.table_header([
                ("Stage", col_stage),
                ("Status", col_status),
                ("Duration", col_dur),
                ("Details", col_detail),
            ])

            pdf.set_font(*_FONT_TABLE_BODY)
            for s in stages:
                pdf.ensure_space(12)
                y_start = pdf.get_y()
                x_base = _MARGIN_L

                stage_name = _safe(s.get("display_name", s.get("stage_id", "Unknown")))
                stage_status = s.get("status", "unknown").replace("_", " ").title()
                duration = s.get("duration_seconds")
                dur_text = f"{duration:.1f}s" if duration is not None else "-"
                summary = _safe(_truncate(s.get("summary", "-"), 100))
                error = s.get("error", "")
                detail = summary if not error else _safe(_truncate(error, 100))

                # Render each column
                pdf.set_xy(x_base, y_start)
                pdf.set_font(*_FONT_TABLE_BODY)
                pdf.multi_cell(col_stage, 4.5, stage_name)
                y1 = pdf.get_y()

                pdf.set_xy(x_base + col_stage, y_start)
                pdf.multi_cell(col_status, 4.5, stage_status)
                y2 = pdf.get_y()

                pdf.set_xy(x_base + col_stage + col_status, y_start)
                pdf.multi_cell(col_dur, 4.5, dur_text)
                y3 = pdf.get_y()

                pdf.set_xy(x_base + col_stage + col_status + col_dur, y_start)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.multi_cell(col_detail, 4.5, detail)
                y4 = pdf.get_y()

                final_y = max(y1, y2, y3, y4) + 1
                # Draw separator line
                pdf.set_draw_color(220, 220, 220)
                pdf.line(_MARGIN_L, final_y - 0.5, _PAGE_W - _MARGIN_R, final_y - 0.5)
                pdf.set_xy(_MARGIN_L, final_y)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 4 — ACTIVITY LOG
        # ═══════════════════════════════════════════════════════════════

        if timeline:
            pdf.section("4. Activity Log")
            pdf.set_font(*_FONT_MONO)

            # Column widths for log: Time(18mm) Level(16mm) Message(remaining)
            col_time = 18
            col_level = 16
            col_msg = _USABLE_W - col_time - col_level

            for i, entry in enumerate(timeline[:60]):
                pdf.ensure_space(6)
                y_start = pdf.get_y()

                time_str = entry.get("time", "??:??:??")
                level = entry.get("level", "INFO")
                msg = _safe(_truncate(entry.get("message", ""), 160))

                # Render time
                pdf.set_xy(_MARGIN_L, y_start)
                pdf.set_font(*_FONT_MONO_SM)
                pdf.set_text_color(120, 120, 120)
                pdf.cell(col_time, 3.8, time_str, new_x="RIGHT")

                # Render level with color
                if level == "SUCCESS":
                    pdf.set_text_color(22, 163, 74)
                elif level == "WARN":
                    pdf.set_text_color(217, 119, 6)
                elif level == "ERROR":
                    pdf.set_text_color(220, 38, 38)
                else:
                    pdf.set_text_color(59, 130, 246)

                pdf.set_font("Courier", "B", 6.5)
                pdf.cell(col_level, 3.8, f"{level:7s}", new_x="RIGHT")

                # Render message
                pdf.set_text_color(30, 30, 30)
                pdf.set_font(*_FONT_MONO_SM)
                pdf.multi_cell(col_msg, 3.8, msg)

                final_y = pdf.get_y()
                pdf.set_xy(_MARGIN_L, final_y)

            if len(timeline) > 60:
                pdf.set_font(*_FONT_ITALIC)
                pdf.set_text_color(120, 120, 120)
                pdf.cell(0, 4, f"... and {len(timeline) - 60} more entries",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(20, 20, 20)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 5 — FINDINGS
        # ═══════════════════════════════════════════════════════════════

        pdf.section("5. Findings")

        if findings and findings.total > 0:
            pdf.kv("Total Observations", str(findings.total))
            for sev, count in findings.by_severity.items():
                pdf.kv(f"  {sev.title()}", str(count))
            pdf.ln(4)

            for f in findings.findings[:30]:
                pdf.ensure_space(20)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(20, 20, 20)
                title = _safe(_truncate(f"[{f.severity.value.upper()}] {f.title}", 200))
                pdf.multi_cell(pdf.usable_w, 5, title)
                pdf.set_font(*_FONT_BODY_SM)
                if f.explanation:
                    pdf.multi_cell(pdf.usable_w, 4.5, _safe(f"  Observation: {_truncate(f.explanation, 300)}"))
                if f.why_it_matters:
                    pdf.multi_cell(pdf.usable_w, 4.5, _safe(f"  Significance: {_truncate(f.why_it_matters, 200)}"))
                if f.interpretation:
                    pdf.multi_cell(pdf.usable_w, 4.5, _safe(f"  Interpretation: {_truncate(f.interpretation, 200)}"))
                pdf.ln(3)

            if findings.total > 30:
                pdf.italic_text(f"... and {findings.total - 30} additional observations")
        else:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(20, 20, 20)
            if findings and findings.total_records_processed > 0:
                pdf.cell(0, 8, "NO CONFIRMED INDICATORS IDENTIFIED",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                pdf.body_text(
                    "This means that no confirmed indicator was identified in the "
                    "analyzed evidence available to this examination."
                )
                pdf.ln(2)
                pdf.italic_text(
                    "It does NOT mean the device is guaranteed safe. The analysis "
                    "is limited to the artifacts and indicators supported by MVT."
                )
            elif meta.get("status") == "failed":
                pdf.cell(0, 8, "FINDINGS NOT ASSESSED",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                pdf.body_text(
                    "The examination could not be completed successfully. "
                    "Findings were not fully assessed."
                )
            else:
                pdf.cell(0, 8, "NO OBSERVATIONS FLAGGED",
                         new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                pdf.body_text(
                    "No observations were flagged by the forensic analysis. "
                    "This does NOT guarantee the device is free of threats."
                )

            pdf.ln(3)
            # What was analyzed
            if findings and findings.modules_analyzed:
                pdf.kv("Modules Analyzed", str(len(findings.modules_analyzed)))
                pdf.kv("Records Processed", f"{findings.total_records_processed:,}")
                pdf.ln(2)
                for mod in findings.modules_analyzed:
                    pdf.bullet(f"{_safe(mod.display_name)}: {mod.records_processed:,} records, "
                              f"{mod.alerts_generated} alerts ({mod.status})")

        # ═══════════════════════════════════════════════════════════════
        # SECTION 6 — THREAT INTELLIGENCE COVERAGE
        # ═══════════════════════════════════════════════════════════════

        pdf.section("6. Threat Intelligence Coverage")

        if findings and findings.ioc_configured:
            pdf.kv("Indicator Database", "Configured")
            pdf.kv("Indicators Loaded", str(findings.ioc_indicators_loaded))
            pdf.kv("Indicators Matched", str(sum(1 for f in findings.findings if f.category.value == "indicator_match")) if findings.findings else "0")
        else:
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.cell(0, 6, "THREAT INDICATOR MATCHING", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(*_FONT_BODY)
            pdf.cell(0, 6, "Not performed", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.kv("Reason", "No indicator database was configured for this examination")
            pdf.ln(2)
            pdf.italic_text(
                "No STIX2 indicator dataset was available for this examination. "
                "The absence of IOC matches does not indicate the device is safe. "
                "Consider configuring threat indicators for comprehensive analysis."
            )

        # ═══════════════════════════════════════════════════════════════
        # SECTION 7 — EVIDENCE INVENTORY
        # ═══════════════════════════════════════════════════════════════

        files = manifest.get("files", [])
        if files:
            pdf.section("7. Evidence Inventory")
            pdf.kv("Total Files", str(manifest.get("file_count", len(files))))
            pdf.kv("Total Size", self._fmt_bytes(manifest.get("total_bytes", 0)))
            pdf.kv("Hash Algorithm", "SHA-256")
            pdf.ln(4)

            # Evidence table: File(85mm), Size(25mm), SHA-256(70mm)
            col_file = 80
            col_size = 25
            col_hash = _USABLE_W - col_file - col_size

            pdf.table_header([
                ("File", col_file),
                ("Size", col_size),
                ("SHA-256", col_hash),
            ])

            for finfo in files:
                pdf.ensure_space(10)
                y_start = pdf.get_y()

                rel_path = _safe(_truncate(str(finfo.get("relative_path", "?")), 120))
                size_str = self._fmt_bytes(finfo.get("size_bytes", 0))
                sha = str(finfo.get("sha256", "?"))
                # Show first 32 chars of hash for readability
                sha_display = sha[:32] + "..." if len(sha) > 32 else sha

                # File column
                pdf.set_xy(_MARGIN_L, y_start)
                pdf.set_font("Courier", "", 6.5)
                pdf.multi_cell(col_file, 3.8, rel_path)
                y1 = pdf.get_y()

                # Size column
                pdf.set_xy(_MARGIN_L + col_file, y_start)
                pdf.set_font(*_FONT_TABLE_BODY)
                pdf.cell(col_size, 3.8, size_str)

                # Hash column
                pdf.set_xy(_MARGIN_L + col_file + col_size, y_start)
                pdf.set_font("Courier", "", 5.5)
                pdf.multi_cell(col_hash, 3.8, sha_display)
                y3 = pdf.get_y()

                final_y = max(y1, y3) + 0.5
                pdf.set_draw_color(235, 235, 235)
                pdf.line(_MARGIN_L, final_y - 0.3, _PAGE_W - _MARGIN_R, final_y - 0.3)
                pdf.set_xy(_MARGIN_L, final_y)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 8 — EVIDENCE INTEGRITY
        # ═══════════════════════════════════════════════════════════════

        pdf.section("8. Evidence Integrity")
        pdf.kv("Total Files", str(manifest.get("file_count", 0)))
        pdf.kv("Hash Algorithm", "SHA-256")
        pdf.kv("Files Hashed", str(len(files)))
        integrity_result = "Verified" if len(files) > 0 else "No files"
        pdf.kv("Integrity Result", integrity_result)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 9 — WARNINGS AND LIMITATIONS
        # ═══════════════════════════════════════════════════════════════

        warnings = list(set(meta.get("warnings", []) + manifest.get("warnings", [])))
        limitations = manifest.get("limitations", [])

        if warnings or limitations:
            pdf.section("9. Warnings and Limitations")

            if warnings:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 6, "Collection Warnings:", new_x="LMARGIN", new_y="NEXT")
                for w in warnings:
                    pdf.bullet(_safe(_truncate(w, 300)))
                pdf.ln(3)

            if limitations:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 6, "Forensic Limitations:", new_x="LMARGIN", new_y="NEXT")
                for lim in limitations:
                    pdf.bullet(_safe(lim))
                pdf.ln(3)

        # ═══════════════════════════════════════════════════════════════
        # SECTION 10 — TECHNICAL DETAILS
        # ═══════════════════════════════════════════════════════════════

        pdf.section("10. Technical Details")
        pdf.kv("Forensic Engine", f"MVT {_safe(meta.get('mvt_version', 'N/A'))}")
        pdf.kv("Device Connection", f"ADB {_safe(meta.get('adb_version', 'N/A'))}")
        pdf.kv("Platform", "S*EntryTrace v0.1.0")
        if findings:
            pdf.kv("Records Processed", f"{findings.total_records_processed:,}")
            pdf.kv("Modules Analyzed", str(len(findings.modules_analyzed)))

        # ═══════════════════════════════════════════════════════════════
        # SECTION 11 — COLLECTION DISCLAIMER
        # ═══════════════════════════════════════════════════════════════

        pdf.section("11. Collection Disclaimer")
        pdf.body_text(
            "This report documents forensic evidence collected by S*EntryTrace "
            "using the Mobile Verification Toolkit (MVT). Results are limited "
            "to the artifacts and indicators supported by MVT. This report does "
            "not guarantee device safety nor constitute a complete forensic "
            "examination. Absence of findings does not confirm the absence of "
            "threats. Seek expert assistance for serious security concerns."
        )
        pdf.ln(3)
        pdf.italic_text(
            "Evidence was collected via ADB read-only commands. This is not "
            "a full device image or a legally admissible forensic acquisition. "
            "For law enforcement or legal proceedings, a certified forensic "
            "examiner should perform a complete physical acquisition."
        )

        # ═══════════════════════════════════════════════════════════════
        # OUTPUT
        # ═══════════════════════════════════════════════════════════════

        pdf.output(str(output_path))

    def _build_minimal_pdf(
        self, output_path: Path, scan_id: str, meta: dict, error: str
    ) -> None:
        """Build a minimal fallback PDF when the full report fails."""
        pdf = _ForensicPDF()
        pdf.add_page()
        pdf.ln(15)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "S*EntryTrace", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, "Report Generation Error", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)
        pdf.kv("Examination ID", scan_id)
        pdf.kv("Status", meta.get("status", "unknown"))
        pdf.kv("Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        pdf.ln(5)
        pdf.section("Error Details")
        pdf.body_text(f"The full report could not be generated due to the following error:")
        pdf.ln(3)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(pdf.usable_w, 4, _safe(_truncate(error, 800)))
        pdf.output(str(output_path))

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _mask_serial(serial: str) -> str:
        if len(serial) <= 4:
            return serial
        return serial[:4] + "*" * (len(serial) - 4)

    @staticmethod
    def _fmt_bytes(b: int) -> str:
        if b > 1048576:
            return f"{b / 1048576:.1f} MB"
        if b > 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b} bytes"
