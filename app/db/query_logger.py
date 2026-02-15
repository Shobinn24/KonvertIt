"""
Slow query detection via SQLAlchemy engine events.

Hooks into before_cursor_execute / after_cursor_execute to measure
query wall-clock time. Queries exceeding the configured threshold
are logged as warnings with the SQL statement and duration.

Usage:
    from app.db.query_logger import attach_query_logger
    attach_query_logger(engine)
"""

import logging
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings

logger = logging.getLogger(__name__)


def attach_query_logger(engine: AsyncEngine) -> None:
    """
    Attach before/after cursor execute events to the sync engine
    underlying the async engine.

    Args:
        engine: The async SQLAlchemy engine to instrument.
    """
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("query_start_time")
        if not start_times:
            return
        start = start_times.pop()
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        settings = get_settings()
        if elapsed_ms >= settings.query_slow_threshold_ms:
            # Truncate long statements for readability
            stmt_preview = statement[:500] if len(statement) > 500 else statement
            logger.warning(
                "slow_query_detected",
                extra={
                    "duration_ms": round(elapsed_ms, 2),
                    "threshold_ms": settings.query_slow_threshold_ms,
                    "statement": stmt_preview,
                },
            )
