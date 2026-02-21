import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthContext } from "@/contexts/AuthContext";
import { LoadingSpinner } from "./LoadingSpinner";

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuthContext();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname || "/dashboard" }} replace />;
  }

  return <Outlet />;
}
