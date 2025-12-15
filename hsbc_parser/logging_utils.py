from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


def configure_logging(*, log_file: str | Path = "data/logs/hsbc_parser.log", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("hsbc_parser")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Idempotent: don't add duplicate handlers.
    if getattr(logger, "_hsbc_configured", False):
        return logger

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.setLevel(logger.level)

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logger.level)

    logger.addHandler(stream)
    logger.addHandler(file_handler)
    logger.propagate = False

    logger._hsbc_configured = True  # type: ignore[attr-defined]
    logger.debug("Logging configured (file=%s level=%s)", str(log_path), level.upper())
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    base = logging.getLogger("hsbc_parser")
    return base if not name else base.getChild(name)
