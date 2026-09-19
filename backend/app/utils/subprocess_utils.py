"""S*EntryTrace — Safe subprocess utilities."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("ste.subprocess")


class SubprocessResult:
    """Wrapper for a completed subprocess."""
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.ok = returncode == 0


def run_safe(
    args: list[str],
    timeout: int = 300,
    cwd: Optional[Path] = None,
) -> SubprocessResult:
    """Run a subprocess with safety constraints.

    - Never uses shell=True
    - Enforces timeout
    - Captures all output
    - Returns structured result
    """
    log.debug("Subprocess: %s", " ".join(args))
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            cwd=str(cwd) if cwd else None,
        )
        return SubprocessResult(result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return SubprocessResult(-1, "", f"Command timed out after {timeout}s")
    except FileNotFoundError:
        return SubprocessResult(-1, "", f"Executable not found: {args[0]}")
    except OSError as exc:
        return SubprocessResult(-1, "", f"OS error: {exc}")
