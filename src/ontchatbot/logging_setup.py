"""Centralised logging configuration for runtime tracing.

A single :func:`configure_logging` call sets up a *rotating* file handler on
the ``ontchatbot`` logger hierarchy plus a parallel console stream. All
modules obtain their logger via ``logging.getLogger(__name__)`` and inherit
this handler set automatically.

The pipeline emits one log record per stage (preprocessing, NER, fuzzy
disambiguation, SPARQL fetch, response composition), which makes it easy to
follow the data shape as a query flows through the system. Each record is
prefixed with a stable stage tag (e.g. ``[recv]``, ``[ner]``, ``[fuzzy]``)
so log files can be filtered with a simple ``grep``.
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
    # ``caplog``, central log aggregators) still see our records. Production
    # duplication is avoided by uvicorn not installing handlers on the root
    # logger.
    logger.propagate = True
    _CONFIGURED = True
    _ACTIVE_LOG_FILE = target
    logger.info("[init] logging started log_file=%s level=%s",
                target, logging.getLevelName(level))
    return target


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor — equivalent to ``logging.getLogger(name)`` but
    guarantees the returned logger sits under the ``ontchatbot`` namespace."""
    if not name.startswith(_PKG_LOGGER):
        name = f"{_PKG_LOGGER}.{name}"
    return logging.getLogger(name)
