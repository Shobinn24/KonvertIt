"""
arq task queue worker configuration.

Uses arq (lightweight async Redis task queue) for MVP.
Migration path to Celery documented for when scaling demands it.
"""

import logging
from urllib.parse import urlparse

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.tasks.scrape_tasks import shutdown, startup

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL into arq RedisSettings."""
    settings = get_settings()
    parsed = urlparse(settings.redis_url)

    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    password = parsed.password or None
    database = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0

    return RedisSettings(host=host, port=port, database=database, password=password)


class WorkerSettings:
    """arq worker configuration — defines available background tasks."""

    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 300  # 5 minutes max per job

    # Register task functions
    functions = [
        "app.tasks.scrape_tasks.scrape_product_task",
        "app.tasks.scrape_tasks.convert_product_task",
        "app.tasks.scrape_tasks.bulk_convert_task",
        "app.tasks.monitor_tasks.monitor_prices_task",
        "app.tasks.discovery_tasks.auto_discover_task",
    ]

    # Scheduled cron jobs — auto-discovery runs once daily at 02:00 UTC
    cron_jobs = [
        cron(
            "app.tasks.discovery_tasks.auto_discover_task",
            hour=2,
            minute=0,
            timeout=600,  # 10 min max for full sweep
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown
