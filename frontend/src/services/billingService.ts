import api from "./apiClient";

export interface SubscriptionStatus {
  tier: string;
  status: string; // "active" | "past_due" | "canceled" | "none"
  current_period_end: number | null;
  cancel_at_period_end: boolean;
}

export async function createCheckoutSession(
  tier: "pro" | "enterprise",
  successUrl: string,
  cancelUrl: string,
): Promise<string> {
  const res = await api.post<{ checkout_url: string }>("/billing/checkout", {
    tier,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  return res.data.checkout_url;
}

export async function createPortalSession(returnUrl: string): Promise<string> {
  const res = await api.post<{ portal_url: string }>("/billing/portal", {
    return_url: returnUrl,
  });
  return res.data.portal_url;
}

export async function getSubscriptionStatus(): Promise<SubscriptionStatus> {
  const res = await api.get<SubscriptionStatus>("/billing/subscription");
  return res.data;
}
