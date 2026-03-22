import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuthContext } from "@/contexts/AuthContext";
import api from "@/services/apiClient";

export function EmailVerificationBanner() {
  const { user } = useAuthContext();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  if (!user || user.email_verified) return null;

  const handleResend = async () => {
    setSending(true);
    try {
      await api.post("/auth/resend-verification");
      setSent(true);
    } catch {
      // silently fail — rate-limited or server error
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
      <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
        />
      </svg>
      <span className="flex-1">
        Please verify your email address. Check your inbox for the verification link.
      </span>
      {sent ? (
        <span className="text-green-700 dark:text-green-400">Sent!</span>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={handleResend}
          disabled={sending}
          className="shrink-0"
        >
          {sending ? "Sending..." : "Resend"}
        </Button>
      )}
    </div>
  );
}
