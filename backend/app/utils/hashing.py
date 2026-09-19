"""S*EntryTrace — SHA-256 hashing utilities."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_directory(directory: Path) -> list[dict]:
    """Hash every file in a directory tree.

    Returns a list of dicts with relative_path, size_bytes, sha256, and timestamp.
    """
    results = []
    if not directory.is_dir():
        return results

    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            fpath = Path(root) / fname
            try:
                stat = fpath.stat()
                results.append({
                    "relative_path": str(fpath.relative_to(directory)),
                    "size_bytes": stat.st_size,
                    "sha256": sha256_file(fpath),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })
            except (OSError, PermissionError):
                results.append({
                    "relative_path": str(fpath.relative_to(directory)),
                    "size_bytes": 0,
                    "sha256": "ERROR",
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })
    return results
