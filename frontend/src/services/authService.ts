import api from "./apiClient";
import type { AuthResponse, TokenResponse } from "@/types/api";

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("/auth/login", { email, password });
  return res.data;
}

export async function register(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("/auth/register", {
    email,
    password,
  });
  return res.data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return res.data;
}

export async function getEbayConnectUrl(): Promise<{
  authorization_url: string;
  state: string;
}> {
  const res = await api.post("/auth/ebay/connect");
  return res.data;
}

export async function handleEbayCallback(
  code: string,
  state?: string,
): Promise<{ message: string; store_name: string }> {
  const params = new URLSearchParams({ code });
  if (state) params.set("state", state);
  const res = await api.get(`/auth/ebay/callback?${params.toString()}`);
  return res.data;
}
