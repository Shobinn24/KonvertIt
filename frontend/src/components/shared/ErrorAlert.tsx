import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface ErrorAlertProps {
  error: Error | string | null;
  className?: string;
}

export function ErrorAlert({ error, className }: ErrorAlertProps) {
  if (!error) return null;

  const message = typeof error === "string" ? error : error.message;

  return (
    <Alert variant="destructive" className={className}>
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
