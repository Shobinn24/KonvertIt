import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { ProtectedRoute } from "@/components/shared/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ConvertPage } from "@/pages/ConvertPage";
import { ListingsPage } from "@/pages/ListingsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { DiscoverPage } from "@/pages/DiscoverPage";
import { HelpPage } from "@/pages/HelpPage";
import { CheckoutSuccessPage } from "@/pages/CheckoutSuccessPage";
import { TermsPage } from "@/pages/TermsPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { RefundPolicyPage } from "@/pages/RefundPolicyPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";
import { AdminPage } from "@/pages/AdminPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/register",
    element: <RegisterPage />,
  },
  {
    path: "/terms",
    element: <TermsPage />,
  },
  {
    path: "/privacy",
    element: <PrivacyPage />,
  },
  {
    path: "/refund-policy",
    element: <RefundPolicyPage />,
  },
  {
    path: "/verify-email",
    element: <VerifyEmailPage />,
  },
  {
    path: "/admin",
    element: <AdminPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "dashboard", element: <DashboardPage /> },
          { path: "discover", element: <DiscoverPage /> },
          { path: "convert", element: <ConvertPage /> },
          { path: "listings", element: <ListingsPage /> },
          { path: "settings", element: <SettingsPage /> },
          { path: "help", element: <HelpPage /> },
          { path: "billing/success", element: <CheckoutSuccessPage /> },
        ],
      },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
