import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import {
  useAutoDiscoveryConfig,
  useUpdateAutoDiscoveryConfig,
  useTriggerAutoDiscoveryRun,
  useAutoDiscoveryHistory,
} from "@/hooks/useAutoDiscovery";

export function AutoDiscoverPage() {
  const { data: config, isLoading } = useAutoDiscoveryConfig();
  const updateConfig = useUpdateAutoDiscoveryConfig();
  const triggerRun = useTriggerAutoDiscoveryRun();
  const { data: history } = useAutoDiscoveryHistory();

  const [minMargin, setMinMargin] = useState<string>("");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <>
        <TopBar title="Auto-Discovery" />
        <div className="p-6">
          <p className="text-muted-foreground">Loading configuration...</p>
        </div>
      </>
    );
  }

  const handleToggle = (enabled: boolean) => {
    updateConfig.mutate({ enabled });
  };

  const handleAutoPublishToggle = (auto_publish: boolean) => {
    updateConfig.mutate({ auto_publish });
  };

  const handleMarginSave = () => {
    const pct = parseFloat(minMargin);
    if (!isNaN(pct) && pct >= 5 && pct <= 80) {
      updateConfig.mutate({ min_margin_pct: pct / 100 });
    }
  };

  const handleMaxItemsChange = (value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num >= 1 && num <= 50) {
      updateConfig.mutate({ max_daily_items: num });
    }
  };

  return (
    <>
      <TopBar title="Auto-Discovery" />
      <div className="space-y-6 p-6">
        {/* Top section: settings cards constrained to readable width */}
        <div className="max-w-3xl space-y-6">
        {/* Master Toggle */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Auto-Discovery</span>
              <div className="flex items-center gap-3">
                <Badge variant={config?.enabled ? "default" : "secondary"}>
                  {config?.enabled ? "Active" : "Inactive"}
                </Badge>
                <Switch
                  checked={config?.enabled ?? false}
                  onCheckedChange={handleToggle}
                  disabled={updateConfig.isPending}
                />
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              When enabled, KonvertIt automatically scans eBay for trending
              products, finds them on Amazon &amp; Walmart at lower prices, and
              converts profitable matches into listings for you — daily.
            </p>
          </CardContent>
        </Card>

        {/* Settings */}
        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Auto-Publish Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">
                  Auto-Publish to eBay
                </Label>
                <p className="text-xs text-muted-foreground mt-1">
                  When off, products are saved as drafts for your review.
                </p>
              </div>
              <Switch
                checked={config?.auto_publish ?? false}
                onCheckedChange={handleAutoPublishToggle}
                disabled={updateConfig.isPending}
              />
            </div>

            {/* Min Margin */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Minimum Profit Margin
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={5}
                  max={80}
                  placeholder={String(
                    Math.round((config?.min_margin_pct ?? 0.2) * 100)
                  )}
                  value={minMargin}
                  onChange={(e) => setMinMargin(e.target.value)}
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">%</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleMarginSave}
                  disabled={!minMargin || updateConfig.isPending}
                >
                  Save
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Only convert products with at least this profit margin after eBay
                fees.
              </p>
            </div>

            {/* Max Daily Items */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Max Items Per Day</Label>
              <Select
                value={String(config?.max_daily_items ?? 10)}
                onValueChange={handleMaxItemsChange}
                disabled={updateConfig.isPending}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[5, 10, 15, 20, 30, 50].map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n} items
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Maximum number of products to auto-convert each day.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Manual Run */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Run Now</span>
              {config?.last_run_at && (
                <span className="text-xs font-normal text-muted-foreground">
                  Last run:{" "}
                  {new Date(config.last_run_at).toLocaleString()}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => triggerRun.mutate()}
              disabled={triggerRun.isPending}
            >
              {triggerRun.isPending
                ? "Scanning..."
                : "Trigger Discovery Scan"}
            </Button>
            {triggerRun.data && (
              <div className="mt-4 rounded-md border p-4 text-sm space-y-1">
                <p>
                  <strong>Source:</strong>{" "}
                  {triggerRun.data.data_source === "marketplace_insights"
                    ? "eBay Sold Data"
                    : "Your Conversion History"}
                </p>
                <p>
                  <strong>Queries:</strong>{" "}
                  {triggerRun.data.queries_searched.join(", ") || "None"}
                </p>
                <p>
                  <strong>Evaluated:</strong>{" "}
                  {triggerRun.data.products_evaluated} products
                </p>
                <p>
                  <strong>Converted:</strong>{" "}
                  {triggerRun.data.products_converted} products
                </p>
                {triggerRun.data.errors > 0 && (
                  <p className="text-destructive">
                    <strong>Errors:</strong> {triggerRun.data.errors}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
        </div>{/* end max-w-3xl settings section */}

        {/* Run History — full width */}
        {history && history.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Run History</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-6" />
                    <TableHead>Date</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="text-right">Evaluated</TableHead>
                    <TableHead className="text-right">Converted</TableHead>
                    <TableHead className="text-right">Skipped</TableHead>
                    <TableHead className="text-right">Errors</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((run) => {
                    const isExpanded = expandedRunId === run.id;
                    const hasProducts = run.converted_product_details?.length > 0;
                    return (
                      <>
                        <TableRow
                          key={run.id}
                          className={hasProducts ? "cursor-pointer hover:bg-muted/40" : ""}
                          onClick={() =>
                            hasProducts
                              ? setExpandedRunId(isExpanded ? null : run.id)
                              : undefined
                          }
                        >
                          <TableCell className="pl-3">
                            {hasProducts ? (
                              isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )
                            ) : null}
                          </TableCell>
                          <TableCell className="text-xs">
                            {new Date(run.run_at).toLocaleDateString()}{" "}
                            {new Date(run.run_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                run.data_source === "marketplace_insights"
                                  ? "default"
                                  : "secondary"
                              }
                            >
                              {run.data_source === "marketplace_insights"
                                ? "eBay Data"
                                : "History"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            {run.products_evaluated}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {run.products_converted}
                          </TableCell>
                          <TableCell className="text-right text-muted-foreground">
                            {run.products_skipped_duplicate +
                              run.products_skipped_compliance +
                              run.products_skipped_margin}
                          </TableCell>
                          <TableCell className="text-right">
                            {run.errors > 0 ? (
                              <span className="text-destructive">{run.errors}</span>
                            ) : (
                              <span className="text-muted-foreground">0</span>
                            )}
                          </TableCell>
                        </TableRow>

                        {/* Expanded product details */}
                        {isExpanded && hasProducts && (
                          <TableRow key={`${run.id}-details`}>
                            <TableCell colSpan={7} className="bg-muted/20 p-0">
                              <div className="px-6 py-3 space-y-2">
                                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                                  Converted Products
                                </p>
                                {run.converted_product_details.map((product, i) => (
                                  <div
                                    key={i}
                                    className="flex items-center justify-between rounded-lg border border-darkBorder bg-darkSurface px-4 py-3"
                                  >
                                    <div className="flex-1 min-w-0 pr-4">
                                      <p className="text-sm font-medium truncate">
                                        {product.title}
                                      </p>
                                      <p className="text-xs text-muted-foreground mt-0.5">
                                        {product.marketplace} · Cost ${product.source_price.toFixed(2)} → Sell ${product.sell_price.toFixed(2)} · {product.margin_pct.toFixed(1)}% margin
                                      </p>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                      <Badge
                                        variant={product.published ? "default" : "secondary"}
                                        className="text-xs"
                                      >
                                        {product.published ? "Published" : "Draft"}
                                      </Badge>
                                      {product.ebay_item_id && (
                                        <a
                                          href={`https://www.ebay.com/itm/${product.ebay_item_id}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-xs text-accentBlue hover:underline flex items-center gap-1"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          View on eBay <ExternalLink className="h-3 w-3" />
                                        </a>
                                      )}
                                      <a
                                        href={product.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        Source <ExternalLink className="h-3 w-3" />
                                      </a>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
