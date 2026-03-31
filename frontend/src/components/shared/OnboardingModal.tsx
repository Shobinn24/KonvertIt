import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Plug, RotateCcw, Sparkles, ArrowRight } from "lucide-react";
import { useAuthContext } from "@/contexts/AuthContext";

const STORAGE_KEY_PREFIX = "konvertit_onboarding_seen_";

function getStorageKey(userId: string) {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

const steps = [
  {
    icon: Plug,
    title: "Connect Your eBay Account",
    description:
      "Go to Settings → eBay Account and click Connect. KonvertIt uses eBay's secure OAuth — your password is never stored.",
  },
  {
    icon: RotateCcw,
    title: "Set Up Your Business Policies",
    description:
      "Create your Shipping, Returns, and Payment policies in eBay, then paste the Policy IDs into Settings. You only do this once.",
  },
  {
    icon: Sparkles,
    title: "Turn On Auto-Discovery",
    description:
      "Head to Auto-Discover, toggle it ON, and set your minimum profit margin. KonvertIt will automatically find and convert profitable products for you every day.",
  },
];

export function OnboardingModal() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!user || !user.email_verified) return;

    const key = getStorageKey(user.id);
    const alreadySeen = localStorage.getItem(key);
    if (!alreadySeen) {
      setOpen(true);
    }
  }, [user]);

  const dismiss = () => {
    if (user) {
      localStorage.setItem(getStorageKey(user.id), "true");
    }
    setOpen(false);
  };

  const handleGetStarted = () => {
    dismiss();
    navigate("/settings");
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) dismiss(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">
            Welcome to{" "}
            <span className="text-accentPurple">KonvertIt</span> 🎉
          </DialogTitle>
          <p className="text-sm text-muted-foreground pt-1">
            You're three steps away from your first automated eBay listing.
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={i} className="flex gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accentPurple/10">
                  <Icon className="h-4 w-4 text-accentPurple" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    {i + 1}. {step.title}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col gap-2 pt-2">
          <Button onClick={handleGetStarted} className="w-full gap-2">
            Go to Settings <ArrowRight className="h-4 w-4" />
          </Button>
          <Button variant="ghost" onClick={dismiss} className="w-full text-muted-foreground">
            I'll explore on my own
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
