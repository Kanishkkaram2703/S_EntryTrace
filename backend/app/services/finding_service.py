"""S*EntryTrace — Finding parser service.

Parses MVT JSON output files into structured Finding objects.
Never fabricates findings — only reports what MVT actually produced.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from backend.app.models.finding import (
    Finding, FindingCategory, FindingConfidence,
    FindingSeverity, FindingSummary,
)

log = logging.getLogger("ste.findings")


class FindingService:
    """Parse MVT output and produce structured findings."""

    def parse_scan_findings(self, scan_id: str, findings_dir: Path) -> FindingSummary:
        """Parse all JSON result files from an MVT scan.

        MVT writes one JSON file per module (e.g. dumpsys_packages.json).
        Each file contains a list of result dicts.  We inspect the results
        and classify them honestly.
        """
        findings: list[Finding] = []

        if not findings_dir.is_dir():
            log.info("No findings directory for scan %s", scan_id)
            return FindingSummary(scan_id=scan_id)

        for json_file in sorted(findings_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    continue
                module_name = json_file.stem
                for i, record in enumerate(data):
                    finding = self._record_to_finding(
                        scan_id, module_name, record, json_file, i
                    )
                    if finding:
                        findings.append(finding)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Cannot parse %s: %s", json_file.name, exc)
                findings.append(Finding(
                    finding_id=f"warn-{uuid.uuid4().hex[:8]}",
                    scan_id=scan_id,
                    category=FindingCategory.COLLECTION_WARNING,
                    title=f"Failed to parse {json_file.name}",
                    description=str(exc),
                    severity=FindingSeverity.INFO,
                    source_module=json_file.stem,
                ))

        # Build summary
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for f in findings:
            by_category[f.category.value] = by_category.get(f.category.value, 0) + 1
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

        return FindingSummary(
            scan_id=scan_id,
            total=len(findings),
            by_category=by_category,
            by_severity=by_severity,
            findings=findings,
        )

    def _record_to_finding(
        self, scan_id: str, module: str, record: dict,
        source_file: Path, index: int,
    ) -> Optional[Finding]:
        """Convert a single MVT result record into a Finding.

        MVT modules output different schemas.  We look for common
        patterns: matched_indicator, suspicious fields, etc.
        """
        if not isinstance(record, dict):
            return None

        finding_id = f"{module}-{index}-{uuid.uuid4().hex[:6]}"

        # Check if MVT flagged this with a matched indicator
        matched = record.get("matched_indicator")
        if matched:
            return Finding(
                finding_id=finding_id,
                scan_id=scan_id,
                category=FindingCategory.IOC_MATCH,
                title=f"IOC match in {module}",
                description=str(matched),
                severity=FindingSeverity.HIGH,
                confidence=FindingConfidence.HIGH,
                source_module=module,
                evidence_path=str(source_file),
                indicator_value=str(matched) if matched else None,
            )

        # For informational records (most MVT output), we only record
        # a finding if there is something noteworthy.  We do NOT create
        # findings for every single record — that would flood the user.
        # We skip ordinary records silently.
        return None
