import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, Package, List, AlertTriangle } from "lucide-react";
import { TopBar } from "@/components/layout/TopBar";
import { StatCard } from "@/components/dashboard/StatCard";
import { RateLimitBar } from "@/components/dashboard/RateLimitBar";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { QuickConvert } from "@/components/dashboard/QuickConvert";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { useUsageStats, useRecentConversions } from "@/hooks/useDashboard";
import { useWebSocket } from "@/hooks/useWebSocket";

function sumValues(record: Record<string, number>): number {
  return Object.values(record).reduce((a, b) => a + b, 0);
}

export function DashboardPage() {
  const usage = useUsageStats();
  const recent = useRecentConversions(5);
  const queryClient = useQueryClient();
  const { lastEvent } = useWebSocket();

  // Auto-invalidate React Query caches when WS events arrive
  useEffect(() => {
    if (!lastEvent) return;

    switch (lastEvent.event) {
      case "conversion_complete":
        queryClient.invalidateQueries({ queryKey: ["conversions"] });
        queryClient.invalidateQueries({ queryKey: ["usage-stats"] });
        break;
      case "listing_updated":
        queryClient.invalidateQueries({ queryKey: ["listings"] });
        queryClient.invalidateQueries({ queryKey: ["usage-stats"] });
        break;
      case "price_alert":
        queryClient.invalidateQueries({ queryKey: ["products"] });
        break;
      case "rate_limit_warning":
        queryClient.invalidateQueries({ queryKey: ["usage-stats"] });
        break;
    }
  }, [lastEvent, queryClient]);

  if (usage.isLoading) {
    return (
      <>
        <TopBar title="Dashboard" />
        <div className="flex items-center justify-center p-12">
          <LoadingSpinner size={32} />
        </div>
      </>
    );
  }

  if (usage.error) {
    return (
      <>
        <TopBar title="Dashboard" />
        <div className="p-6">
          <ErrorAlert error={usage.error} />
        </div>
      </>
    );
  }

  const stats = usage.data!;
  const totalConversions = sumValues(stats.conversions);
  const activeListings = stats.listings["active"] ?? 0;
  const failedConversions = stats.conversions["failed"] ?? 0;
  const todayUsed = stats.conversions["completed"] ?? 0;

  return (
    <>
      <TopBar title="Dashboard" />
      <div className="space-y-6 p-6">
        {/* Stat cards row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Conversions"
            value={totalConversions}
            icon={ArrowRightLeft}
            description="All time"
          />
          <StatCard
            title="Active Listings"
            value={activeListings}
            icon={List}
            description="On eBay"
          />
          <StatCard
            title="Total Listings"
            value={sumValues(stats.listings)}
            icon={Package}
            description="Draft + active + ended"
          />
          <StatCard
            title="Failed"
            value={failedConversions}
            icon={AlertTriangle}
            description="Needs attention"
          />
        </div>

        {/* Rate limit bar */}
        <RateLimitBar
          used={todayUsed}
          limit={stats.limits.daily_conversions}
          tier={stats.tier}
        />

        {/* Bottom row: activity + quick convert */}
        <div className="grid gap-6 lg:grid-cols-2">
          <ActivityFeed
            conversions={recent.data?.conversions ?? []}
            isLoading={recent.isLoading}
          />
          <QuickConvert />
        </div>
      </div>
    </>
  );
}
