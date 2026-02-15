import { useQuery } from "@tanstack/react-query";
import { getUsageStats } from "@/services/userService";
import { getConversions } from "@/services/conversionService";
import { getListings } from "@/services/listingService";

export function useUsageStats() {
  return useQuery({
    queryKey: ["usage-stats"],
    queryFn: getUsageStats,
    staleTime: 30_000,
  });
}

export function useRecentConversions(limit = 5) {
  return useQuery({
    queryKey: ["recent-conversions", limit],
    queryFn: () => getConversions({ limit, offset: 0 }),
    staleTime: 30_000,
  });
}

export function useRecentListings(limit = 5) {
  return useQuery({
    queryKey: ["recent-listings", limit],
    queryFn: () => getListings({ limit, offset: 0 }),
    staleTime: 30_000,
  });
}
