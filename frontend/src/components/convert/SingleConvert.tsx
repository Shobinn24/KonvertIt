import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { convertSingle } from "@/services/conversionService";
import type { ConversionResult } from "@/types/api";

interface SingleConvertProps {
  onResult: (result: ConversionResult) => void;
}

export function SingleConvert({ onResult }: SingleConvertProps) {
  const [url, setUrl] = useState("");

  const mutation = useMutation({
    mutationFn: convertSingle,
    onSuccess: (result) => onResult(result),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    mutation.mutate(trimmed);
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
        <ErrorAlert error={mutation.error} />
      </CardContent>
    </Card>
  );
}
