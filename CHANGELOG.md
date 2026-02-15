# Changelog

All notable changes to KonvertIt are documented in this file.

## [1.0.0] - 2026-02-14

### Initial Release

**Core Pipeline**
- Amazon and Walmart product scraping via Playwright with proxy rotation
- Circuit-breaker and retry-with-backoff resilience patterns
- VeRO compliance checking before every listing
- 6-step title optimization pipeline (80 chars, keyword-rich)
- 3 description templates: Modern, Classic, Minimal
- Automated eBay category mapping
- Fee-aware profit calculation engine (eBay FVF, shipping, margin targets)

**API**
- 22 REST endpoints across 7 routers (auth, users, conversions, products, listings, price history, WebSocket)
- JWT authentication with access + refresh tokens
- eBay OAuth2 integration for seller account linking
- Tiered rate limiting: free (10/day), pro (100/day), enterprise (unlimited)
- Server-Sent Events for bulk conversion progress streaming
- WebSocket push notifications (price alerts, listing updates, conversion completions)

**Frontend**
- React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui
- Dashboard with usage stats, rate limit bar, activity feed, quick convert
- Convert page with single and bulk modes, real-time SSE progress
- Listings management with status tabs, price updates, end listing
- Settings page with eBay connection, account, and preferences
- WebSocket-driven toast notifications and auto-refreshing queries

**Infrastructure**
- PostgreSQL 15+ with 7 tables, 2 Alembic migrations, 5 performance indexes
- Redis for rate limiting and query caching (fail-open pattern)
- Docker multi-stage production builds with non-root user
- Gunicorn + Uvicorn ASGI workers (auto-scaled)
- GitHub Actions CI: lint, test, security scan, Docker build
- Structured logging (structlog, JSON in production)
- Sentry error tracking with 4xx filtering
- Health checks with DB and Redis probes
- Slow query detection (200ms threshold)
- GZip response compression
- Security headers middleware

**Testing**
- 811 tests: unit (~750), integration (38), E2E smoke (33)
- 80% coverage threshold

**Documentation**
- OpenAPI/Swagger with tag descriptions and endpoint summaries
- README, API reference, deployment guide, user onboarding guide
