import { useState, useEffect } from "react";
import { Play, Square } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export interface BulkConvertOptions {
  publish: boolean;
  sellPrice: number | undefined;
}

interface BulkConvertProps {
  onStart: (urls: string[], options: BulkConvertOptions) => void;
  onCancel: () => void;
  isStreaming: boolean;
  initialUrls?: string[];
}

export function BulkConvert({
  onStart,
  onCancel,
  isStreaming,
  initialUrls = [],
}: BulkConvertProps) {
  const [text, setText] = useState(
    initialUrls.length > 0 ? initialUrls.join("\n") : "",
  );
  const [publish, setPublish] = useState(false);
  const [sellPrice, setSellPrice] = useState("");

  // Update text when initialUrls changes (e.g., navigating from Discover)
  useEffect(() => {
    if (initialUrls.length > 0) {
      setText(initialUrls.join("\n"));
    }
  }, [initialUrls.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const urls = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const handleStart = () => {
    if (urls.length === 0) return;
    onStart(urls, {
      publish,
      sellPrice: sellPrice ? parseFloat(sellPrice) : undefined,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Bulk Conversion</CardTitle>
        <CardDescription>
          Paste one URL per line (up to 50). Progress streams in real time.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Textarea
          placeholder={
            "https://www.amazon.com/dp/B0...\nhttps://www.walmart.com/ip/..."
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={isStreaming}
          rows={6}
        />

        {/* Options row */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="bulk-publish-toggle"
              checked={publish}
              onCheckedChange={setPublish}
              disabled={isStreaming}
            />
            <Label htmlFor="bulk-publish-toggle" className="text-sm">
              Publish to eBay
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="bulk-sell-price" className="text-sm whitespace-nowrap">
              Sell price
            </Label>
            <Input
              id="bulk-sell-price"
              type="number"
              step="0.01"
              min="0"
              placeholder="Auto"
              value={sellPrice}
              onChange={(e) => setSellPrice(e.target.value)}
              disabled={isStreaming}
              className="w-28"
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {urls.length} URL{urls.length !== 1 ? "s" : ""} detected
          </span>
          {isStreaming ? (
            <Button variant="destructive" onClick={onCancel}>
              <Square className="h-4 w-4" />
              Cancel
            </Button>
          ) : (
            <Button onClick={handleStart} disabled={urls.length === 0}>
              <Play className="h-4 w-4" />
              Start Bulk Convert
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
