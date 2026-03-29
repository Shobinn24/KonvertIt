import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAutoDiscoveryConfig,
  updateAutoDiscoveryConfig,
  triggerAutoDiscoveryRun,
  getAutoDiscoveryHistory,
  type AutoDiscoveryConfigUpdate,
} from "@/services/autoDiscoveryService";

const CONFIG_KEY = ["auto-discovery", "config"];
const HISTORY_KEY = ["auto-discovery", "history"];

export function useAutoDiscoveryConfig() {
  return useQuery({
    queryKey: CONFIG_KEY,
    queryFn: getAutoDiscoveryConfig,
    staleTime: 30_000,
  });
}

export function useUpdateAutoDiscoveryConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AutoDiscoveryConfigUpdate) =>
      updateAutoDiscoveryConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_KEY });
    },
  });
}

export function useTriggerAutoDiscoveryRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: triggerAutoDiscoveryRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HISTORY_KEY });
      queryClient.invalidateQueries({ queryKey: CONFIG_KEY });
    },
  });
}

export function useAutoDiscoveryHistory(limit = 20) {
  return useQuery({
    queryKey: [...HISTORY_KEY, limit],
    queryFn: () => getAutoDiscoveryHistory(limit),
    staleTime: 30_000,
  });
}
