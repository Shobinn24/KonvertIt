import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { useAuthContext } from "@/contexts/AuthContext";
import { getSubscriptionStatus } from "@/services/billingService";
import { CheckCircle2 } from "lucide-react";

const tierLabels: Record<string, string> = {
  free: "Starter",
  pro: "Hustler",
  enterprise: "Enterprise",
};

export function CheckoutSuccessPage() {
  const navigate = useNavigate();
  const { updateUser } = useAuthContext();
  const [newTier, setNewTier] = useState<string | null>(null);

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 5;

    async function pollSubscription() {
      try {
        const status = await getSubscriptionStatus();
        if (status.tier !== "free") {
          setNewTier(status.tier);
          updateUser({ tier: status.tier as "free" | "pro" | "enterprise" });
          return;
        }
      } catch {
        // ignore
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(pollSubscription, 2000);
      }
    }

    pollSubscription();
  }, [updateUser]);

  useEffect(() => {
    // Auto-redirect to settings after 5 seconds
    const timer = setTimeout(() => navigate("/settings"), 5000);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <>
      <TopBar title="Payment Successful" />
      <div className="flex flex-col items-center justify-center gap-6 p-12 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/10">
          <CheckCircle2 className="h-10 w-10 text-emerald-400" />
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-bold">Welcome to {tierLabels[newTier ?? "pro"]}!</h2>
          <p className="text-muted-foreground">
            Your subscription is active. Enjoy your upgraded limits and features.
          </p>
        </div>

        <button
          onClick={() => navigate("/settings")}
          className="btn-glow rounded-lg bg-accentPurple px-6 py-3 text-sm font-semibold text-white"
        >
          Go to Settings
        </button>

        <p className="text-xs text-muted-foreground">
          Redirecting to settings in a few seconds...
        </p>
      </div>
    </>
  );
}
