"""S*EntryTrace — Logging Configuration."""

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the application logger.

    Returns the root 'ste' logger so callers can use
    ``logging.getLogger("ste.submodule")`` for scoped output.
    """
    log = logging.getLogger("ste")
    if log.handlers:
        return log  # already configured

    log.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)
    return log
