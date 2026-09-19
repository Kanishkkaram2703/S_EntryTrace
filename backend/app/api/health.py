"""S*EntryTrace — Health check endpoint."""

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.services.adb_client import AdbClient, AdbError
from backend.app.services.mvt_engine import MVTEngine

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return application health including MVT and ADB status."""
    # ADB status
    adb = AdbClient()
    adb_available = adb.is_available()
    adb_version = None
    if adb_available:
        try:
            adb_version = adb.get_version()
        except AdbError:
            pass

    # MVT status
    engine = MVTEngine()
    mvt_status = engine.get_engine_status()

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "status": "ok",
        "mvt": {
            "available": mvt_status.available,
            "version": mvt_status.version,
            "module_count": mvt_status.module_count,
        },
        "adb": {
            "available": adb_available,
            "version": adb_version,
        },
    }
