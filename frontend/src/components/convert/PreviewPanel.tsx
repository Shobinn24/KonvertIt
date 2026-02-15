import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { ConversionResult } from "@/types/api";

interface PreviewPanelProps {
  result: ConversionResult | null;
}

export function PreviewPanel({ result }: PreviewPanelProps) {
  if (!result) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle>Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Convert a product to see the eBay listing preview here.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle>Preview</CardTitle>
          <StatusBadge status={result.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Title */}
        {result.draft?.title && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">eBay Title</p>
            <p className="text-sm font-medium">{result.draft.title}</p>
          </div>
        )}

        {/* Source product */}
        {result.product && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Source Product</p>
            <p className="text-sm">{result.product.title}</p>
            <p className="text-xs text-muted-foreground">
              {result.product.brand} &middot; ${result.product.price.toFixed(2)}
            </p>
          </div>
        )}

        {/* Pricing */}
        {result.profit && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Pricing</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Sell: </span>
                <span className="font-medium">${result.profit.sell_price.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Cost: </span>
                <span>${result.profit.cost.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Profit: </span>
                <span className="font-medium text-green-600">
                  ${result.profit.profit.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Margin: </span>
                <span>{result.profit.margin_pct.toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-muted-foreground">Fees: </span>
                <span>${result.profit.total_fees.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Compliance */}
        {result.compliance && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Compliance</p>
            <StatusBadge status={result.compliance.risk_level} />
            {result.compliance.violations.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {result.compliance.violations.map((v, i) => (
                  <li key={i} className="text-xs text-destructive">
                    {v}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Error */}
        {result.error && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-destructive">Error</p>
            <p className="text-sm text-destructive">{result.error}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
