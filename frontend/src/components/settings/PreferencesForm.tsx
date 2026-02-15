import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { useUsageStats } from "@/hooks/useDashboard";
import { useAuthContext } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const tierColors: Record<string, string> = {
  free: "bg-gray-100 text-gray-700",
  pro: "bg-blue-100 text-blue-700",
  enterprise: "bg-purple-100 text-purple-700",
};

function sumValues(record: Record<string, number>): number {
  return Object.values(record).reduce((a, b) => a + b, 0);
}

function LimitRow({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number;
}) {
  const isUnlimited = limit === -1;
  const pct = isUnlimited ? 0 : limit > 0 ? Math.min((used / limit) * 100, 100) : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="text-muted-foreground">
          {isUnlimited ? `${used} (unlimited)` : `${used} / ${limit}`}
        </span>
      </div>
      {!isUnlimited && <Progress value={pct} />}
    </div>
  );
}

export function PreferencesForm() {
  const { user } = useAuthContext();
  const usage = useUsageStats();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Plan &amp; Usage</CardTitle>
            <CardDescription>
              Your current tier and resource usage.
            </CardDescription>
          </div>
          {user && (
            <Badge
              variant="secondary"
              className={cn("text-sm capitalize", tierColors[user.tier])}
            >
              {user.tier}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {usage.isLoading ? (
          <div className="flex justify-center py-4">
            <LoadingSpinner />
          </div>
        ) : usage.error ? (
          <ErrorAlert error={usage.error} />
        ) : usage.data ? (
          <>
            <LimitRow
              label="Daily Conversions"
              used={usage.data.conversions["completed"] ?? 0}
              limit={usage.data.limits.daily_conversions}
            />
            <LimitRow
              label="Total Listings"
              used={sumValues(usage.data.listings)}
              limit={usage.data.limits.max_listings}
            />
          </>
        ) : null}

        {user && (
          <div className="space-y-1 pt-2 text-xs text-muted-foreground">
            {user.created_at && (
              <p>
                Member since{" "}
                {new Date(user.created_at).toLocaleDateString("en-US", {
                  month: "long",
                  year: "numeric",
                })}
              </p>
            )}
            {user.last_login && (
              <p>
                Last login{" "}
                {new Date(user.last_login).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
