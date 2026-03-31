import { TopBar } from "@/components/layout/TopBar";
import {
  Plug,
  Truck,
  RotateCcw,
  Search,
  Zap,
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
      <TopBar title="Help & Getting Started" />
      <div className="max-w-3xl space-y-8 p-6">
        {/* Intro */}
        <div>
          <h2 className="text-2xl font-bold">
            Getting Started with{" "}
            <span className="text-accentPurple">KonvertIt</span>
          </h2>
          <p className="mt-2 text-muted-foreground">
            Follow these four steps to connect your eBay account and start
            listing profitable products in minutes.
          </p>
        </div>

        {/* ── Step 1: Connect eBay ── */}
        <SectionCard icon={Plug} number={1} title="Connect Your eBay Account">
          <StepList
            steps={[
              "Go to Settings (bottom of the left sidebar).",
              'Open the "eBay Account" tab.',
              'Click "Connect eBay Account" and sign in with your eBay seller credentials.',
              "Once connected, your account name will appear and you're ready to list.",
            ]}
          />
          <Tip>
            KonvertIt uses eBay's official OAuth flow — your password is never
            stored. You can disconnect at any time from the same Settings page.
          </Tip>
        </SectionCard>

        {/* ── Step 2: Business Policies ── */}
        <SectionCard icon={RotateCcw} number={2} title="Set Up Your eBay Business Policies">
          <p>
            KonvertIt attaches your eBay business policies (shipping, returns,
            payment) to every listing automatically. You only set these up once.
          </p>
          <StepList
            steps={[
              "In eBay, go to Account Settings → Business Policies.",
              "Create a Shipping policy, a Returns policy, and a Payment policy.",
              "Copy the Policy IDs from eBay.",
              "Paste them into Settings → eBay Account → Policy IDs in KonvertIt.",
            ]}
          />
          <Tip>
            Need to create your policies?{" "}
            <a
              href="https://www.ebay.com/bp/manage"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accentBlue hover:underline"
            >
              Manage policies at ebay.com/bp/manage{" "}
              <ExternalLink className="mb-0.5 inline h-3 w-3" />
            </a>
          </Tip>
          <Warning>
            If you don't see Business Policies in your eBay account, you may
            need to opt in once — eBay will prompt you automatically.
          </Warning>
        </SectionCard>

        {/* ── Step 3: Discover Products ── */}
        <SectionCard icon={Search} number={3} title="Find Profitable Products">
          <p>There are two ways to find products to sell:</p>
          <div className="space-y-3">
            <div className="rounded-lg border border-darkBorder p-3">
              <p className="font-medium text-foreground">Manual Discovery</p>
              <p className="mt-1">
                Go to the <strong>Discover</strong> tab and search by keyword or
                category. KonvertIt scans Amazon and Walmart for products with
                strong profit margins and shows you the best matches.
              </p>
            </div>
            <div className="rounded-lg border border-accentPurple/20 p-3">
              <p className="font-medium text-foreground">
                Auto-Discovery{" "}
                <span className="text-accentPurple">(set it and forget it)</span>
              </p>
              <p className="mt-1">
                Go to the <strong>Auto-Discover</strong> tab and toggle it ON.
                KonvertIt will automatically find and convert profitable products
                for you every day — no manual searching needed.
              </p>
            </div>
          </div>
          <Tip>
            Start with Auto-Discovery toggled ON and set your minimum margin to
            20%. KonvertIt will do the daily scanning for you in the background.
          </Tip>
        </SectionCard>

        {/* ── Step 4: Convert & List ── */}
        <SectionCard icon={Zap} number={4} title="Convert Products & Publish to eBay">
          <p>Once you've found a product you want to sell:</p>
          <StepList
            steps={[
              "Go to the Convert tab.",
              "Paste the Amazon or Walmart product URL.",
              'Click "Convert" — KonvertIt generates the full eBay listing automatically.',
              'Review the listing, then click "Publish to eBay" to go live instantly.',
            ]}
          />
          <Tip>
            Use <strong>Bulk Convert</strong> to upload a list of URLs at once
            and convert multiple products in one go — great for scaling up fast.
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
                "Stock core supplies: 4×6 thermal printer, boxes, poly mailers, bubble, tape, scale.",
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
              tip: "Option 1 (Fastest): Copy/paste the item title from the eBay listing into the Amazon search bar. Option 2: KonvertIt inserts the ASIN into the eBay listing SKU — copy the ASIN and search directly.",
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
              text: 'If the tracking number starts with TBA (Amazon\'s logistics) — which is 95% of cases — you must convert it to an eBay-accepted tracking number.',
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
