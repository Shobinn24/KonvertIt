import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "@/services/discoveryService";

export function useDiscoverSearch(params: {
  query: string;
  marketplace: "amazon" | "walmart";
  page: number;
}) {
  return useQuery({
    queryKey: ["discover", params.query, params.marketplace, params.page],
    queryFn: () => searchProducts(params),
    enabled: params.query.length > 0,
    staleTime: 60_000, // Cache search results for 1 minute
    placeholderData: (previousData) => previousData, // Smooth pagination
  });
}
