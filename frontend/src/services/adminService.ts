import api from "./apiClient";

// The admin key is stored in sessionStorage for the current tab only
const ADMIN_KEY_STORAGE = "konvertit_admin_key";

export function setAdminKey(key: string) {
  sessionStorage.setItem(ADMIN_KEY_STORAGE, key);
}

export function getAdminKey(): string | null {
  return sessionStorage.getItem(ADMIN_KEY_STORAGE);
}

export function clearAdminKey() {
  sessionStorage.removeItem(ADMIN_KEY_STORAGE);
}

function adminHeaders() {
  const key = getAdminKey();
  if (!key) throw new Error("Admin key not set");
  return { "X-Admin-Key": key };
}

// ─── Types ──────────────────────────────────────────────────

export interface AdminUserSummary {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  tier: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string | null;
  last_login: string | null;
  conversion_count: number;
  listing_count: number;
}

export interface AdminUserDetail extends AdminUserSummary {
  city: string;
  state: string;
  country: string;
  postal_code: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  recent_errors: {
    id: string;
    error_message: string;
    status: string;
    source_url: string;
    created_at: string | null;
  }[];
}

export interface AdminUsersResponse {
  users: AdminUserSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminErrorEntry {
  id: string;
  user_id: string;
  user_email: string;
  error_message: string;
  status: string;
  source_url: string;
  created_at: string | null;
}

export interface AdminErrorsResponse {
  errors: AdminErrorEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  verified_users: number;
  users_by_tier: Record<string, number>;
  total_conversions: number;
  conversions_today: number;
  failed_conversions: number;
  total_listings: number;
  active_listings: number;
  new_users_today: number;
  new_users_this_week: number;
}

// ─── API Calls ──────────────────────────────────────────────

export async function getAdminStats(): Promise<AdminStats> {
  const res = await api.get<AdminStats>("/admin/stats", { headers: adminHeaders() });
  return res.data;
}

export async function getAdminUsers(params: {
  page?: number;
  page_size?: number;
  search?: string;
  tier?: string;
}): Promise<AdminUsersResponse> {
  const res = await api.get<AdminUsersResponse>("/admin/users", {
    headers: adminHeaders(),
    params,
  });
  return res.data;
}

export async function getAdminUserDetail(userId: string): Promise<AdminUserDetail> {
  const res = await api.get<AdminUserDetail>(`/admin/users/${userId}`, {
    headers: adminHeaders(),
  });
  return res.data;
}

export async function getAdminErrors(params: {
  page?: number;
  page_size?: number;
  user_id?: string;
}): Promise<AdminErrorsResponse> {
  const res = await api.get<AdminErrorsResponse>("/admin/errors", {
    headers: adminHeaders(),
    params,
  });
  return res.data;
}

/** Validate admin key by hitting the stats endpoint */
export async function validateAdminKey(key: string): Promise<boolean> {
  try {
    await api.get("/admin/stats", { headers: { "X-Admin-Key": key } });
    return true;
  } catch {
    return false;
  }
}
