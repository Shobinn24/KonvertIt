import api from "./apiClient";
import type { ConversionsPage, ConversionResult } from "@/types/api";

export async function getConversions(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ConversionsPage> {
  const res = await api.get<ConversionsPage>("/conversions", { params });
  return res.data;
}

export async function convertSingle(url: string): Promise<ConversionResult> {
  const res = await api.post<ConversionResult>("/conversions", { url });
  return res.data;
}
