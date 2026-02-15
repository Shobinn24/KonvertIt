# KonvertIt User Onboarding Guide

This guide walks through the complete flow from account creation to your first
eBay listing.

---

## Step 1: Create an Account

```
POST /api/v1/auth/register
{
  "email": "you@example.com",
  "password": "your-secure-password"
}
```

**What happens:**
- A new account is created on the **free** tier (10 conversions/day).
- You receive an `access_token` (15 min) and `refresh_token` (7 days).
- Use the access token for all subsequent API calls.

**Frontend:** Navigate to `/register`, fill in email and password, click Register.

---

## Step 2: Connect Your eBay Account

Before you can publish listings, you need to link your eBay seller account via OAuth.

```
POST /api/v1/auth/ebay/connect
Authorization: Bearer <access_token>
```

**What happens:**
- The API returns an `authorization_url` pointing to eBay's consent page.
- Open the URL in your browser and authorize KonvertIt.
- eBay redirects back to the callback endpoint, which stores your credentials securely.

**Frontend:** Go to Settings > eBay Connection and click "Connect eBay Account".

> **Note:** You can skip this step if you only want to create draft listings (not publish to eBay).

---

## Step 3: Convert Your First Product

Paste an Amazon or Walmart product URL to run the full conversion pipeline.

```
POST /api/v1/conversions/
Authorization: Bearer <access_token>
{
  "url": "https://www.amazon.com/dp/B08N5WRWNW",
  "publish": false
}
```

**The pipeline runs these steps:**

1. **Scrape** — Extracts title, price, images, brand, description from the source page.
2. **Compliance** — Checks against the eBay VeRO restricted-brand database.
3. **Convert** — Optimizes the title (80 chars, keyword-rich), builds a structured
   eBay description, maps to the best eBay category.
4. **Price** — Calculates profit margin after eBay fees and shipping estimates.

**Response:** A conversion result containing the optimized listing draft.

Set `"publish": true` to immediately list on eBay (requires eBay connection).

**Frontend:** Go to the Convert page, paste a URL, and click "Convert".

---

## Step 4: Preview Before Publishing

If you want to review the listing before committing:

```
POST /api/v1/conversions/preview
Authorization: Bearer <access_token>
{
  "url": "https://www.amazon.com/dp/B08N5WRWNW"
}
```

This runs the full pipeline but does **not** create an eBay listing.

**Frontend:** The Convert page shows a preview panel with the optimized title,
description, images, pricing breakdown, and compliance status before you publish.

---

## Step 5: Bulk Convert

Convert up to 50 URLs at once:

```
POST /api/v1/conversions/bulk/stream
Authorization: Bearer <access_token>
{
  "urls": [
    "https://www.amazon.com/dp/B08N5WRWNW",
    "https://www.amazon.com/dp/B09V3KXJPB",
    "https://www.walmart.com/ip/123456789"
  ],
  "publish": false
}
```

This returns a Server-Sent Events (SSE) stream with real-time progress.
Each URL progresses through: `item_started` → `item_step` (scraping, compliance,
converting, pricing) → `item_completed`.

**Frontend:** The Bulk Convert tab shows a progress bar for each URL in real time.

---

## Step 6: Manage Your Listings

### View All Listings

```
GET /api/v1/listings/?status=active
Authorization: Bearer <access_token>
```

### Update a Price

```
PUT /api/v1/listings/{listing_id}/price
Authorization: Bearer <access_token>
{
  "price": 29.99
}
```

### End a Listing

```
POST /api/v1/listings/{listing_id}/end
Authorization: Bearer <access_token>
```

**Frontend:** The Listings page shows tabs for Draft, Active, Ended, and Error.
Click any listing to view details, update the price, or end it.

---

## Step 7: Monitor Prices

KonvertIt automatically checks source product prices on a background schedule
(default: every 6 hours). When a price changes, you receive a real-time WebSocket
notification.

### View Price History

```
GET /api/v1/products/{product_id}/prices
Authorization: Bearer <access_token>
```

### View Price Statistics

```
GET /api/v1/products/{product_id}/prices/stats
Authorization: Bearer <access_token>
```

Returns min, max, and average observed prices.

**Frontend:** The Dashboard shows price alert toasts in real time. Check the
product detail page for full price history charts.

---

## Step 8: Real-Time Notifications

Connect to the WebSocket for live updates:

```
ws://localhost:8000/api/v1/ws?token=<access_token>
```

You will receive push events for:
- **Price alerts** — Source product price changed
- **Listing updates** — eBay listing status or price changed
- **Conversion complete** — Background conversion finished
- **Rate limit warnings** — Approaching your daily limit

**Frontend:** Notifications appear as toast messages at the bottom of the screen
and automatically refresh the Dashboard data.

---

## User Tiers

| Feature              | Free  | Pro   | Enterprise |
|----------------------|-------|-------|------------|
| Daily conversions    | 10    | 100   | Unlimited  |
| WebSocket connections| 1     | 3     | 10         |
| Rate limit bypass    | No    | No    | Yes        |

To upgrade your tier, contact support.

---

## Common Workflows

### Quick Single Listing

1. Register or login
2. Connect eBay (one-time)
3. `POST /conversions/` with `publish: true`
4. Done — listing is live on eBay

### Research Without Publishing

1. Login
2. `POST /conversions/preview` to see the optimized listing
3. Review pricing and compliance
4. Decide whether to proceed

### Bulk Sourcing Session

1. Login
2. Collect 10-50 product URLs
3. `POST /conversions/bulk/stream` with `publish: false`
4. Review results on the Listings page (status: draft)
5. Publish selected drafts individually

---

## Troubleshooting

| Issue                        | Solution                                      |
|------------------------------|-----------------------------------------------|
| 401 Unauthorized             | Token expired — call `POST /auth/refresh`      |
| 422 Validation Error         | Check request body matches the API schema      |
| 429 Rate Limit Exceeded      | Wait until midnight UTC or upgrade tier         |
| Conversion fails (scraping)  | URL may be blocked — try again or check proxy config |
| eBay publish fails           | Verify eBay credentials in Settings             |
| WebSocket disconnects        | Client auto-reconnects with exponential backoff |
