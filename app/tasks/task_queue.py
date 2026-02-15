"""
arq task queue worker configuration.

Uses arq (lightweight async Redis task queue) for MVP.
Migration path to Celery documented for when scaling demands it.
"""

import logging

from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL into arq RedisSettings."""
    settings = get_settings()
    url = settings.redis_url

    # Parse redis://host:port/db format
    # Default: redis://localhost:6379/0
    if url.startswith("redis://"):
        url = url[len("redis://"):]

    parts = url.split("/")
    host_port = parts[0]
    database = int(parts[1]) if len(parts) > 1 else 0

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 6379

    return RedisSettings(host=host, port=port, database=database)


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
    ]

    on_startup = "app.tasks.scrape_tasks.startup"
    on_shutdown = "app.tasks.scrape_tasks.shutdown"
