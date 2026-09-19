"""S*EntryTrace — Application Configuration.

Resolves all project paths relative to the repository root.
Supports environment-variable overrides for deployment flexibility.
Uses pathlib.Path for platform-independent path handling.
"""

import os
import shutil
from pathlib import Path
from typing import Optional


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains mvt-main/)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "mvt-main").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: two levels up from backend/app/config.py
    return Path(__file__).resolve().parent.parent.parent


def _resolve_adb_path(project_root: Path) -> Optional[Path]:
    """Find the ADB executable: local platform-tools first, then PATH."""
    # Platform-specific binary name
    adb_name = "adb.exe" if os.name == "nt" else "adb"

    # 1. Check project-local platform-tools
    local_adb = project_root / "platform-tools" / adb_name
    if local_adb.is_file():
        return local_adb

    # 2. Check PATH
    path_adb = shutil.which("adb")
    if path_adb:
        return Path(path_adb)

    return None


class Settings:
    """Central configuration for S*EntryTrace backend.

    All paths resolve relative to the project root by default.
    Override individual settings via environment variables prefixed with STE_.
    """

    def __init__(self) -> None:
        self.project_root: Path = Path(
            os.environ.get("STE_PROJECT_ROOT", str(_find_project_root()))
        ).resolve()

        self.mvt_source_dir: Path = Path(
            os.environ.get(
                "STE_MVT_SOURCE_DIR",
                str(self.project_root / "mvt-main"),
            )
        ).resolve()

        self.evidence_dir: Path = Path(
            os.environ.get(
                "STE_EVIDENCE_DIR",
                str(self.project_root / "evidence"),
            )
        ).resolve()

        self.reports_dir: Path = Path(
            os.environ.get(
                "STE_REPORTS_DIR",
                str(self.project_root / "reports"),
            )
        ).resolve()

        self.log_dir: Path = Path(
            os.environ.get(
                "STE_LOG_DIR",
                str(self.project_root / "logs"),
            )
        ).resolve()

        # ADB executable — resolved dynamically
        adb_env = os.environ.get("STE_ADB_PATH")
        if adb_env:
            self.adb_path: Optional[Path] = Path(adb_env).resolve()
        else:
            self.adb_path = _resolve_adb_path(self.project_root)

        # Subprocess timeout in seconds
        self.subprocess_timeout: int = int(
            os.environ.get("STE_SUBPROCESS_TIMEOUT", "30")
        )

        # Application environment
        self.environment: str = os.environ.get("STE_ENVIRONMENT", "development")

        # Safe mode — when True, blocks any write operations to device
        self.safe_mode: bool = (
            os.environ.get("STE_SAFE_MODE", "true").lower() in ("true", "1", "yes")
        )

        # Application metadata
        self.app_name: str = "S*EntryTrace"
        self.app_version: str = "0.1.0"

    @property
    def adb_available(self) -> bool:
        """Check whether the ADB executable exists at the configured path."""
        return self.adb_path is not None and self.adb_path.is_file()

    @property
    def mvt_source_available(self) -> bool:
        """Check whether the MVT source directory exists."""
        return self.mvt_source_dir.is_dir()

    def ensure_directories(self) -> None:
        """Create output directories if they don't exist."""
        for directory in (self.evidence_dir, self.reports_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        """Return a safe, serializable snapshot of the settings.

        Does not expose full filesystem paths in production.
        """
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "safe_mode": self.safe_mode,
            "adb_available": self.adb_available,
            "mvt_source_available": self.mvt_source_available,
            "subprocess_timeout": self.subprocess_timeout,
        }


# Singleton instance used across the application
settings = Settings()
