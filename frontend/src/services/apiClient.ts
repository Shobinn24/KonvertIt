import axios from "axios";
import type { RateLimitState } from "@/types/api";

const TOKEN_KEY = "konvertit_access_token";
const REFRESH_KEY = "konvertit_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach Bearer token to every request
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Silent refresh on 401
let refreshPromise: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/refresh") &&
      !original.url?.includes("/auth/login")
    ) {
      original._retry = true;

      try {
        // Deduplicate concurrent refresh calls
        if (!refreshPromise) {
          refreshPromise = doRefresh();
        }
        const newToken = await refreshPromise;
        refreshPromise = null;

        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        refreshPromise = null;
        clearTokens();
        window.dispatchEvent(new Event("auth:logout"));
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  },
);

async function doRefresh(): Promise<string> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token");

  // Use a raw axios call to avoid the interceptor loop
  const res = await axios.post("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });

  const newAccessToken: string = res.data.access_token;
  localStorage.setItem(TOKEN_KEY, newAccessToken);
  return newAccessToken;
}

export function extractRateLimitHeaders(
  headers: Record<string, string>,
): RateLimitState | null {
  const limit = headers["x-ratelimit-limit"];
  const remaining = headers["x-ratelimit-remaining"];
  const reset = headers["x-ratelimit-reset"];

  if (!limit || !remaining || !reset) return null;
  if (limit === "unlimited") {
    return { limit: -1, remaining: -1, reset: Number(reset) };
  }

  return {
    limit: Number(limit),
    remaining: Number(remaining),
    reset: Number(reset),
  };
}

export default api;
