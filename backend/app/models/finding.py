"""S*EntryTrace — Finding data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FindingCategory(str, Enum):
    """Honest finding categories — no exaggerated claims."""
    IOC_MATCH = "Confirmed IOC Match"
    SUSPICIOUS = "Suspicious Heuristic"
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


class FindingSummary(BaseModel):
    """Aggregated findings overview for a scan."""
    scan_id: str
    total: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
