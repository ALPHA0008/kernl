"""Structured (JSON-lines) logging for the /v1 decision path.

Every log line is one JSON object on stdout: {"ts", "level", "event", ...fields}.
This is the audit-adjacent trail the arc calls for — tenant + decision + bundle
IDs on every ruling — separate from the ledger (which is the system of record;
these logs are operational, not authoritative, and never gate a decision).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

_LOGGER_NAME = "kernl.v1"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str, separators=(",", ":"))


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(event: str, **fields: Any) -> None:
    """One structured line. Always include tenant/decision/bundle identifiers
    when the caller has them -- that's the whole point of this module."""
    get_logger().info(event, extra={"fields": fields})
