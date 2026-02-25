import { z } from "zod";

// ─── Auth ──────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  tier: "free" | "pro" | "enterprise";
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
}

export interface AuthResponse {
  user: UserProfile;
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ─── Usage ─────────────────────────────────────────────────────

export interface UsageStats {
  tier: string;
  conversions: Record<string, number>;
  listings: Record<string, number>;
  limits: {
    daily_conversions: number;
    max_listings: number;
  };
}

// ─── Conversion Result ─────────────────────────────────────────

export interface ProductInfo {
  title: string;
  price: number;
  brand: string;
  source_product_id: string;
  image_urls: string[];
  description?: string;
  category?: string;
  source_marketplace?: "amazon" | "walmart";
}

export interface ComplianceInfo {
  is_compliant: boolean;
  risk_level: "clear" | "warning" | "blocked";
  violations: string[];
}

export interface DraftInfo {
  title: string;
  price: number;
  sku: string;
}

export interface ProfitInfo {
  cost: number;
  sell_price: number;
  profit: number;
  margin_pct: number;
  total_fees: number;
  ebay_fee?: number;
  payment_fee?: number;
  shipping_cost?: number;
}

export interface ListingInfo {
  marketplace_item_id: string;
  status: string;
  url: string;
}

export interface ConversionResult {
  url: string;
  status: "pending" | "processing" | "completed" | "failed";
  step: string;
  product: ProductInfo | null;
  compliance: ComplianceInfo | null;
  draft: DraftInfo | null;
  profit: ProfitInfo | null;
  listing: ListingInfo | null;
  error: string | null;
}

// ─── Conversion History ────────────────────────────────────────

export interface ConversionRecord {
  id: string;
  product_id: string;
  listing_id: string | null;
  status: string;
  error_message: string | null;
  converted_at: string | null;
  created_at: string | null;
}

export interface ConversionsPage {
  conversions: ConversionRecord[];
  total: number;
}

// ─── Products ──────────────────────────────────────────────────

export interface ProductRecord {
  id: string;
  source_marketplace: "amazon" | "walmart";
  source_url: string;
  source_product_id: string;
  title: string;
  price: number;
  brand: string;
  category: string;
  image_urls: string[];
  scraped_at: string | null;
  created_at: string | null;
}

export interface ProductsPage {
  products: ProductRecord[];
  total: number;
}

// ─── Listings ──────────────────────────────────────────────────

export type ListingStatus = "draft" | "active" | "ended" | "error";

export interface Listing {
  id: string;
  ebay_item_id: string | null;
  title: string;
  price: number;
  ebay_category_id: string | null;
  status: ListingStatus;
  listed_at: string | null;
  last_synced_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ListingsPage {
  listings: Listing[];
  total: number;
}

// ─── Rate Limit ────────────────────────────────────────────────

export interface RateLimitState {
  limit: number;
  remaining: number;
  reset: number;
}

// ─── SSE Events ────────────────────────────────────────────────

export type SSEEventType =
  | "job_started"
  | "item_started"
  | "item_step"
  | "item_completed"
  | "job_progress"
  | "job_completed"
  | "heartbeat"
  | "error";

export interface BulkItemState {
  url: string;
  status: "pending" | "processing" | "completed" | "failed";
  step: string | null;
  result: ConversionResult | null;
  error: string | null;
}

// ─── WebSocket Events ─────────────────────────────────────────

export type WSEventType =
  | "welcome"
  | "price_alert"
  | "listing_updated"
  | "conversion_complete"
  | "rate_limit_warning"
  | "tier_changed"
  | "heartbeat"
  | "error";

export interface WSEvent {
  event: WSEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

// ─── Discovery ────────────────────────────────────────────────

export interface DiscoveryProduct {
  name: string;
  price: number;
  price_symbol: string;
  image: string;
  url: string;
  stars: number | null;
  total_reviews: number | null;
  is_prime: boolean;
  is_best_seller: boolean;
  is_amazons_choice: boolean;
  seller: string;
  marketplace: "amazon" | "walmart";
}

export interface DiscoveryResponse {
  products: DiscoveryProduct[];
  page: number;
  total_pages: number | null;
  marketplace: string;
  query: string;
}

// ─── Zod Form Schemas ──────────────────────────────────────────

export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    email: z.string().email("Invalid email address"),
    password: z.string().min(8, "Password must be at least 8 characters").max(128),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;
