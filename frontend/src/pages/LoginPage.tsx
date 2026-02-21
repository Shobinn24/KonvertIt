import { Link, Navigate } from "react-router-dom";
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
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex min-h-screen bg-darkBg">
      {/* Branding panel */}
      <div className="relative hidden flex-1 items-center justify-center lg:flex">
        {/* Background glow */}
        <div className="pointer-events-none absolute -top-40 left-1/4 h-[400px] w-[400px] rounded-full bg-accentPurple/15 blur-[120px]" />
        <div className="pointer-events-none absolute bottom-20 right-1/4 h-[300px] w-[300px] rounded-full bg-accentBlue/10 blur-[120px]" />

        <div className="relative max-w-md space-y-6 px-8">
          <img src="/logo.jpg" alt="KonvertIt" className="h-16 w-auto" />
          <p className="text-lg text-muted-foreground">
            Convert Amazon and Walmart products to optimized eBay listings in
            seconds. Automated title optimization, compliance checks, and profit
            calculations.
          </p>
          <Link
            to="/"
            className="inline-block text-sm text-accentBlue hover:underline"
          >
            &larr; Back to home
          </Link>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center p-8">
        <Card className="w-full max-w-md border-darkBorder">
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
