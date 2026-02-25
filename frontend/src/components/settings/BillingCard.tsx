import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { useAuthContext } from "@/contexts/AuthContext";
import {
  createCheckoutSession,
  createPortalSession,
  getSubscriptionStatus,
} from "@/services/billingService";
import { cn } from "@/lib/utils";
import { CreditCard, ExternalLink, Sparkles } from "lucide-react";

const tierLabels: Record<string, string> = {
  free: "Starter",
  pro: "Hustler",
  enterprise: "Enterprise",
};

const tierPrices: Record<string, string> = {
  free: "Free",
  pro: "$29/mo",
  enterprise: "$99/mo",
};

const tierBadgeColors: Record<string, string> = {
  free: "bg-gray-100 text-gray-700",
  pro: "bg-blue-100 text-blue-700",
  enterprise: "bg-purple-100 text-purple-700",
};

export function BillingCard() {
  const { user } = useAuthContext();
  const [loading, setLoading] = useState<string | null>(null);

  const subscription = useQuery({
    queryKey: ["subscription-status"],
    queryFn: getSubscriptionStatus,
    staleTime: 30_000,
  });

  const handleCheckout = async (tier: "pro" | "enterprise") => {
    setLoading(tier);
    try {
      const origin = window.location.origin;
      const url = await createCheckoutSession(
        tier,
        `${origin}/billing/success`,
        `${origin}/settings`,
      );
      window.location.href = url;
    } catch {
      setLoading(null);
    }
  };

  const handlePortal = async () => {
    setLoading("portal");
    try {
      const url = await createPortalSession(`${window.location.origin}/settings`);
      window.location.href = url;
    } catch {
      setLoading(null);
    }
  };

  const tier = user?.tier ?? "free";
  const isPaid = tier === "pro" || tier === "enterprise";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-accentPurple" />
            <div>
              <CardTitle>Billing & Subscription</CardTitle>
              <CardDescription>Manage your KonvertIt plan</CardDescription>
            </div>
          </div>
          {user && (
            <Badge
              variant="secondary"
              className={cn("text-sm", tierBadgeColors[tier])}
            >
              {tierLabels[tier]} — {tierPrices[tier]}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {subscription.isLoading ? (
          <div className="flex justify-center py-4">
            <LoadingSpinner />
          </div>
        ) : subscription.error ? (
          <ErrorAlert error={subscription.error} />
        ) : isPaid && subscription.data ? (
          /* ── Paid Tier ── */
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Status</span>
              <Badge
                variant="secondary"
                className={cn(
                  "capitalize",
                  subscription.data.status === "active"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-orange-100 text-orange-700",
                )}
              >
                {subscription.data.status}
              </Badge>
            </div>

            {subscription.data.current_period_end && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Next billing</span>
                <span>
                  {new Date(
                    subscription.data.current_period_end * 1000,
                  ).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>
            )}

            {subscription.data.cancel_at_period_end && (
              <p className="text-sm text-orange-500">
                Your subscription will end at the current billing period.
              </p>
            )}

            <Button
              variant="outline"
              className="w-full gap-2"
              onClick={handlePortal}
              disabled={loading === "portal"}
            >
              {loading === "portal" ? (
                <LoadingSpinner />
              ) : (
                <ExternalLink className="h-4 w-4" />
              )}
              Manage Subscription
            </Button>
          </div>
        ) : (
          /* ── Free Tier — Upgrade Options ── */
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              You're on the free Starter plan. Upgrade to unlock more
              conversions, bulk uploads, and priority support.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                onClick={() => handleCheckout("pro")}
                disabled={loading === "pro"}
                className="group relative flex flex-col items-center gap-2 rounded-xl border border-accentPurple/30 bg-darkSurface p-4 text-center transition-all hover:border-accentPurple/60 hover:shadow-lg hover:shadow-accentPurple/10 disabled:opacity-50"
              >
                <Sparkles className="h-5 w-5 text-accentPurple" />
                <span className="text-sm font-semibold">Get Hustler</span>
                <span className="text-2xl font-bold">
                  $29<span className="text-sm font-normal text-muted-foreground">/mo</span>
                </span>
                <span className="text-xs text-muted-foreground">
                  500 conversions/day · Unlimited listings
                </span>
                {loading === "pro" && <LoadingSpinner />}
              </button>

              <button
                onClick={() => handleCheckout("enterprise")}
                disabled={loading === "enterprise"}
                className="group relative flex flex-col items-center gap-2 rounded-xl border border-accentBlue/30 bg-darkSurface p-4 text-center transition-all hover:border-accentBlue/60 hover:shadow-lg hover:shadow-accentBlue/10 disabled:opacity-50"
              >
                <Sparkles className="h-5 w-5 text-accentBlue" />
                <span className="text-sm font-semibold">Get Enterprise</span>
                <span className="text-2xl font-bold">
                  $99<span className="text-sm font-normal text-muted-foreground">/mo</span>
                </span>
                <span className="text-xs text-muted-foreground">
                  Unlimited everything · API access
                </span>
                {loading === "enterprise" && <LoadingSpinner />}
              </button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
