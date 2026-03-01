import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, ExternalLink, Link, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { getEbayConnectUrl, getEbayStatus } from "@/services/authService";
import { useToast } from "@/hooks/use-toast";

export function EbayConnectionCard() {
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  // Check existing connection status on mount
  useEffect(() => {
    getEbayStatus()
      .then((status) => setConnected(status.connected))
      .catch(() => {}) // Ignore — user may not be connected
      .finally(() => setChecking(false));
  }, []);

  // Handle eBay OAuth callback redirect (?ebay=connected or ?ebay=error)
  useEffect(() => {
    const ebayParam = searchParams.get("ebay");
    if (ebayParam === "connected") {
      setConnected(true);
      toast({
        title: "eBay Connected",
        description: "Your eBay seller account has been connected successfully.",
      });
      // Clean up URL params
      searchParams.delete("ebay");
      setSearchParams(searchParams, { replace: true });
    } else if (ebayParam === "error") {
      const reason = searchParams.get("reason") || "unknown";
      setError(`eBay connection failed: ${reason.replace(/_/g, " ")}`);
      searchParams.delete("ebay");
      searchParams.delete("reason");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, toast]);

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await getEbayConnectUrl();
      // Navigate in same tab — callback will redirect back here
      window.location.href = authorization_url;
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to start eBay connection";
      setError(message);
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link className="h-5 w-5" />
            eBay Connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link className="h-5 w-5" />
          eBay Connection
        </CardTitle>
        <CardDescription>
          Connect your eBay seller account to publish listings directly.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ErrorAlert error={error} />

        {connected ? (
          <div className="flex items-center gap-2 text-green-500">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">eBay account connected</span>
          </div>
        ) : (
          <Button onClick={handleConnect} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Redirecting to eBay...
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4" />
                Connect eBay Account
              </>
            )}
          </Button>
        )}
        <p className="text-xs text-muted-foreground">
          {connected
            ? "Your eBay seller account is linked. Listings will publish to your eBay store."
            : "You\u2019ll be redirected to eBay to authorize KonvertIt."}
        </p>
      </CardContent>
    </Card>
  );
}
