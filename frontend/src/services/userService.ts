import api from "./apiClient";
import type { UserProfile, UsageStats } from "@/types/api";

export async function getProfile(): Promise<UserProfile> {
  const res = await api.get<UserProfile>("/users/me");
  return res.data;
}

export async function updateProfile(data: {
  email?: string;
  password?: string;
}): Promise<UserProfile> {
  const res = await api.put<UserProfile>("/users/me", data);
  return res.data;
}

export async function getUsageStats(): Promise<UsageStats> {
  const res = await api.get<UsageStats>("/users/me/usage");
  return res.data;
}
