"""
Gunicorn configuration for KonvertIt production deployment.

Uses Uvicorn workers for async ASGI support. Tuned for a 2-CPU / 2GB
container (typical Railway / Render / Docker deployment).
"""

import multiprocessing
import os

# ─── Server Socket ───────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', os.getenv('APP_PORT', '8000'))}"

# ─── Worker Processes ────────────────────────────────────────
# Uvicorn worker class for ASGI/async support
worker_class = "uvicorn.workers.UvicornWorker"

# Workers = (2 × CPU cores) + 1 — capped at 4 for memory safety
workers = min(multiprocessing.cpu_count() * 2 + 1, int(os.getenv("WEB_CONCURRENCY", "4")))

# Threads per worker (1 for async workers — concurrency is via asyncio)
threads = 1

# ─── Timeouts ────────────────────────────────────────────────
# Request timeout: scraping operations can take up to 60s
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Graceful shutdown timeout
graceful_timeout = 30

# Time to wait for requests on a Keep-Alive connection
keepalive = 5

# ─── Worker Lifecycle ────────────────────────────────────────
# Restart workers after this many requests (prevents memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))

# Jitter to avoid all workers restarting simultaneously
max_requests_jitter = 50

# Preload app to save memory via copy-on-write
preload_app = False  # Disabled — async engines don't fork well

# ─── Logging ─────────────────────────────────────────────────
# Let structlog handle formatting — Gunicorn just forwards to stdout
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Disable default access log format — structlog LoggingMiddleware handles it
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s "%(f)s" %(D)sμs'

# ─── Server Mechanics ────────────────────────────────────────
# Forward proxy headers (X-Forwarded-For, X-Forwarded-Proto)
forwarded_allow_ips = "*"

# Reuse port for zero-downtime restarts
reuse_port = True

# Tmp directory for worker heartbeat files
tmp_upload_dir = "/app/tmp"
