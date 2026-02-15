import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getListings,
  updateListingPrice,
  endListing,
} from "@/services/listingService";

export function useListingsQuery(params: {
  status?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["listings", params],
    queryFn: () => getListings(params.status ? params : { limit: params.limit, offset: params.offset }),
    staleTime: 30_000,
  });
}

export function useUpdatePriceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listingId, price }: { listingId: string; price: number }) =>
      updateListingPrice(listingId, price),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
  });
}

export function useEndListingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (listingId: string) => endListing(listingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
  });
}
