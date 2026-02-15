"""
Structured logging configuration for KonvertIt.

Configures structlog to wrap stdlib logging so that:
- Development: colored, human-readable console output
- Staging/Production: JSON lines for log aggregation

All existing ``logging.getLogger(__name__)`` calls work unchanged —
structlog's ProcessorFormatter is attached to the root logger handler.
"""

import logging
import sys

import structlog

from app.config import AppEnv


def setup_logging(
    app_env: AppEnv,
    log_level: str = "INFO",
    log_format: str = "auto",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        app_env: Current environment (development, staging, production).
        log_level: Root logger level (DEBUG, INFO, WARNING, ERROR).
        log_format: ``"json"``, ``"console"``, or ``"auto"``
                    (auto = console in dev, json otherwise).
    """
    use_json = _should_use_json(app_env, log_format)

    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if use_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog itself (for code that uses structlog.get_logger())
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib root logger — this is the key: all existing
    # logging.getLogger(__name__) calls get structured output via
    # the ProcessorFormatter on the root handler.
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def _should_use_json(app_env: AppEnv, log_format: str) -> bool:
    """Determine whether to use JSON output."""
    if log_format == "json":
        return True
    if log_format == "console":
        return False
    # auto: JSON for staging/production, console for development
    return app_env != AppEnv.DEVELOPMENT
