import { TopBar } from "@/components/layout/TopBar";
import {
  Settings,
  Truck,
  RotateCcw,
  CreditCard,
  MapPin,
  LayoutList,
  BarChart3,
  Package,
  ShoppingCart,
  ArrowRight,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";

/* ─── Reusable Components ─── */

function SectionCard({
  icon: Icon,
  number,
  title,
  children,
}: {
  icon: React.ElementType;
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-darkBorder bg-darkSurface p-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accentPurple/10 text-sm font-bold text-accentPurple">
          {number}
        </div>
        <Icon className="h-5 w-5 text-accentPurple" />
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <div className="space-y-3 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

function StepList({ steps }: { steps: string[] }) {
  return (
    <ol className="list-inside list-decimal space-y-2">
      {steps.map((step, i) => (
        <li key={i}>{step}</li>
      ))}
    </ol>
  );
}

function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-accentPurple/5 p-3 text-sm">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-accentPurple" />
      <span>{children}</span>
    </div>
  );
}

function Warning({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-orange-500/10 p-3 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-orange-400" />
      <span>{children}</span>
    </div>
  );
}

/* ─── Main Help Page ─── */

export function HelpPage() {
  return (
    <>
      <TopBar title="Help & Setup Guide" />
      <div className="max-w-3xl space-y-8 p-6">
        {/* Intro */}
        <div>
          <h2 className="text-2xl font-bold">
            Getting Started with{" "}
            <span className="text-accentPurple">KonvertIt</span>
          </h2>
          <p className="mt-2 text-muted-foreground">
            Follow these steps to set up your eBay seller account for automated
            listings. Once configured, KonvertIt can push converted products
            directly to your store.
          </p>
        </div>

        {/* ── Section 1: Selling Preferences ── */}
        <SectionCard icon={Settings} number={1} title="Dial in Your Selling Preferences">
          <StepList
            steps={[
              "In eBay, click your avatar/name \u2192 Account settings.",
              "Open Selling preferences.",
              "Automated Feedback \u2192 Edit \u2192 On \u2192 Save.",
              "Return preferences \u2192 Edit \u2192 enable RMA number.",
            ]}
          />
          <p className="mt-2 font-medium text-foreground">Turn On:</p>
          <ul className="list-inside list-disc space-y-1">
            <li>
              <strong>Listings stay active when you're out of stock</strong> — prevents ended
              listings when quantity hits 0.
            </li>
            <li>
              <strong>Show buyers the exact quantity available</strong> — social proof + urgency.
            </li>
          </ul>
          <Tip>
            These switches reduce manual work, keep URLs alive for SEO/history,
            and increase buyer trust.
          </Tip>
        </SectionCard>

        {/* ── Section 2: Shipping & Business Policies ── */}
        <SectionCard icon={Truck} number={2} title="Shipping Preferences + Business Policies">
          <StepList
            steps={[
              "In Account settings, open Shipping preferences.",
              "Set Request buyer's phone number \u2192 Yes (useful for carrier issues and freight-sized items).",
              "Go back to Account settings \u2192 Business policies.",
            ]}
          />
          <Warning>
            If you don't see Business policies, eBay may prompt you to opt
            in — do it once and it stays on.
          </Warning>
          <p>
            You'll create three policies: <strong>Shipping</strong>,{" "}
            <strong>Returns</strong>, <strong>Payment</strong>.
          </p>
          <p className="text-xs">
            Manage at:{" "}
            <a
              href="https://www.ebay.com/bp/manage"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accentBlue hover:underline"
            >
              ebay.com/bp/manage <ExternalLink className="mb-0.5 inline h-3 w-3" />
            </a>
          </p>
          <Tip>
            Policies let KonvertIt attach the right rules to each listing
            automatically. Copy the policy IDs into your Settings page once
            created.
          </Tip>
        </SectionCard>

        {/* ── Section 3: Shipping Policy ── */}
        <SectionCard icon={Package} number={3} title="Create Your Shipping Policy (Contiguous US)">
          <p className="font-medium text-foreground">
            Goal: Fast, predictable shipping windows that match supplier
            performance.
          </p>
          <StepList
            steps={[
              'Create policy \u2192 Shipping.',
              'Policy name: US-Contig-Flat-2Biz (use names you\'ll recognize in bulk).',
              'Domestic services: Standard shipping with Flat cost type.',
              'Primary service: USPS Priority Mail (1\u20134 business days) or UPS Ground.',
              'Price: start with Free shipping for best conversion on BIN listings.',
              'Handling time: 2 business days (safe with most supplier-direct flows).',
              'Ship-to: United States.',
              'Exclude locations: Alaska/Hawaii and US Protectorates (PR, GU, VI).',
            ]}
          />
          <Tip>
            If your catalog includes heavier/bulky items, duplicate this policy
            as <code className="rounded bg-darkBorder px-1">US-Contig-Calc-2Biz</code>{" "}
            and use Calculated rates with UPS/FedEx ground. Keep one Economy
            (5-8 business days) policy in reserve for slower suppliers.
          </Tip>
        </SectionCard>

        {/* ── Section 4: Return Policy ── */}
        <SectionCard icon={RotateCcw} number={4} title="Create Your Return Policy">
          <p className="font-medium text-foreground">
            Option A: Conversion-Focused (recommended if margins allow)
          </p>
          <ul className="list-inside list-disc space-y-1">
            <li>Accept returns: 30 days</li>
            <li>Who pays return shipping: Seller (Free returns)</li>
            <li>Refund method: Money back</li>
            <li>
              Policy name:{" "}
              <code className="rounded bg-darkBorder px-1">Returns-30D-Free</code>
            </li>
          </ul>
          <p className="mt-3 font-medium text-foreground">
            Option B: Margin-Protect (common for supplier-direct)
          </p>
          <ul className="list-inside list-disc space-y-1">
            <li>Accept returns: 30 days</li>
            <li>
              Who pays: Buyer for remorse/changed mind; Seller if SNAD/defect
            </li>
            <li>Refund method: Money back</li>
            <li>
              Policy name:{" "}
              <code className="rounded bg-darkBorder px-1">Returns-30D-BuyerPays</code>
            </li>
          </ul>
          <Tip>
            Free returns can lift conversion and help with seller protections on
            many categories. If your niche is low-margin, use Option B.
          </Tip>
        </SectionCard>

        {/* ── Section 5: Payment Policy ── */}
        <SectionCard icon={CreditCard} number={5} title="Create Your Payment Policy">
          <StepList
            steps={[
              "Create policy \u2192 Payment.",
              "Policy name: Payment-Immediate.",
              "Immediate payment required: On (applies to Buy It Now).",
              "Save.",
            ]}
          />
          <Tip>
            Cuts down on unpaid orders and speeds up auto-fulfillment.
          </Tip>
        </SectionCard>

        {/* ── Section 6: Shopping Location ── */}
        <SectionCard icon={MapPin} number={6} title="Set Your Shopping (Viewing) Location">
          <StepList
            steps={[
              'Search any item (e.g., "book").',
              "Click Update your shipping location in the results header.",
              "Choose your country and enter a valid ZIP.",
              "Apply.",
            ]}
          />
          <Tip>
            Ensures you see accurate ETAs/rates while researching and
            spot-checking listings.
          </Tip>
        </SectionCard>

        {/* ── Section 7: Listing Page Display ── */}
        <SectionCard icon={LayoutList} number={7} title="Customize Your Listing Page Display">
          <StepList
            steps={[
              "Click the \u22EF menu (top right) \u2192 Customise.",
              "Enable: Seller information, Item number.",
              "Apply changes.",
            ]}
          />
          <Tip>
            Item numbers are handy for support, spreadsheets, and bulk actions.
          </Tip>
        </SectionCard>

        {/* ── Section 8: Seller Hub Table ── */}
        <SectionCard icon={BarChart3} number={8} title="Optimize Your Seller Hub Table View">
          <StepList
            steps={[
              "Go to Seller Hub \u2192 Listings.",
              "Customise table \u2192 enable the columns listed below.",
              "Save.",
            ]}
          />
          <p className="font-medium text-foreground">Enable these columns:</p>
          <ul className="list-inside list-disc space-y-1">
            <li>Item specifics</li>
            <li>Custom label (SKU)</li>
            <li>Item number</li>
            <li>Available quantity</li>
            <li>Sold</li>
            <li>Price</li>
            <li>Start date</li>
            <li>End date</li>
          </ul>
          <Tip>
            This view shows the levers that matter for automation, stock control,
            and aging.
          </Tip>
        </SectionCard>

        {/* ── Divider ── */}
        <div className="gradient-line h-px w-full" />

        {/* ── Fulfillment Section ── */}
        <div>
          <h2 className="text-2xl font-bold">
            Fulfillment <span className="text-accentPurple">Methods</span>
          </h2>
          <p className="mt-2 text-muted-foreground">
            Choose the fulfillment method that fits your operation. Most sellers
            start with direct-from-Amazon shipping and graduate to self-shipping
            as volume grows.
          </p>
        </div>

        {/* Method A: Ship Direct */}
        <div className="rounded-xl border border-accentBlue/30 bg-darkSurface p-6">
          <div className="mb-4 flex items-center gap-3">
            <ShoppingCart className="h-5 w-5 text-accentBlue" />
            <h3 className="text-lg font-semibold">
              Method A: Ship Direct from Amazon{" "}
              <span className="text-accentBlue">(Fastest to Scale)</span>
            </h3>
          </div>
          <div className="mb-4 grid gap-2 sm:grid-cols-2">
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> No handling or storage
              </div>
              <div className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Fastest operationally
              </div>
            </div>
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-1.5 text-orange-400">
                <AlertTriangle className="h-3.5 w-3.5" /> Buyer may see Amazon packaging
              </div>
              <div className="flex items-center gap-1.5 text-orange-400">
                <AlertTriangle className="h-3.5 w-3.5" /> Policy risk if buyers complain
              </div>
            </div>
          </div>
          <div className="space-y-3 text-sm text-muted-foreground">
            <StepList
              steps={[
                "Place order on Amazon to buyer's address (match variant, ensure ETA meets your eBay handling time).",
                "Select speed that beats your listing promise; add gift receipt/no price.",
                "Send ETA message to buyer on eBay.",
                "Inject tracking once available; monitor first scan.",
              ]}
            />
          </div>
        </div>

        {/* Method B: Self-Ship */}
        <div className="rounded-xl border border-darkBorder bg-darkSurface p-6">
          <div className="mb-4 flex items-center gap-3">
            <Truck className="h-5 w-5 text-accentPurple" />
            <h3 className="text-lg font-semibold">
              Method B: Ship to Your Home, Then Re-Ship{" "}
              <span className="text-accentPurple">(Maximum Control)</span>
            </h3>
          </div>
          <div className="mb-4 grid gap-2 sm:grid-cols-2">
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Inspect personally; add branding
              </div>
              <div className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Flex for odd sizes/fragile/kits
              </div>
            </div>
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-1.5 text-orange-400">
                <AlertTriangle className="h-3.5 w-3.5" /> Time-intensive daily workflow
              </div>
              <div className="flex items-center gap-1.5 text-orange-400">
                <AlertTriangle className="h-3.5 w-3.5" /> Double shipping reduces margin
              </div>
            </div>
          </div>
          <div className="space-y-3 text-sm text-muted-foreground">
            <StepList
              steps={[
                "Stock core supplies: 4\u00D76 thermal printer, boxes, poly mailers, bubble, tape, scale.",
                "Receive & QC the item (photos if high value).",
                "Pack in neutral packaging; add thank-you card/QR if you want.",
                "Buy label (eBay label, Pirate Ship, or Shippo).",
                "Upload tracking; schedule carrier pickup.",
                "File/organize receipts for COGS.",
                "Track first scan and delivery; message if delayed.",
              ]}
            />
          </div>
        </div>

        {/* ── Divider ── */}
        <div className="gradient-line h-px w-full" />

        {/* ── Amazon to eBay Fulfillment Guide ── */}
        <div>
          <h2 className="text-2xl font-bold">
            Amazon to eBay Fulfillment{" "}
            <span className="text-accentPurple">Step-by-Step</span>
          </h2>
          <p className="mt-2 text-muted-foreground">
            When a buyer purchases on eBay, follow these 10 steps to fulfill the
            order via Amazon.
          </p>
        </div>

        <div className="space-y-4">
          {[
            {
              title: "Find the eBay Order",
              text: "Go to your Seller Hub on eBay and view the order to see which item was purchased.",
            },
            {
              title: "Head to Amazon",
              text: "Go to your PERSONAL Amazon.com buying account (not your business account).",
              tip: "Option 1 (Fastest): Copy/paste the item title from the eBay listing into the Amazon search bar. Option 2: KonvertIt inserts the ASIN into the eBay listing SKU \u2014 copy the ASIN and search directly.",
            },
            {
              title: "Locate the Exact Item",
              text: "Validate the item matches what you sold on eBay. If sold out or price changed, find a similar item. If no match exists, message the buyer about alternatives.",
            },
            {
              title: "Copy Item + Buyer Info",
              text: "Go back to the eBay order and copy the buyer's name and shipping address.",
            },
            {
              title: "Proceed to Checkout",
              text: 'Click "Proceed to Checkout" on the Amazon cart page, then change the Shipping Address.',
            },
            {
              title: "Add a New Delivery Address",
              text: "Add a new delivery address using your buyer's shipping details from eBay.",
            },
            {
              title: "Input the Shipping Address Correctly",
              text: "Go back to eBay and input the buyer's exact shipping address.",
              warning: 'Keep your OWN phone number in the phone number field. Uncheck "Make this my default address."',
            },
            {
              title: "Choose Shipping + Double Check",
              text: "Select the shipping option that fits your eBay delivery window. Double-check the buyer's address one more time.",
            },
            {
              title: "Add Tracking on eBay",
              text: 'Once you receive the tracking number from Amazon, go to the eBay order and click "Add Tracking." If it\'s a standard carrier (USPS, FedEx, UPS), enter it directly.',
            },
            {
              title: "Convert the Tracking Number",
              text: 'If the tracking number starts with TBA (Amazon\'s logistics) \u2014 which is 95% of cases \u2014 you must convert it to an eBay-accepted tracking number.',
            },
          ].map((step, i) => (
            <div
              key={i}
              className="flex gap-4 rounded-xl border border-darkBorder bg-darkSurface p-5"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accentPurple/10 text-sm font-bold text-accentPurple">
                {i + 1}
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-foreground">{step.title}</h4>
                <p className="text-sm text-muted-foreground">{step.text}</p>
                {step.tip && <Tip>{step.tip}</Tip>}
                {step.warning && <Warning>{step.warning}</Warning>}
              </div>
            </div>
          ))}
        </div>

        {/* ── TrackerBot Recommendation ── */}
        <div className="rounded-xl border border-accentBlue/30 bg-darkSurface p-6">
          <div className="mb-3 flex items-center gap-3">
            <ArrowRight className="h-5 w-5 text-accentBlue" />
            <h3 className="text-lg font-semibold">
              Recommended Tool:{" "}
              <span className="text-accentBlue">TrackerBot</span>
            </h3>
          </div>
          <p className="text-sm text-muted-foreground">
            95% of Amazon orders ship with TBA tracking numbers (Amazon's own
            logistics). eBay does not accept TBA numbers. TrackerBot automatically
            converts Amazon TBA tracking numbers into eBay-compatible tracking
            numbers so your orders show as shipped and trackable.
          </p>
          <a
            href="https://app.trackerbot.me/signup?ref=70260"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-glow-cyan mt-4 inline-flex items-center gap-2 rounded-lg bg-accentBlue/10 px-4 py-2 text-sm font-semibold text-accentBlue transition-colors hover:bg-accentBlue/20"
          >
            Get TrackerBot <ExternalLink className="h-4 w-4" />
          </a>
        </div>

        {/* ── Bottom spacer ── */}
        <div className="h-8" />
      </div>
    </>
  );
}
