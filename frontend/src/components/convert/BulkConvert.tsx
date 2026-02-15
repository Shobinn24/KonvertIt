import { useState } from "react";
import { Play, Square } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface BulkConvertProps {
  onStart: (urls: string[]) => void;
  onCancel: () => void;
  isStreaming: boolean;
}

export function BulkConvert({ onStart, onCancel, isStreaming }: BulkConvertProps) {
  const [text, setText] = useState("");

  const urls = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const handleStart = () => {
    if (urls.length === 0) return;
    onStart(urls);
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
          placeholder={"https://www.amazon.com/dp/B0...\nhttps://www.walmart.com/ip/..."}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={isStreaming}
          rows={6}
        />
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
