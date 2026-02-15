import { Navigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { useAuthContext } from "@/contexts/AuthContext";

export function RegisterPage() {
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
            Start converting products across marketplaces. Free tier includes 50
            conversions per day and up to 100 active listings.
          </p>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Create an account</CardTitle>
            <CardDescription>Get started with KonvertIt for free</CardDescription>
          </CardHeader>
          <CardContent>
            <RegisterForm />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
