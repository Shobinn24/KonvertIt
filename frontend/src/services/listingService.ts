import api from "./apiClient";
import type { Listing, ListingsPage } from "@/types/api";

export async function getListings(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ListingsPage> {
  const res = await api.get<ListingsPage>("/listings", { params });
  return res.data;
}

export async function updateListingPrice(
  listingId: string,
  price: number,
): Promise<Listing> {
  const res = await api.put<Listing>(`/listings/${listingId}/price`, { price });
  return res.data;
}

export async function endListing(
  listingId: string,
): Promise<{ id: string; status: string; message: string }> {
  const res = await api.post(`/listings/${listingId}/end`);
  return res.data;
}
