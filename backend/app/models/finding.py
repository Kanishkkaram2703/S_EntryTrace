"""S*EntryTrace — Finding data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FindingCategory(str, Enum):
    """Honest finding categories — no exaggerated claims."""
    IOC_MATCH = "Confirmed IOC Match"
    SUSPICIOUS = "Suspicious Observation"
    INFORMATIONAL = "Informational"
    NOT_ASSESSED = "Not Assessed"
    COLLECTION_WARNING = "Collection Warning"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class FindingConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Finding(BaseModel):
    """A single forensic finding from an MVT scan."""
    finding_id: str
    scan_id: str
    category: FindingCategory = FindingCategory.NOT_ASSESSED
    title: str
    description: str = ""
    severity: FindingSeverity = FindingSeverity.UNKNOWN
    confidence: FindingConfidence = FindingConfidence.UNKNOWN
    source_module: str = ""
    evidence_path: Optional[str] = None
    indicator_value: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "new"

    # MVT-specific fields
    mvt_level: Optional[str] = None  # MEDIUM, HIGH, CRITICAL etc.
    mvt_message: Optional[str] = None
    event_time: Optional[str] = None
    event_data: Optional[dict[str, Any]] = None

    # Human-readable explanation
    explanation: str = ""
    why_it_matters: str = ""
    interpretation: str = ""


class AnalysisModule(BaseModel):
    """Summary of what a single MVT module analyzed."""
    module_name: str
    display_name: str
    records_processed: int = 0
    alerts_generated: int = 0
    status: str = "completed"
    summary: str = ""


class FindingSummary(BaseModel):
    """Aggregated findings overview for a scan."""
    scan_id: str
    total: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    modules_analyzed: list[AnalysisModule] = Field(default_factory=list)
    ioc_configured: bool = False
    ioc_indicators_loaded: int = 0
    total_records_processed: int = 0
