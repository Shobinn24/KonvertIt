import api from "./apiClient";

export interface AutoDiscoveryConfig {
  enabled: boolean;
  auto_publish: boolean;
  min_margin_pct: number;
  max_daily_items: number;
  marketplaces: string[];
  last_run_at: string | null;
  items_found_today: number;
}

export interface AutoDiscoveryConfigUpdate {
  enabled?: boolean;
  auto_publish?: boolean;
  min_margin_pct?: number;
  max_daily_items?: number;
  marketplaces?: string[];
}

export interface ConvertedProductDetail {
  title: string;
  source_price: number;
  sell_price: number;
  estimated_profit: number;
  margin_pct: number;
  marketplace: string;
  url: string;
  published: boolean;
  ebay_item_id: string | null;
}

export interface AutoDiscoveryRun {
  id: string;
  data_source: string;
  queries_searched: string[];
  products_evaluated: number;
  products_converted: number;
  products_skipped_duplicate: number;
  products_skipped_compliance: number;
  products_skipped_margin: number;
  errors: number;
  run_at: string;
  converted_product_details: ConvertedProductDetail[];
}

export interface AutoDiscoveryRunResult {
  data_source: string;
  queries_searched: string[];
  products_evaluated: number;
  products_converted: number;
  errors: number;
  converted_product_details: ConvertedProductDetail[];
}

export async function getAutoDiscoveryConfig(): Promise<AutoDiscoveryConfig> {
  const res = await api.get<AutoDiscoveryConfig>("/auto-discover/config");
  return res.data;
}

export async function updateAutoDiscoveryConfig(
  data: AutoDiscoveryConfigUpdate
): Promise<AutoDiscoveryConfig> {
  const res = await api.put<AutoDiscoveryConfig>("/auto-discover/config", data);
  return res.data;
}

export async function triggerAutoDiscoveryRun(): Promise<AutoDiscoveryRunResult> {
  const res = await api.post<AutoDiscoveryRunResult>("/auto-discover/run");
  return res.data;
}

export async function getAutoDiscoveryHistory(
  limit = 20
): Promise<AutoDiscoveryRun[]> {
  const res = await api.get<AutoDiscoveryRun[]>("/auto-discover/history", {
    params: { limit },
  });
  return res.data;
}
