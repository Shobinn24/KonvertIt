# KonvertIt Deployment Guide

## Prerequisites

- Docker 24+ with Compose V2
- PostgreSQL 15+ (if running without Docker)
- Redis 7+ (if running without Docker)
- A domain with TLS termination (nginx, Caddy, or cloud LB)

---

## Docker Production Deployment

### 1. Build the Production Image

```bash
make docker-prod-build
# or directly:
docker compose -f docker/docker-compose.prod.yml build
```

The production Dockerfile (`docker/Dockerfile.prod`) uses a multi-stage build:
- **Stage 1 (builder):** Installs Python dependencies and Playwright
- **Stage 2 (runtime):** Copies only the built artifacts into a minimal image
- Runs as non-root user `konvertit` (UID 1000)
- Includes a `HEALTHCHECK` that pings `/health` every 30 seconds

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with production values. At minimum, set:

| Variable             | Description                        | Required |
|----------------------|------------------------------------|----------|
| `SECRET_KEY`         | Random 64-char string for JWT signing | yes    |
| `ENCRYPTION_KEY`     | Fernet key for credential encryption  | yes    |
| `DATABASE_URL`       | PostgreSQL connection string          | yes    |
| `REDIS_URL`          | Redis connection string               | yes    |
| `APP_ENV`            | Set to `production`                   | yes    |
| `APP_DEBUG`          | Set to `false`                        | yes    |
| `EBAY_APP_ID`        | eBay API application ID               | yes    |
| `EBAY_DEV_ID`        | eBay API developer ID                 | yes    |
| `EBAY_CERT_ID`       | eBay API certificate ID               | yes    |
| `EBAY_REDIRECT_URI`  | eBay OAuth redirect URI               | yes    |
| `EBAY_SANDBOX`       | Set to `false` for production         | yes    |
| `SCRAPER_API_KEY`    | ScraperAPI key for proxy rotation     | yes    |

**Optional but recommended:**

| Variable                    | Default | Description                         |
|-----------------------------|---------|-------------------------------------|
| `SENTRY_DSN`                | —       | Sentry error tracking DSN            |
| `SENTRY_TRACES_SAMPLE_RATE` | 0.1     | APM trace sampling (0.0-1.0)        |
| `LOG_LEVEL`                 | INFO    | Logging level                        |
| `LOG_FORMAT`                | auto    | `json` in production                 |
| `WEB_CONCURRENCY`           | auto    | Gunicorn worker count                |
| `GUNICORN_TIMEOUT`          | 120     | Request timeout (seconds)            |

### 3. Start Services

```bash
make docker-prod-up
```

This starts three containers:

| Service      | Resources         | Notes                                    |
|--------------|-------------------|------------------------------------------|
| **app**      | 2 CPU / 2 GB RAM  | Gunicorn + Uvicorn workers, port 8000     |
| **postgres** | 1 CPU / 1 GB RAM  | Data persisted in `konvertit_pg_data`     |
| **redis**    | 0.5 CPU / 512 MB  | maxmemory 256 MB, LRU eviction            |

### 4. Run Migrations

```bash
docker compose -f docker/docker-compose.prod.yml exec app alembic upgrade head
```

### 5. Verify

```bash
curl http://localhost:8000/health
```

Expected response: `{"status": "healthy", ...}`

---

## Gunicorn Configuration

The production server uses Gunicorn with Uvicorn workers (`gunicorn.conf.py`):

| Setting            | Value                    | Description                          |
|--------------------|--------------------------|--------------------------------------|
| `worker_class`     | `UvicornWorker`          | ASGI worker for async FastAPI        |
| `workers`          | `min(CPU*2+1, 4)`       | Auto-scaled, overridable via env     |
| `max_requests`     | 1000                     | Restart workers after N requests     |
| `max_requests_jitter` | 50                    | Stagger restarts to avoid thundering |
| `timeout`          | 120s                     | Scraping operations can be slow      |
| `preload_app`      | `False`                  | Async engines don't fork safely      |

Override via environment variables:

```bash
WEB_CONCURRENCY=4        # Worker count
GUNICORN_TIMEOUT=120     # Request timeout
GUNICORN_MAX_REQUESTS=1000
```

---

## Environment Variable Reference

See `.env.example` for the complete list with descriptions. Key sections:

### Application

| Variable        | Default       | Description                      |
|-----------------|---------------|----------------------------------|
| `APP_NAME`      | KonvertIt     | Application name                  |
| `APP_ENV`       | development   | `development` or `production`    |
| `APP_DEBUG`     | true          | Debug mode (disable in prod)      |
| `SECRET_KEY`    | —             | JWT signing secret                |
| `ENCRYPTION_KEY`| —             | Fernet encryption key             |

### Database

| Variable                  | Default              | Description                     |
|---------------------------|----------------------|---------------------------------|
| `DATABASE_URL`            | (local dev default)  | PostgreSQL asyncpg URL           |
| `DATABASE_POOL_SIZE`      | 10                   | Connection pool size             |
| `DATABASE_MAX_OVERFLOW`   | 20                   | Max overflow connections         |
| `DATABASE_POOL_RECYCLE`   | 1800                 | Recycle connections after 30 min |
| `DATABASE_POOL_PRE_PING`  | true                 | Verify connections before use    |
| `DATABASE_POOL_TIMEOUT`   | 30                   | Connection acquisition timeout   |

### Performance

| Variable                | Default | Description                       |
|-------------------------|---------|-----------------------------------|
| `QUERY_SLOW_THRESHOLD_MS` | 200   | Log warning for slow queries      |
| `CACHE_TTL_DEFAULT`     | 300     | Redis cache default TTL (seconds) |
| `GZIP_MINIMUM_SIZE`     | 500     | GZip responses above this size    |

### Observability

| Variable                      | Default | Description                |
|-------------------------------|---------|----------------------------|
| `SENTRY_DSN`                  | —       | Empty = Sentry disabled     |
| `SENTRY_TRACES_SAMPLE_RATE`   | 0.1     | APM trace sampling rate     |
| `SENTRY_PROFILES_SAMPLE_RATE` | 0.1     | Profiling sampling rate     |
| `LOG_LEVEL`                   | INFO    | Python logging level        |
| `LOG_FORMAT`                  | auto    | `console` or `json`         |

---

## Monitoring

### Health Check

```
GET /health
```

Returns `"healthy"` when both DB and Redis are reachable, `"degraded"` otherwise.
The Docker HEALTHCHECK uses this endpoint automatically.

### Structured Logging

- **Development:** Human-readable console output (colored)
- **Production:** JSON lines to stdout (ship to your log aggregator)

Every log entry includes a `request_id` (also sent as `X-Request-ID` response header)
for request tracing.

### Sentry Integration

Set `SENTRY_DSN` to enable error tracking. The integration:
- Automatically captures unhandled exceptions
- Filters out 4xx client errors (only 5xx and unhandled are reported)
- Tags KonvertIt-specific errors with error type
- Supports APM traces and profiling via sampling rates

### Slow Query Detection

Queries exceeding `QUERY_SLOW_THRESHOLD_MS` (default 200ms) are logged at WARN level
with the truncated SQL statement and execution time.

### Error Correlation

Unhandled 500 errors return an `error_id` in the response body. This same ID appears
in the structured logs and Sentry, enabling fast support correlation.

---

## Reverse Proxy

KonvertIt should run behind a TLS-terminating reverse proxy. Example nginx config:

```nginx
upstream konvertit {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name api.konvertit.com;

    ssl_certificate     /etc/ssl/certs/konvertit.crt;
    ssl_certificate_key /etc/ssl/private/konvertit.key;

    location / {
        proxy_pass http://konvertit;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /api/v1/ws {
        proxy_pass http://konvertit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # SSE support — disable buffering
    location /api/v1/conversions/bulk/stream {
        proxy_pass http://konvertit;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

---

## CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) runs:

1. **lint** — ruff check + format verification
2. **test** — Full pytest suite (811 tests) with PostgreSQL + Redis services
3. **security** — bandit static analysis + safety dependency scan
4. **docker** — Production image build verification (main branch only)

Tests and security run in parallel after linting.

---

## Backup & Recovery

### Database Backup

```bash
# Inside Docker
docker compose -f docker/docker-compose.prod.yml exec postgres \
  pg_dump -U konvertit konvertit > backup_$(date +%Y%m%d).sql

# Restore
docker compose -f docker/docker-compose.prod.yml exec -T postgres \
  psql -U konvertit konvertit < backup_20260214.sql
```

### Redis

Redis is used for rate limiting and caching (ephemeral data). No backup needed —
data regenerates automatically on restart.
