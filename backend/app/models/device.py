"""S*EntryTrace — Device and common data models.

Uses Pydantic for validation, serialization, and JSON-schema generation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DeviceState(str, Enum):
    """Possible states of an Android device as seen through ADB."""

    CONNECTED = "connected"
    UNAUTHORIZED = "unauthorized"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class MetadataState(str, Enum):
    """State of device metadata freshness."""
    VERIFIED = "verified"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class DeviceInfo(BaseModel):
    """Metadata for a single Android device.

    Fields use ``None`` to represent values that were never collected.
    Previously valid values are preserved via the metadata cache in
    DeviceManager — they are never overwritten with None due to
    temporary ADB failures.
    """

    serial: str = Field(..., description="ADB device serial number")
    model: Optional[str] = Field(None, description="Device model name")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    android_version: Optional[str] = Field(None, description="Android OS version")
    sdk_level: Optional[str] = Field(None, description="Android SDK / API level")
    security_patch: Optional[str] = Field(
        None, description="Android security patch date"
    )
    build_fingerprint: Optional[str] = Field(None, description="Build fingerprint")
    state: DeviceState = Field(
        DeviceState.UNAVAILABLE, description="Current device state"
    )
    is_rooted: Optional[bool] = Field(
        None,
        description="Root status: True = confirmed rooted, False = not rooted, None = unknown",
    )
    adb_version: Optional[str] = Field(None, description="ADB server version")
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this device was first detected",
    )
    last_verified_at: Optional[datetime] = Field(
        None, description="Timestamp when metadata was last successfully verified"
    )
    metadata_state: MetadataState = Field(
        MetadataState.UNAVAILABLE,
        description="Freshness state of device metadata"
    )

    model_config = {"json_schema_extra": {"example": {
        "serial": "ABCD1234",
        "model": "Pixel 6",
        "manufacturer": "Google",
        "android_version": "14",
        "sdk_level": "34",
        "security_patch": "2024-09-05",
        "build_fingerprint": "google/oriole/oriole:14/AP2A.240905.003",
        "state": "connected",
        "is_rooted": None,
        "adb_version": "37.0.1",
        "detected_at": "2026-09-15T12:00:00",
        "last_verified_at": "2026-09-15T12:00:00",
        "metadata_state": "verified",
    }}}
