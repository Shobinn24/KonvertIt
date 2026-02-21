import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useRegisterMutation } from "@/hooks/useAuth";
import { registerSchema, type RegisterFormData } from "@/types/api";
import { useAuthContext } from "@/contexts/AuthContext";

export function RegisterForm() {
  const navigate = useNavigate();
  const { login: authLogin } = useAuthContext();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const registerMutation = useRegisterMutation();

  const onSubmit = (data: RegisterFormData) => {
    registerMutation.mutate(
      { email: data.email, password: data.password },
      {
        onSuccess: (res) => {
          authLogin(res.access_token, res.refresh_token, res.user);
          navigate("/dashboard", { replace: true });
        },
      },
    );
  };

  const apiError = registerMutation.error
    ? ((
        registerMutation.error as {
          response?: { data?: { detail?: string } };
        }
      ).response?.data?.detail ?? "Registration failed. Please try again.")
    : null;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          {...register("email")}
        />
        {errors.email && (
          <p className="text-sm text-destructive">{errors.email.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder="Min 8 characters"
          autoComplete="new-password"
          {...register("password")}
        />
        {errors.password && (
          <p className="text-sm text-destructive">{errors.password.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirmPassword">Confirm Password</Label>
        <Input
          id="confirmPassword"
          type="password"
          placeholder="Repeat your password"
          autoComplete="new-password"
          {...register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p className="text-sm text-destructive">
            {errors.confirmPassword.message}
          </p>
        )}
      </div>

      <ErrorAlert error={apiError} />

      <Button
        type="submit"
        className="w-full"
        disabled={registerMutation.isPending}
      >
        {registerMutation.isPending ? (
          <LoadingSpinner size={16} className="mr-2" />
        ) : null}
        Create account
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/login" className="text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
