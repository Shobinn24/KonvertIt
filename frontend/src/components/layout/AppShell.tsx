import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { WebSocketToast } from "@/components/shared/WebSocketToast";
import { EmailVerificationBanner } from "@/components/shared/EmailVerificationBanner";
import { OnboardingModal } from "@/components/shared/OnboardingModal";

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-background">
        <EmailVerificationBanner />
        <Outlet />
      </main>
      <WebSocketToast />
      <OnboardingModal />
    </div>
  );
}
