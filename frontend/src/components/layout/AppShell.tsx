import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { WebSocketToast } from "@/components/shared/WebSocketToast";
import { EmailVerificationBanner } from "@/components/shared/EmailVerificationBanner";

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-background">
        <EmailVerificationBanner />
        <Outlet />
      </main>
      <WebSocketToast />
    </div>
  );
}
