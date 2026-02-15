import { useState } from "react";
import { ExternalLink, Link, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { getEbayConnectUrl } from "@/services/authService";

export function EbayConnectionCard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await getEbayConnectUrl();
      window.open(authorization_url, "_blank", "noopener,noreferrer");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to start eBay connection";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

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
        <Button onClick={handleConnect} disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <ExternalLink className="h-4 w-4" />
              Connect eBay Account
            </>
          )}
        </Button>
        <p className="text-xs text-muted-foreground">
          You&apos;ll be redirected to eBay to authorize KonvertIt.
        </p>
      </CardContent>
    </Card>
  );
}
