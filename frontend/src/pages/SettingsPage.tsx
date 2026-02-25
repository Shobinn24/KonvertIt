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
      </div>
    </>
  );
}
