"""S*EntryTrace — Scan and engine data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ScanStatus(str, Enum):
    """Lifecycle status of a forensic scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_IMPLEMENTED = "not_implemented"


class StageStatus(str, Enum):
    """Status of an individual scan stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_AVAILABLE = "not_available"


class ScanStage(BaseModel):
    """A single stage in the scan pipeline."""
    stage_id: str
    display_name: str
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    summary: str = ""
    error: Optional[str] = None
    records_processed: int = 0


class EngineStatus(BaseModel):
    """Status snapshot of the MVT forensic engine."""

    available: bool = Field(False, description="Whether MVT can be imported")
    version: Optional[str] = Field(None, description="Installed MVT version")
    module_count: int = Field(0, description="Number of Android forensic modules")
    modules_loaded: bool = Field(False, description="Whether modules loaded without error")
    warnings: list[str] = Field(default_factory=list)


class ScanRequest(BaseModel):
    """Model for a scan request."""

    device_serial: str
    scan_type: str = Field("bugreport", description="bugreport | androidqf | backup")
    output_dir: Optional[str] = None
    ioc_files: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Model for a scan result."""

    scan_id: str
    status: ScanStatus = ScanStatus.NOT_IMPLEMENTED
    device_serial: str
    scan_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: list[ScanStage] = Field(default_factory=list)
    module_results: list[dict[str, Any]] = Field(default_factory=list)
    alert_count: int = 0
    error_message: Optional[str] = None
