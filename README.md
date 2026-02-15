# KonvertIt

Multi-marketplace product conversion platform that transforms Amazon and Walmart
product listings into optimized eBay listing drafts.

Built by **E-Clarx LLC**.

## Features

- **Multi-Marketplace Scraping** — Extract product data from Amazon and Walmart via
  Playwright-based scrapers with proxy rotation and circuit-breaker resilience.
- **Smart Conversion** — 6-step title optimization, 3 description templates
  (Modern / Classic / Minimal), automated eBay category mapping.
- **Compliance** — VeRO restricted-brand checking before every listing.
- **Profit Calculation** — Fee-aware pricing engine covering eBay final-value fees,
  shipping estimates, and configurable margin targets.
- **Bulk Operations** — Convert up to 50 URLs in one request with real-time
  Server-Sent Events (SSE) progress streaming.
- **Price Monitoring** — Background cron checks source prices and pushes WebSocket
  alerts when they change.
- **Real-Time Updates** — WebSocket push notifications for price alerts, listing
  changes, and conversion completions.
- **Tiered Rate Limiting** — Redis-backed per-user daily limits (free / pro / enterprise)
  with fail-open safety.
- **Production-Ready** — Gunicorn + Uvicorn workers, Docker multi-stage builds,
  structured logging (structlog), Sentry integration, health checks with DB/Redis probes.

## Tech Stack

| Layer          | Technology                                                      |
|----------------|-----------------------------------------------------------------|
| **Backend**    | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), asyncpg          |
| **Frontend**   | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui             |
| **Database**   | PostgreSQL 15+                                                   |
| **Cache/Queue**| Redis 7+, arq (background tasks)                                |
| **Scraping**   | Playwright (Chromium), ScraperAPI proxy rotation                 |
| **Auth**       | JWT (access + refresh tokens), eBay OAuth2                       |
| **Observability** | structlog (JSON in prod), Sentry, slow-query detection        |
| **CI/CD**      | GitHub Actions (lint, test, security scan, Docker build)         |

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (frontend)

### Setup

```bash
# Clone and enter the project
git clone <repo-url> && cd KonvertIt

# Copy environment config
cp .env.example .env
# Edit .env with your database, Redis, and eBay API credentials

# Install backend dependencies
make install

# Run database migrations
make migrate

# Start the API server (dev mode with hot reload)
make run
```

The API is now available at `http://localhost:8000`.
Interactive docs at `http://localhost:8000/docs` (dev mode only).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is available at `http://localhost:5173` and proxies API calls to the backend.

### Docker (Development)

```bash
make docker-up      # Starts PostgreSQL + Redis + app
make docker-down    # Stops all services
```

### Docker (Production)

```bash
make docker-prod-build   # Multi-stage production image
make docker-prod-up      # Starts with resource limits, log rotation
make docker-prod-down
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full production deployment instructions.

## Project Structure

```
KonvertIt/
├── app/
│   ├── api/v1/            # FastAPI route handlers
│   │   ├── auth.py        # Register, login, refresh, eBay OAuth
│   │   ├── users.py       # Profile, usage stats
│   │   ├── conversions.py # Convert, bulk, preview, SSE stream
│   │   ├── products.py    # Scrape, list, detail
│   │   ├── listings.py    # List, detail, reprice, end
│   │   ├── price_history.py # Price tracking & stats
│   │   └── ws.py          # WebSocket endpoint
│   ├── config.py          # Pydantic Settings (env vars)
│   ├── core/              # Logging, Sentry, health, exceptions
│   ├── converters/        # EbayConverter, TitleOptimizer, DescriptionBuilder
│   ├── db/                # SQLAlchemy models, repositories, migrations
│   ├── listers/           # EbayLister, EbayAuth (OAuth)
│   ├── middleware/        # Auth, rate limiter, security headers, logging
│   ├── scrapers/          # BaseScraper, AmazonScraper, WalmartScraper
│   └── services/          # ConversionService, ProfitEngine, ComplianceService, etc.
├── frontend/              # React 18 + TypeScript + Vite
├── docker/                # Dockerfiles and Compose configs
├── tests/
│   ├── unit/              # ~750 unit tests
│   ├── integration/       # 38 integration tests
│   └── e2e/               # 33 E2E smoke tests
├── docs/                  # Documentation
│   ├── API.md             # API reference
│   ├── DEPLOYMENT.md      # Production deployment guide
│   └── ONBOARDING.md      # User onboarding guide
├── gunicorn.conf.py       # Production WSGI/ASGI config
├── Makefile               # Developer workflow commands
└── .env.example           # Environment variable reference
```

## Available Make Commands

| Command               | Description                               |
|-----------------------|-------------------------------------------|
| `make help`           | Show all available commands                |
| `make install`        | Install all dependencies + Playwright      |
| `make test`           | Run all tests with coverage                |
| `make test-unit`      | Run unit tests only                        |
| `make lint`           | Run ruff linter checks                     |
| `make format`         | Auto-format code with ruff                 |
| `make security`       | Run bandit + safety scans                  |
| `make migrate`        | Run Alembic database migrations            |
| `make run`            | Start dev server with hot reload           |
| `make docker-up`      | Start dev Docker services                  |
| `make docker-prod-up` | Start production Docker services           |
| `make clean`          | Remove cache and build artifacts           |

## API Documentation

- **Interactive (Swagger):** `http://localhost:8000/docs` (dev mode)
- **ReDoc:** `http://localhost:8000/redoc` (dev mode)
- **Reference:** [docs/API.md](docs/API.md)

## Testing

```bash
# Full suite (811 tests)
make test

# Unit tests only
make test-unit

# Specific markers
pytest tests/ -m e2e -v
pytest tests/ -m integration -v
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/API.md](docs/API.md) | API endpoint reference, authentication, rate limits, error codes |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment, Docker, environment configuration, monitoring |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | User onboarding guide and getting-started flow |

## License

Proprietary — E-Clarx LLC. All rights reserved.
