# KonvertIt API Reference

Base URL: `/api/v1`

All endpoints require JWT authentication unless noted otherwise.
Pass the access token as `Authorization: Bearer <token>`.

## Authentication

### Register

```
POST /api/v1/auth/register
```

Create a new user account. Returns JWT tokens on success.

| Field      | Type   | Required | Description              |
|------------|--------|----------|--------------------------|
| `email`    | string | yes      | Valid email address       |
| `password` | string | yes      | 8-128 characters          |

**Response (201):**

```json
{
  "user": { "id": "uuid", "email": "...", "tier": "free" },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Login

```
POST /api/v1/auth/login
```

Authenticate with email and password.

| Field      | Type   | Required | Description              |
|------------|--------|----------|--------------------------|
| `email`    | string | yes      | Registered email          |
| `password` | string | yes      | Account password          |

**Response (200):** Same shape as register.

### Refresh Token

```
POST /api/v1/auth/refresh
```

Exchange a refresh token for a new access token.

| Field           | Type   | Required | Description         |
|-----------------|--------|----------|---------------------|
| `refresh_token` | string | yes      | Valid refresh token  |

**Response (200):**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Token Lifetimes:**

| Token   | Default Expiry | Config Variable                   |
|---------|----------------|-----------------------------------|
| Access  | 15 minutes     | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh | 7 days         | `JWT_REFRESH_TOKEN_EXPIRE_DAYS`   |

### eBay OAuth

```
POST /api/v1/auth/ebay/connect    # Returns authorization URL
GET  /api/v1/auth/ebay/callback   # Handles OAuth callback
```

---

## Users

### Get Profile

```
GET /api/v1/users/me
```

Returns the authenticated user's profile.

### Update Profile

```
PUT /api/v1/users/me
```

Update profile fields (at least one field required).

### Usage Statistics

```
GET /api/v1/users/me/usage
```

Returns daily conversion usage, tier limits, and remaining quota.

---

## Conversions

### Convert a URL

```
POST /api/v1/conversions/
```

Convert a single product URL through the full pipeline:
scrape → compliance check → convert → price.

| Field        | Type    | Required | Description                    |
|--------------|---------|----------|--------------------------------|
| `url`        | string  | yes      | Amazon or Walmart product URL   |
| `publish`    | boolean | no       | Publish to eBay (default false) |
| `sell_price` | number  | no       | Override selling price           |

**Response (200):** Conversion result with product data, listing draft, and pricing.

### Bulk Convert

```
POST /api/v1/conversions/bulk
```

Convert multiple URLs sequentially. Returns a JSON summary after all complete.

| Field        | Type     | Required | Description                     |
|--------------|----------|----------|---------------------------------|
| `urls`       | string[] | yes      | 1-50 product URLs               |
| `publish`    | boolean  | no       | Publish to eBay (default false)  |
| `sell_price` | number   | no       | Override selling price            |

### Bulk Convert with SSE Streaming

```
POST /api/v1/conversions/bulk/stream
```

Same as bulk convert but returns a `text/event-stream` response with real-time
progress events:

| SSE Event        | Description                                |
|------------------|--------------------------------------------|
| `job_started`    | Job created with total URL count            |
| `item_started`   | Individual URL conversion starting          |
| `item_step`      | Pipeline step changed (scraping, etc.)      |
| `item_completed` | Individual URL finished                     |
| `job_progress`   | Aggregate progress after each item          |
| `job_completed`  | Entire job finished with final summary      |
| `heartbeat`      | Keep-alive ping every 15 seconds            |
| `error`          | Unexpected stream error                     |

The response includes an `X-Job-ID` header for tracking.

### Preview Conversion

```
POST /api/v1/conversions/preview
```

Run the full pipeline without creating a listing on eBay.

| Field | Type   | Required | Description             |
|-------|--------|----------|-------------------------|
| `url` | string | yes      | Product URL to preview   |

### List Conversions

```
GET /api/v1/conversions/
```

List conversion history for the authenticated user.

| Param    | Type   | Default | Description                                      |
|----------|--------|---------|--------------------------------------------------|
| `status` | string | —       | Filter: `pending`, `processing`, `completed`, `failed` |
| `limit`  | int    | 50      | Max results (1-200)                               |
| `offset` | int    | 0       | Pagination offset                                 |

### Get Job Status

```
GET /api/v1/conversions/jobs/{job_id}
```

Check progress of a bulk conversion job.

### Cancel Job

```
POST /api/v1/conversions/jobs/{job_id}/cancel
```

Cancel a running bulk job. Already-completed items are not affected.

---

## Products

### Scrape Product

```
POST /api/v1/products/scrape
```

Scrape a product from a source marketplace URL. Returns product data and
compliance status.

| Field | Type   | Required | Description     |
|-------|--------|----------|-----------------|
| `url` | string | yes      | Product URL      |

### List Products

```
GET /api/v1/products/
```

List scraped products for the authenticated user.

| Param         | Type   | Default | Description                        |
|---------------|--------|---------|------------------------------------|
| `marketplace` | string | —       | Filter: `amazon`, `walmart`         |
| `limit`       | int    | 50      | Max results (1-200)                 |
| `offset`      | int    | 0       | Pagination offset                   |

### Get Product

```
GET /api/v1/products/{product_id}
```

Get product details. Only returns products belonging to the authenticated user.

---

## Listings

### List Listings

```
GET /api/v1/listings/
```

List eBay listings for the authenticated user.

| Param    | Type   | Default | Description                                    |
|----------|--------|---------|------------------------------------------------|
| `status` | string | —       | Filter: `draft`, `active`, `ended`, `error`     |
| `limit`  | int    | 50      | Max results (1-200)                             |
| `offset` | int    | 0       | Pagination offset                               |

### Get Listing

```
GET /api/v1/listings/{listing_id}
```

Get listing details. Only returns listings belonging to the authenticated user.

### Update Price

```
PUT /api/v1/listings/{listing_id}/price
```

Update the price of a listing.

| Field   | Type   | Required | Description      |
|---------|--------|----------|------------------|
| `price` | number | yes      | New price (> 0)   |

### End Listing

```
POST /api/v1/listings/{listing_id}/end
```

End (delist) a listing. The listing must be in `active` or `draft` status.
Returns 409 if the listing is already ended or in error state.

---

## Price History

### Get Price History

```
GET /api/v1/products/{product_id}/prices
```

Returns recorded price observations over time, newest first.

| Param    | Type | Default | Description          |
|----------|------|---------|----------------------|
| `limit`  | int  | 100     | Max results (1-500)  |
| `offset` | int  | 0       | Pagination offset    |

### Get Price Statistics

```
GET /api/v1/products/{product_id}/prices/stats
```

Returns min, max, average price, and total observation count.

---

## WebSocket

```
GET /api/v1/ws?token=<access_token>
```

Upgrades to a WebSocket connection for real-time push notifications.
Authentication is via JWT passed as a query parameter (WebSocket handshake
does not support custom headers).

**Event Types:**

| Event                | Description                          |
|----------------------|--------------------------------------|
| `welcome`            | Connection established (tier, limits) |
| `price_alert`        | Source product price changed           |
| `listing_updated`    | eBay listing status/price changed     |
| `conversion_complete`| Background conversion finished        |
| `rate_limit_warning` | Approaching daily rate limit          |
| `heartbeat`          | Keep-alive ping every 30s             |
| `error`              | Server error                          |

**Connection Limits (per tier):**

| Tier       | Max Connections |
|------------|-----------------|
| Free       | 1               |
| Pro        | 3               |
| Enterprise | 10              |

**Close Codes:**

| Code | Reason                          |
|------|---------------------------------|
| 4001 | Missing or invalid token        |
| 4003 | Token is not an access token    |
| 4008 | Connection limit exceeded       |
| 1000 | Normal closure                  |
| 1011 | Unexpected server error         |

---

## Health Check

```
GET /health
```

No authentication required. Returns system status with DB and Redis probes.

**Response (200):**

```json
{
  "status": "healthy",
  "app_name": "KonvertIt",
  "version": "0.1.0",
  "environment": "production",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

Status is `"degraded"` if either DB or Redis probe fails (service remains available).

---

## Rate Limiting

Conversion endpoints are rate-limited per user tier on a daily basis (UTC).

| Tier       | Daily Conversions |
|------------|-------------------|
| Free       | 10                |
| Pro        | 100               |
| Enterprise | Unlimited         |

Rate limit headers are included on all conversion responses:

| Header                | Description                    |
|-----------------------|--------------------------------|
| `X-RateLimit-Limit`   | Daily limit for the user's tier |
| `X-RateLimit-Used`    | Conversions used today          |
| `X-RateLimit-Remaining` | Remaining conversions today  |
| `X-RateLimit-Reset`   | Seconds until limit resets      |

When the limit is exceeded, the API returns **429 Too Many Requests** with a
`Retry-After` header (seconds until midnight UTC).

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

For unhandled 500 errors, an `error_id` is included for support correlation:

```json
{
  "detail": "Internal server error",
  "error_id": "abc12345"
}
```

**Standard HTTP Status Codes:**

| Code | Meaning                                     |
|------|---------------------------------------------|
| 200  | Success                                      |
| 201  | Created (registration)                       |
| 400  | Bad request / invalid input                  |
| 401  | Missing or invalid authentication             |
| 404  | Resource not found (or tenant isolation)      |
| 409  | Conflict (e.g., ending an already-ended listing) |
| 422  | Validation error                              |
| 429  | Rate limit exceeded                           |
| 500  | Internal server error                         |

**Note:** Tenant isolation returns 404 (not 403) to prevent resource enumeration.
