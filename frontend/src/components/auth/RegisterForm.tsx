import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useRegisterMutation } from "@/hooks/useAuth";
import { useRecaptcha } from "@/hooks/useRecaptcha";
import { registerSchema, type RegisterFormData } from "@/types/api";
import { useAuthContext } from "@/contexts/AuthContext";

export function RegisterForm() {
  const navigate = useNavigate();
  const { login: authLogin } = useAuthContext();
  // Honeypot state — hidden from real users, bots auto-fill it
  const [website, setWebsite] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const registerMutation = useRegisterMutation();
  const { execute: executeRecaptcha } = useRecaptcha();

  const onSubmit = async (data: RegisterFormData) => {
    const recaptchaToken = await executeRecaptcha("register");
    registerMutation.mutate(
      {
        firstName: data.firstName,
        lastName: data.lastName,
        email: data.email,
        password: data.password,
        city: data.city,
        state: data.state,
        country: data.country,
        postalCode: data.postalCode,
        recaptchaToken,
        website,
      },
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
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="firstName">First name</Label>
          <Input
            id="firstName"
            type="text"
            placeholder="Jane"
            autoComplete="given-name"
            {...register("firstName")}
          />
          {errors.firstName && (
            <p className="text-sm text-destructive">{errors.firstName.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="lastName">Last name</Label>
          <Input
            id="lastName"
            type="text"
            placeholder="Doe"
            autoComplete="family-name"
            {...register("lastName")}
          />
          {errors.lastName && (
            <p className="text-sm text-destructive">{errors.lastName.message}</p>
          )}
        </div>
      </div>

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

      {/* Location (optional) */}
      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs">Location (optional)</Label>
        <div className="grid grid-cols-2 gap-3">
          <Input
            placeholder="City"
            autoComplete="address-level2"
            {...register("city")}
          />
          <Input
            placeholder="State"
            autoComplete="address-level1"
            {...register("state")}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input
            placeholder="Postal code"
            autoComplete="postal-code"
            {...register("postalCode")}
          />
          <Input
            placeholder="US"
            maxLength={2}
            autoComplete="country"
            {...register("country")}
          />
        </div>
      </div>

      {/* Honeypot — hidden from real users via CSS, bots auto-fill it */}
      <div className="absolute -left-[9999px] opacity-0" aria-hidden="true">
        <label htmlFor="website">Website</label>
        <input
          id="website"
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
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
