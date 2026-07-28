"""Shared structured logging configuration.

Uses structlog with a stdlib bridge so that:
- New code calls `get_logger(__name__).info(...)` and gets structured output.
- Existing `logging.getLogger(...)` calls are also formatted by structlog.
- In local development / tests logs are rendered as human-readable console lines
  via `print()`, so pytest's `capsys` continues to capture CLI output.
- In production (STRUCTLOG_JSON=true) logs are emitted as compact JSON for
  Loki/Datadog/CloudWatch parsing.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog


def is_production_json() -> bool:
    """Return True when the caller explicitly requested JSON log output."""
    if os.getenv("STRUCTLOG_JSON", "").lower() in ("1", "true", "yes"):
        return True
    return False


def configure() -> None:
    """Configure structlog and the stdlib logging bridge once per process.

    Safe to call multiple times; idempotent because structlog ignores redundant
    configuration once processors are set.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if is_production_json():
        # add_logger_name only works with stdlib-backed loggers.
        shared_processors.append(structlog.stdlib.add_logger_name)
        shared_processors.append(structlog.stdlib.ExtraAdder())

    if is_production_json():
        # Production: JSON lines via stdlib logging so log shippers can parse them.
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        logger_factory = structlog.stdlib.LoggerFactory()
        wrapper_class = structlog.stdlib.BoundLogger

        # Bridge existing stdlib loggers through structlog formatters.
        root = logging.getLogger()
        root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        if not root.handlers:
            root.addHandler(logging.StreamHandler(sys.stdout))
        for handler in root.handlers:
            handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        # Local / tests: human-readable lines via print() so capsys still works.
        renderer = structlog.dev.ConsoleRenderer()
        logger_factory = structlog.PrintLoggerFactory()
        wrapper_class = structlog.make_filtering_bound_logger(
            getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())
        )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=wrapper_class,
        context_class=dict,
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )

    # Keep third-party noise low by default.
    for noisy in ("urllib3", "httpx", "httpcore", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structured logger for the given module name.

    Example:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("task_finished", rows=42)
    """
    configure()
    return structlog.get_logger(name)
