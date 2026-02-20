import api from "./apiClient";
import type { DiscoveryResponse } from "@/types/api";

export interface SearchProductsParams {
  query: string;
  marketplace?: "amazon" | "walmart";
  page?: number;
}

export async function searchProducts(
  params: SearchProductsParams
): Promise<DiscoveryResponse> {
  const res = await api.get<DiscoveryResponse>("/discover/search", { params });
  return res.data;
}
