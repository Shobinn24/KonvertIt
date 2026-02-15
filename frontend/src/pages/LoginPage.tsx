import { Navigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LoginForm } from "@/components/auth/LoginForm";
import { useAuthContext } from "@/contexts/AuthContext";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen">
      {/* Branding panel */}
      <div className="hidden flex-1 items-center justify-center bg-primary/5 lg:flex">
        <div className="max-w-md space-y-4 px-8">
          <h1 className="text-4xl font-bold tracking-tight">
            Konvert<span className="text-primary">It</span>
          </h1>
          <p className="text-lg text-muted-foreground">
            Convert Amazon and Walmart products to optimized eBay listings in
            seconds. Automated title optimization, compliance checks, and profit
            calculations.
          </p>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome back</CardTitle>
            <CardDescription>
              Sign in to your KonvertIt account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
