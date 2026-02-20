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

export interface ConvertSingleParams {
  url: string;
  publish?: boolean;
  sell_price?: number | null;
}

export async function convertSingle(
  params: ConvertSingleParams,
): Promise<ConversionResult> {
  const res = await api.post<ConversionResult>("/conversions", params);
  return res.data;
}
