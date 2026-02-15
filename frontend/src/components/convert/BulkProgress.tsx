import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { BulkStreamState } from "@/hooks/useBulkStream";

interface BulkProgressProps {
  state: BulkStreamState;
  onReset: () => void;
}

const stepLabels: Record<string, string> = {
  starting: "Starting...",
  scraping: "Scraping product...",
  compliance: "Checking compliance...",
  converting: "Converting to eBay...",
  pricing: "Calculating pricing...",
  listing: "Creating listing...",
};

function ItemIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "processing":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
}

export function BulkProgress({ state, onReset }: BulkProgressProps) {
  if (state.phase === "idle") return null;

  const isDone = state.phase === "done" || state.phase === "error";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">
            {state.phase === "streaming"
              ? "Converting..."
              : state.phase === "error"
                ? "Error"
                : `Done — ${state.completed} succeeded, ${state.failed} failed`}
          </CardTitle>
          {isDone && (
            <button
              onClick={onReset}
              className="text-xs text-primary hover:underline"
            >
              Clear
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              {state.completed + state.failed} / {state.total}
            </span>
            <span>{Math.round(state.progressPct)}%</span>
          </div>
          <Progress value={state.progressPct} />
        </div>

        {/* Global error */}
        {state.error && (
          <p className="text-sm text-destructive">{state.error}</p>
        )}

        {/* Item list */}
        <ul className="max-h-64 space-y-1.5 overflow-y-auto">
          {state.items.map((item, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <ItemIcon status={item.status} />
              <span className="min-w-0 flex-1 truncate">{item.url}</span>
              {item.status === "processing" && item.step && (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {stepLabels[item.step] ?? item.step}
                </span>
              )}
              {item.status === "failed" && item.error && (
                <span className="shrink-0 text-xs text-destructive">
                  {item.error}
                </span>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
