"""Rotating file handler + console handler for the ``ontchatbot`` logger.

Each module gets its own logger via ``getLogger(__name__)`` so per-module
levels can be tuned independently.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LOG_FILE

_FMT = "%(asctime)s | %(levelname)-7s | %(name)-34s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_PKG_LOGGER = "ontchatbot"
_CONFIGURED = False
_ACTIVE_LOG_FILE: Path | None = None


def configure_logging(
    log_file: Path | None = None,
    level: int = logging.INFO,
    *,
    console: bool = True,
    max_bytes: int = 5_000_000,
    backups: int = 5,
) -> Path:
    """Install a rotating file handler (and optional console handler).

    Idempotent: subsequent calls return the active log path without
    duplicating handlers.
    """
    global _CONFIGURED, _ACTIVE_LOG_FILE
    if _CONFIGURED and _ACTIVE_LOG_FILE is not None:
        return _ACTIVE_LOG_FILE

    target = Path(log_file) if log_file else LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_PKG_LOGGER)

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    fh = RotatingFileHandler(
        target, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    logger.setLevel(level)
    # Keep propagation enabled so external capture mechanisms (pytest's
    # ``caplog``, central log aggregators) still see our records.
    logger.propagate = True
    _CONFIGURED = True
    _ACTIVE_LOG_FILE = target
    logger.info("[init] logging started log_file=%s level=%s",
                target, logging.getLevelName(level))
    return target
