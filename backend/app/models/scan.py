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
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_IMPLEMENTED = "not_implemented"


class EngineStatus(BaseModel):
    """Status snapshot of the MVT forensic engine."""

    available: bool = Field(False, description="Whether MVT can be imported")
    version: Optional[str] = Field(None, description="Installed MVT version")
    module_count: int = Field(0, description="Number of Android forensic modules")
    modules_loaded: bool = Field(False, description="Whether modules loaded without error")
    warnings: list[str] = Field(default_factory=list)


class ScanRequest(BaseModel):
    """Placeholder model for a future scan request."""

    device_serial: str
    scan_type: str = Field("bugreport", description="bugreport | androidqf | backup")
    output_dir: Optional[str] = None
    ioc_files: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Placeholder model for a future scan result."""

    scan_id: str
    status: ScanStatus = ScanStatus.NOT_IMPLEMENTED
    device_serial: str
    scan_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    module_results: list[dict[str, Any]] = Field(default_factory=list)
    alert_count: int = 0
    error_message: Optional[str] = None
