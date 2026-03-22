import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "@/contexts/AuthContext";
import * as authService from "@/services/authService";

export function useLoginMutation() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authService.login(email, password),
  });
}

export function useRegisterMutation() {
  return useMutation({
    mutationFn: (params: {
      firstName: string;
      lastName: string;
      email: string;
      password: string;
      city?: string;
      state?: string;
      country?: string;
      postalCode?: string;
      recaptchaToken?: string | null;
      website?: string;
    }) => authService.register(params),
  });
}

export function useLogout() {
  const { logout } = useAuthContext();
  const navigate = useNavigate();

  return () => {
    logout();
    navigate("/login", { replace: true });
  };
}
