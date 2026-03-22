import { Link } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { EbayConnectionCard } from "@/components/settings/EbayConnectionCard";
import { AccountForm } from "@/components/settings/AccountForm";
import { BillingCard } from "@/components/settings/BillingCard";
import { PreferencesForm } from "@/components/settings/PreferencesForm";

export function SettingsPage() {
  return (
    <>
      <TopBar title="Settings" />
      <div className="space-y-6 p-6 max-w-2xl">
        <EbayConnectionCard />
        <AccountForm />
        <BillingCard />
        <PreferencesForm />

        {/* Admin access — blends into the footer, only visible if you know to look */}
        <div className="pt-4 text-center">
          <Link
            to="/admin"
            className="text-xs text-muted-foreground/30 hover:text-muted-foreground transition-colors"
          >
            System
          </Link>
        </div>
      </div>
    </>
  );
}
