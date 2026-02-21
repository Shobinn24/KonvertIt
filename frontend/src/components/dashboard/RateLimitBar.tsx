import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface RateLimitBarProps {
  used: number;
  limit: number;
  tier: string;
}

const tierColors: Record<string, string> = {
  free: "bg-darkBorder text-gray-300",
  pro: "bg-accentBlue/20 text-accentBlue",
  enterprise: "bg-accentPurple/20 text-accentPurple",
};

export function RateLimitBar({ used, limit, tier }: RateLimitBarProps) {
  const isUnlimited = limit === -1;
  const pct = isUnlimited ? 0 : limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isHigh = pct >= 80;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">
            Daily Conversion Quota
          </CardTitle>
          <Badge
            variant="secondary"
            className={cn("text-xs capitalize", tierColors[tier])}
          >
            {tier}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {isUnlimited ? (
          <p className="text-sm text-muted-foreground">
            Unlimited conversions ({used} used today)
          </p>
        ) : (
          <>
            <div className="flex items-center justify-between text-sm">
              <span className={cn(isHigh && "font-medium text-destructive")}>
                {used} / {limit} used
              </span>
              <span className="text-muted-foreground">
                {limit - used} remaining
              </span>
            </div>
            <Progress value={pct} className={cn(isHigh && "[&>div]:bg-destructive")} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
