import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import { useAuthContext } from "@/contexts/AuthContext";
import { updateProfile } from "@/services/userService";

export function AccountForm() {
  const { user, updateUser } = useAuthContext();
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState<string | null>(null);

  const emailMutation = useMutation({
    mutationFn: () => updateProfile({ email }),
    onSuccess: (updated) => {
      updateUser(updated);
      setSuccess("Email updated successfully.");
      setTimeout(() => setSuccess(null), 3000);
    },
  });

  const passwordMutation = useMutation({
    mutationFn: () => updateProfile({ password }),
    onSuccess: () => {
      setPassword("");
      setConfirmPassword("");
      setSuccess("Password updated successfully.");
      setTimeout(() => setSuccess(null), 3000);
    },
  });

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || email === user?.email) return;
    emailMutation.mutate();
  };

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8 || password !== confirmPassword) return;
    passwordMutation.mutate();
  };

  const passwordMismatch =
    confirmPassword.length > 0 && password !== confirmPassword;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>
          Manage your email and password.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {success && (
          <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
            <Check className="h-4 w-4" />
            {success}
          </div>
        )}

        {/* Email */}
        <form onSubmit={handleEmailSubmit} className="space-y-3">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <div className="flex gap-2">
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={emailMutation.isPending}
              className="flex-1"
            />
            <Button
              type="submit"
              size="sm"
              disabled={
                emailMutation.isPending ||
                !email.trim() ||
                email === user?.email
              }
            >
              {emailMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save"
              )}
            </Button>
          </div>
          <ErrorAlert error={emailMutation.error} />
        </form>

        <Separator />

        {/* Password */}
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <label htmlFor="new-password" className="text-sm font-medium">
            New Password
          </label>
          <Input
            id="new-password"
            type="password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={passwordMutation.isPending}
          />
          <Input
            type="password"
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={passwordMutation.isPending}
          />
          {passwordMismatch && (
            <p className="text-xs text-destructive">Passwords don&apos;t match</p>
          )}
          <Button
            type="submit"
            size="sm"
            disabled={
              passwordMutation.isPending ||
              password.length < 8 ||
              password !== confirmPassword
            }
          >
            {passwordMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Change Password"
            )}
          </Button>
          <ErrorAlert error={passwordMutation.error} />
        </form>
      </CardContent>
    </Card>
  );
}
