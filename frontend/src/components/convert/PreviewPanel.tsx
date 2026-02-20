import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@/lib/utils";
import type { ConversionResult } from "@/types/api";

interface PreviewPanelProps {
  result: ConversionResult | null;
}

export function PreviewPanel({ result }: PreviewPanelProps) {
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);

  // Reset selected image when result changes
  useEffect(() => {
    setSelectedImageIndex(0);
  }, [result]);

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

  const images = result.product?.image_urls ?? [];

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle>Preview</CardTitle>
          <StatusBadge status={result.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Product Images */}
        {images.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              Images ({images.length})
            </p>
            {/* Main image */}
            <div className="overflow-hidden rounded-md border bg-gray-50">
              <img
                src={images[selectedImageIndex] ?? images[0]}
                alt={result.product?.title ?? "Product"}
                className="mx-auto h-48 w-auto object-contain p-2"
              />
            </div>
            {/* Thumbnails */}
            {images.length > 1 && (
              <div className="flex gap-1 overflow-x-auto pb-1">
                {images.slice(0, 8).map((url, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedImageIndex(i)}
                    className={cn(
                      "flex-shrink-0 h-12 w-12 overflow-hidden rounded border p-0.5 transition-colors",
                      selectedImageIndex === i
                        ? "border-primary ring-1 ring-primary"
                        : "border-gray-200 hover:border-gray-400"
                    )}
                  >
                    <img
                      src={url}
                      alt={`Product image ${i + 1}`}
                      className="h-full w-full object-contain"
                    />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

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
