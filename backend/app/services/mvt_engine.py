"""S*EntryTrace — MVT Engine Wrapper.

Provides a safe interface to the upstream MVT forensic engine without
modifying its source.  MVT is treated as an external library: we
import its public classes and inspect their capabilities.
"""

import logging
from typing import Optional

from backend.app.models.scan import EngineStatus, ScanRequest, ScanResult, ScanStatus

log = logging.getLogger("ste.mvt_engine")


class MVTEngine:
    """Read-only wrapper around the MVT forensic engine.

    All interactions go through MVT's public Python API.  No MVT source
    files are modified.  Scan execution is deliberately **not**
    implemented in Day 2 — only engine introspection is available.
    """

    def __init__(self) -> None:
        self._version: Optional[str] = None
        self._modules: dict[str, list[str]] = {}
        self._available: bool = False
        self._warnings: list[str] = []
        self._init_engine()

    # ── Public API ─────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return whether MVT can be imported and version read."""
        return self._available

    def get_version(self) -> Optional[str]:
        """Return the installed MVT version string."""
        return self._version

    def get_engine_status(self) -> EngineStatus:
        """Return a full status snapshot of the engine."""
        total = sum(len(mods) for mods in self._modules.values())
        return EngineStatus(
            available=self._available,
            version=self._version,
            module_count=total,
            modules_loaded=total > 0,
            warnings=list(self._warnings),
        )

    def get_module_categories(self) -> dict[str, list[str]]:
        """Return module names grouped by category."""
        return dict(self._modules)

    def validate_module(self, module_name: str) -> bool:
        """Check whether a named module exists in MVT's registry."""
        all_names = [
            name for names in self._modules.values() for name in names
        ]
        return module_name in all_names

    def prepare_scan_request(self, request: ScanRequest) -> ScanResult:
        """Validate a scan request and return a placeholder result.

        This does NOT execute a scan.  It verifies that the request
        parameters are structurally valid and returns a NOT_IMPLEMENTED
        result to signal that scan execution is a Day 3+ feature.
        """
        log.info(
            "Scan request validated (not executed): device=%s type=%s",
            request.device_serial,
            request.scan_type,
        )

        valid_types = {"bugreport", "androidqf", "backup", "intrusion_logs"}
        if request.scan_type not in valid_types:
            return ScanResult(
                scan_id="N/A",
                status=ScanStatus.FAILED,
                device_serial=request.device_serial,
                scan_type=request.scan_type,
                error_message=f"Unknown scan type: {request.scan_type!r}. "
                              f"Valid types: {sorted(valid_types)}",
            )

        return ScanResult(
            scan_id="pending",
            status=ScanStatus.NOT_IMPLEMENTED,
            device_serial=request.device_serial,
            scan_type=request.scan_type,
            error_message="Scan execution is not yet implemented (Day 3+).",
        )

    # ── Internal ───────────────────────────────────────────────────────

    def _init_engine(self) -> None:
        """Attempt to import MVT and catalog available modules."""
        # 1. Version
        try:
            from mvt.common.version import MVT_VERSION
            self._version = MVT_VERSION
        except Exception as exc:
            self._warnings.append(f"Cannot read MVT version: {exc}")
            self._available = False
            return

        # 2. Android forensic modules
        try:
            from mvt.android.modules.bugreport import BUGREPORT_MODULES
            self._modules["bugreport"] = [
                m.__name__ for m in BUGREPORT_MODULES
            ]
        except Exception as exc:
            self._warnings.append(f"Bugreport modules failed: {exc}")

        try:
            from mvt.android.modules.androidqf import ANDROIDQF_MODULES
            self._modules["androidqf"] = [
                m.__name__ for m in ANDROIDQF_MODULES
            ]
        except Exception as exc:
            self._warnings.append(f"AndroidQF modules failed: {exc}")

        try:
            from mvt.android.modules.backup import BACKUP_MODULES
            self._modules["backup"] = [m.__name__ for m in BACKUP_MODULES]
        except Exception as exc:
            self._warnings.append(f"Backup modules failed: {exc}")

        try:
            from mvt.android.modules.intrusion_logs import INTRUSION_LOGS_MODULES
            self._modules["intrusion_logs"] = [
                m.__name__ for m in INTRUSION_LOGS_MODULES
            ]
        except Exception as exc:
            self._warnings.append(f"Intrusion logs modules failed: {exc}")

        # 3. Verify command classes are importable
        try:
            from mvt.android.cmd_check_bugreport import CmdAndroidCheckBugreport  # noqa: F401
            from mvt.android.cmd_check_androidqf import CmdAndroidCheckAndroidQF  # noqa: F401
            from mvt.common.command import Command  # noqa: F401
        except Exception as exc:
            self._warnings.append(f"Command classes not importable: {exc}")

        self._available = True
        total = sum(len(m) for m in self._modules.values())
        log.info("MVT engine initialized: v%s, %d modules", self._version, total)
