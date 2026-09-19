"""S*EntryTrace — Report data models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    """Metadata for a forensic audit report."""
    report_id: str
    scan_id: str
    device_serial: str
    device_model: Optional[str] = None
    mvt_version: Optional[str] = None
    adb_version: Optional[str] = None
    scan_profile: str = ""
    collection_start: Optional[datetime] = None
    collection_end: Optional[datetime] = None
    collection_status: str = ""
    evidence_file_count: int = 0
    total_evidence_bytes: int = 0
    finding_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This report documents forensic evidence collected by S*EntryTrace "
        "using the Mobile Verification Toolkit (MVT). Results are limited "
        "to the artifacts and indicators supported by MVT. This report does "
        "not guarantee device safety nor constitute a complete forensic "
        "examination. MVT coverage is limited to supported artifacts and "
        "publicly available indicators of compromise."
    )
