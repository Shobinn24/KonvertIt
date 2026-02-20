import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { convertSingle } from "@/services/conversionService";
import type { ConversionResult } from "@/types/api";

interface SingleConvertProps {
  onResult: (result: ConversionResult) => void;
  initialUrl?: string;
}

export function SingleConvert({ onResult, initialUrl = "" }: SingleConvertProps) {
  const [url, setUrl] = useState(initialUrl);

  // Update URL when navigating from Discover page
  useEffect(() => {
    if (initialUrl) setUrl(initialUrl);
  }, [initialUrl]);
  const [publish, setPublish] = useState(false);
  const [sellPrice, setSellPrice] = useState("");

  const mutation = useMutation({
    mutationFn: convertSingle,
    onSuccess: (result) => onResult(result),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    mutation.mutate({
      url: trimmed,
      publish,
      sell_price: sellPrice ? parseFloat(sellPrice) : null,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Single Conversion</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            placeholder="Paste an Amazon or Walmart product URL..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={mutation.isPending}
            className="flex-1"
          />
          <Button type="submit" disabled={mutation.isPending || !url.trim()}>
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Converting...
              </>
            ) : (
              <>
                Convert
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </form>

        {/* Options row */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="publish-toggle"
              checked={publish}
              onCheckedChange={setPublish}
              disabled={mutation.isPending}
            />
            <Label htmlFor="publish-toggle" className="text-sm">
              Publish to eBay
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="sell-price" className="text-sm whitespace-nowrap">
              Sell price
            </Label>
            <Input
              id="sell-price"
              type="number"
              step="0.01"
              min="0"
              placeholder="Auto"
              value={sellPrice}
              onChange={(e) => setSellPrice(e.target.value)}
              disabled={mutation.isPending}
              className="w-28"
            />
          </div>
        </div>

        <ErrorAlert error={mutation.error} />
      </CardContent>
    </Card>
  );
}
