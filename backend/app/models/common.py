"""S*EntryTrace — Common response models."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Standard API status response."""

    ok: bool
    message: str = ""
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Standard API error response."""

    ok: bool = False
    error: str
    detail: Optional[str] = None
