import json
import logging
import os
import sys
from datetime import UTC, datetime


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configure task scheduler logs as one JSON object per stderr line."""
    logger = logging.getLogger("task_scheduler")
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    log_file = os.getenv("TASK_SCHEDULER_LOG_FILE", "scheduler.log")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(file_handler)


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        **fields,
    }
    logger.log(level, json.dumps(payload, default=str, ensure_ascii=False))
