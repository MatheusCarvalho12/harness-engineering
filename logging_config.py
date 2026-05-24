"""Structured JSON logging shared by the API and every agent worker.

A single line per event keeps logs grep-able and lets the demo pipe them
straight into any log aggregator without a parsing step.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "context", {}).items():
            log_entry[key] = value
        return json.dumps(log_entry)


def get_logger(component_name: str) -> logging.Logger:
    logger = logging.getLogger(component_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, message: str, **context) -> None:
    logger.info(message, extra={"context": context})


def log_error(
    logger: logging.Logger, message: str, exc: Exception | None = None, **context
) -> None:
    logger.error(message, exc_info=exc, extra={"context": context})
