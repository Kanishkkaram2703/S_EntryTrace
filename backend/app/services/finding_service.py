"""S*EntryTrace — Finding parser service.

Parses MVT JSON output files into structured Finding objects.
Never fabricates findings — only reports what MVT actually produced.
"""

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from backend.app.models.finding import (
    AnalysisModule, Finding, FindingCategory, FindingConfidence,
    FindingSeverity, FindingSummary,
)

log = logging.getLogger("ste.findings")

# Maps MVT module names to human-readable display names
_MODULE_DISPLAY_NAMES: dict[str, str] = {
    "dumpsys_accessibility": "Accessibility Services",
    "dumpsys_activities": "Application Activities",
    "dumpsys_appops": "Application Permissions",
    "dumpsys_battery_daily": "Battery & App Usage",
    "dumpsys_battery_history": "Battery History",
    "dumpsys_dbinfo": "Database Connections",
    "dumpsys_getprop": "System Properties",
    "dumpsys_packages": "Installed Packages",
    "dumpsys_platform_compat": "Platform Compatibility",
    "dumpsys_receivers": "Broadcast Receivers",
    "dumpsys_adb_state": "ADB Trusted Keys",
    "bugreport_timestamps": "Filesystem Timestamps",
    "tombstones": "Crash Reports",
    "processes": "Running Processes",
    "settings": "System Settings",
    "mounts": "Filesystem Mounts",
}

# Human-readable explanations for common MVT alert patterns
_ALERT_EXPLANATIONS: dict[str, dict[str, str]] = {
    "accessibility": {
        "why": "Accessibility services can read screen content, intercept input, and control the device. While many legitimate apps use this feature, it is also commonly abused by spyware.",
        "interpretation": "This is a security observation. Verify that you intentionally installed and enabled this accessibility service.",
    },
    "location_permission": {
        "why": "Location permissions allow an application to track the device's physical position. Risky system packages with location access may indicate unusual configuration.",
        "interpretation": "Review whether this system package requires location access for its intended function.",
    },
    "install_packages": {
        "why": "The REQUEST_INSTALL_PACKAGES permission allows an application to install other applications. This can be used to sideload software without the user's explicit knowledge.",
        "interpretation": "Verify that this application is trusted and that the permission was granted intentionally.",
    },
    "package_uninstall": {
        "why": "Package uninstall events may indicate that an application was removed to cover tracks, or may be routine cleanup by the system.",
        "interpretation": "Review whether the uninstalled package was known to you. Uninstalls of unknown packages may warrant further investigation.",
    },
    "accessibility_enabled": {
        "why": "When accessibility services are enabled system-wide, any registered accessibility service can monitor device activity. This is normal if you use screen readers or keyboard apps with accessibility features.",
        "interpretation": "Confirm that all registered accessibility services are applications you trust.",
    },
    "suspicious_mount": {
        "why": "Unusual mount options on system partitions may indicate filesystem modifications. However, some manufacturers use non-standard mount configurations.",
        "interpretation": "This may be normal for this device manufacturer. Compare with known baselines for this device model if available.",
    },
    "telephony_receiver": {
        "why": "Applications monitoring telephony state can detect incoming and outgoing calls. While messaging and calling apps legitimately need this, it can also be used for surveillance.",
        "interpretation": "Verify that this application is known to you and has a legitimate reason to monitor call state.",
    },
    "sms_receiver": {
        "why": "Applications intercepting SMS messages can read verification codes, personal messages, and other sensitive communications.",
        "interpretation": "Verify that this application is known to you and has a legitimate reason to intercept SMS.",
    },
}


class FindingService:
    """Parse MVT output and produce structured findings."""

    def parse_scan_findings(self, scan_id: str, findings_dir: Path) -> FindingSummary:
        """Parse all result files from an MVT scan.

        Reads alerts.json (MVT's primary alert output) and per-module
        JSON files to build a complete picture of what was analyzed and
        what was found.
        """
        findings: list[Finding] = []
        modules: list[AnalysisModule] = []
        total_records = 0
        ioc_configured = False
        ioc_count = 0

        if not findings_dir.is_dir():
            log.info("No findings directory for scan %s", scan_id)
            return FindingSummary(scan_id=scan_id)

        # Step 1: Parse alerts.json — MVT's primary alert output
        alerts_path = findings_dir / "alerts.json"
        if alerts_path.is_file():
            try:
                alerts = json.loads(alerts_path.read_text(encoding="utf-8"))
                if isinstance(alerts, list):
                    for i, alert in enumerate(alerts):
                        finding = self._alert_to_finding(scan_id, alert, i, alerts_path)
                        if finding:
                            findings.append(finding)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Cannot parse alerts.json: %s", exc)

        # Step 2: Parse per-module files for analysis summary
        for json_file in sorted(findings_dir.glob("*.json")):
            stem = json_file.stem
            if stem in ("alerts", "alerts_timeline", "info", "command"):
                continue  # Skip non-module files

            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    continue

                record_count = len(data)
                total_records += record_count

                # Check for _detected files (MVT's per-module alert output)
                is_detected = stem.endswith("_detected")
                base_module = stem.replace("_detected", "") if is_detected else stem
                display = _MODULE_DISPLAY_NAMES.get(base_module, base_module.replace("_", " ").title())

                if not is_detected:
                    modules.append(AnalysisModule(
                        module_name=base_module,
                        display_name=display,
                        records_processed=record_count,
                        alerts_generated=0,
                        status="completed",
                        summary=f"Processed {record_count:,} records",
                    ))

            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Cannot parse %s: %s", json_file.name, exc)

        # Step 3: Check info.json for IOC configuration
        info_path = findings_dir / "info.json"
        if info_path.is_file():
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
                ioc_count = info.get("indicators_count", 0) or 0
                ioc_configured = ioc_count > 0
            except (json.JSONDecodeError, OSError):
                pass

        # Step 4: Update module alert counts from findings
        module_alert_counts: dict[str, int] = {}
        for f in findings:
            mod = f.source_module
            module_alert_counts[mod] = module_alert_counts.get(mod, 0) + 1
        for m in modules:
            m.alerts_generated = module_alert_counts.get(m.module_name, 0)

        # Build summary
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for f in findings:
            by_category[f.category.value] = by_category.get(f.category.value, 0) + 1
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

        return FindingSummary(
            scan_id=scan_id,
            total=len(findings),
            by_category=by_category,
            by_severity=by_severity,
            findings=findings,
            modules_analyzed=modules,
            ioc_configured=ioc_configured,
            ioc_indicators_loaded=ioc_count,
            total_records_processed=total_records,
        )

    def _alert_to_finding(
        self, scan_id: str, alert: dict, index: int, source_file: Path,
    ) -> Optional[Finding]:
        """Convert an MVT alert record into a Finding.

        MVT alerts have: level, module, message, event_time, event, matched_indicator
        """
        if not isinstance(alert, dict):
            return None

        level = alert.get("level", "")
        module = alert.get("module", "")
        message = alert.get("message", "")
        event_time = alert.get("event_time", "")
        event = alert.get("event", {})
        matched_indicator = alert.get("matched_indicator")

        finding_id = f"alert-{module}-{index}-{uuid.uuid4().hex[:6]}"

        # Determine category and severity
        if matched_indicator:
            category = FindingCategory.IOC_MATCH
            severity = FindingSeverity.HIGH
            confidence = FindingConfidence.HIGH
            title = f"Threat indicator match in {_MODULE_DISPLAY_NAMES.get(module, module)}"
            explanation = f"A known threat indicator was matched: {matched_indicator}"
            why = "Matched indicators suggest the device may have been targeted by known surveillance tools."
            interpretation = "This is a confirmed indicator match. Seek expert assistance for further analysis."
        else:
            category, severity, confidence = self._classify_alert(level, module, message, event)
            title = self._generate_title(module, message, event)
            explanation = self._generate_explanation(message, event)
            why, interpretation = self._get_context(module, message, event)

        return Finding(
            finding_id=finding_id,
            scan_id=scan_id,
            category=category,
            title=title,
            description=message,
            severity=severity,
            confidence=confidence,
            source_module=module,
            evidence_path=str(source_file),
            indicator_value=str(matched_indicator) if matched_indicator else None,
            mvt_level=level,
            mvt_message=message,
            event_time=event_time if event_time else None,
            event_data=event if isinstance(event, dict) else None,
            explanation=explanation,
            why_it_matters=why,
            interpretation=interpretation,
        )

    def _classify_alert(
        self, level: str, module: str, message: str, event: dict
    ) -> tuple[FindingCategory, FindingSeverity, FindingConfidence]:
        """Classify a non-IOC MVT alert into category/severity/confidence."""

        # Map MVT levels
        severity_map = {
            "CRITICAL": FindingSeverity.CRITICAL,
            "HIGH": FindingSeverity.HIGH,
            "MEDIUM": FindingSeverity.MEDIUM,
            "LOW": FindingSeverity.LOW,
            "INFORMATIONAL": FindingSeverity.INFO,
        }
        severity = severity_map.get(level, FindingSeverity.UNKNOWN)

        # Determine category based on module and message content
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("risky package", "risky permission", "suspicious")):
            category = FindingCategory.SUSPICIOUS
            confidence = FindingConfidence.MEDIUM
        elif "accessibility" in msg_lower:
            category = FindingCategory.INFORMATIONAL
            confidence = FindingConfidence.HIGH
        elif "uninstall" in msg_lower:
            category = FindingCategory.INFORMATIONAL
            confidence = FindingConfidence.HIGH
        elif "mount" in msg_lower:
            category = FindingCategory.INFORMATIONAL
            confidence = FindingConfidence.MEDIUM
        else:
            category = FindingCategory.INFORMATIONAL
            confidence = FindingConfidence.MEDIUM

        return category, severity, confidence

    def _generate_title(self, module: str, message: str, event: dict) -> str:
        """Generate a human-readable finding title."""
        pkg = event.get("package_name", "")

        if "accessibility" in module and "service" in message.lower():
            component = event.get("component", "")
            svc = component.split("/")[-1] if "/" in component else component
            return f"Accessibility service detected: {pkg or svc}"

        if module == "dumpsys_appops":
            perms = event.get("permissions", [])
            perm_name = perms[0].get("name", "") if perms else ""
            if "risky package" in message.lower():
                return f"Risky permission on system package: {pkg} ({perm_name})"
            if "risky permission" in message.lower() or perm_name:
                return f"Sensitive permission access: {pkg} ({perm_name})"

        if "uninstall" in message.lower():
            return f"Package uninstall detected: {pkg}"

        if module == "settings" and "accessibility_enabled" in message:
            return "Accessibility services enabled system-wide"

        if module == "mounts" and "suspicious" in message.lower():
            mount_point = event.get("mount_point", "")
            return f"Unusual mount configuration: {mount_point}"

        # Fallback
        display = _MODULE_DISPLAY_NAMES.get(module, module)
        return f"Alert from {display}"

    def _generate_explanation(self, message: str, event: dict) -> str:
        """Generate a human-readable explanation of what was observed."""
        pkg = event.get("package_name", "")

        if "accessibility" in message.lower() and "service" in message.lower():
            component = event.get("component", "")
            enabled = event.get("enabled", False)
            status = "enabled and active" if enabled else "registered but not currently active"
            return f"The application '{pkg}' has an accessibility service that is {status}."

        if event.get("permissions"):
            perms = event["permissions"]
            perm_name = perms[0].get("name", "") if perms else ""
            entries = perms[0].get("entries", []) if perms else []
            if entries:
                last_entry = entries[0]
                ts = last_entry.get("timestamp", "")
                access = last_entry.get("access", "")
                return f"The package '{pkg}' had permission '{perm_name}' with status '{access}' at {ts}."
            return f"The package '{pkg}' has the '{perm_name}' permission configured."

        if "uninstall" in message.lower():
            period_start = event.get("period_start", "")
            occurrences = event.get("occurrences", 0)
            return f"The package '{pkg}' was uninstalled (detected {occurrences} time(s), first observed {period_start})."

        return message

    def _get_context(self, module: str, message: str, event: dict) -> tuple[str, str]:
        """Get 'why it matters' and 'interpretation' for an alert."""
        msg_lower = message.lower()

        if "accessibility" in module and "service" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["accessibility"]
            return ctx["why"], ctx["interpretation"]

        if "location" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["location_permission"]
            return ctx["why"], ctx["interpretation"]

        if "install_packages" in msg_lower or "request_install" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["install_packages"]
            return ctx["why"], ctx["interpretation"]

        if "uninstall" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["package_uninstall"]
            return ctx["why"], ctx["interpretation"]

        if "accessibility_enabled" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["accessibility_enabled"]
            return ctx["why"], ctx["interpretation"]

        if "mount" in module and "suspicious" in msg_lower:
            ctx = _ALERT_EXPLANATIONS["suspicious_mount"]
            return ctx["why"], ctx["interpretation"]

        return (
            "This observation was flagged by the forensic analysis engine for manual review.",
            "Review the details and determine whether this is expected behavior for your device.",
        )
