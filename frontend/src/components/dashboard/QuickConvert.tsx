import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { convertSingle } from "@/services/conversionService";
import type { ConversionResult } from "@/types/api";

export function QuickConvert() {
  const [url, setUrl] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: convertSingle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recent-conversions"] });
      queryClient.invalidateQueries({ queryKey: ["usage-stats"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
  };

  const result: ConversionResult | undefined = mutation.data;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Quick Convert</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            placeholder="Paste an Amazon or Walmart URL..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={mutation.isPending}
            className="flex-1"
          />
          <Button type="submit" size="sm" disabled={mutation.isPending || !url.trim()}>
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="h-4 w-4" />
            )}
          </Button>
        </form>

        <ErrorAlert error={mutation.error} />

        {result && (
          <div className="rounded-md border p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                {result.draft?.title ?? result.product?.title ?? "Conversion"}
              </span>
              <StatusBadge status={result.status} />
            </div>
            {result.profit && (
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>Price: ${result.profit.sell_price.toFixed(2)}</span>
                <span>Profit: ${result.profit.profit.toFixed(2)}</span>
                <span>Margin: {result.profit.margin_pct.toFixed(1)}%</span>
              </div>
            )}
            {result.error && (
              <p className="text-xs text-destructive">{result.error}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
