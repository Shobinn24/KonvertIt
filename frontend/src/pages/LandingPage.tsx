import { Link } from "react-router-dom";
import {
  ShoppingCart,
  Cog,
  Gavel,
  DollarSign,
  Image,
  Type,
  Layers,
  ArrowRight,
  Check,
  Zap,
} from "lucide-react";

/* ─── Hero Section ─── */
function HeroSection() {
  return (
    <section className="relative overflow-hidden px-6 pb-24 pt-32">
      {/* Background gradient orbs */}
      <div className="pointer-events-none absolute -top-40 left-1/4 h-[500px] w-[500px] rounded-full bg-accentPurple/20 blur-[120px]" />
      <div className="pointer-events-none absolute -top-20 right-1/4 h-[400px] w-[400px] rounded-full bg-accentBlue/15 blur-[120px]" />

      <div className="relative mx-auto max-w-4xl text-center">
        <img
          src="/logo.jpg"
          alt="KonvertIt"
          className="mx-auto mb-8 h-20 w-auto"
        />

        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl">
          Stop Copy-Pasting.{" "}
          <span className="text-gradient">Start Selling.</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
          Instantly scrape, format, and push products from Amazon and Walmart
          directly to your eBay store in seconds. Keep your margins high and your
          manual labor at zero.
        </p>

        {/* Magic Input Bar */}
        <div className="mx-auto mt-10 max-w-2xl">
          <div className="flex items-center gap-2 rounded-full border border-darkBorder bg-darkSurface p-2 shadow-lg shadow-accentPurple/5">
            <input
              type="text"
              placeholder="Paste an Amazon or Walmart URL here..."
              className="flex-1 bg-transparent px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              readOnly
            />
            <Link
              to="/register"
              className="btn-glow pulse-glow flex items-center gap-2 rounded-full bg-accentPurple px-6 py-3 text-sm font-semibold text-white"
            >
              <Zap className="h-4 w-4" />
              Konvert It
            </Link>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            No credit card required. Start free with 50 conversions/day.
          </p>
        </div>
      </div>
    </section>
  );
}

/* ─── How It Works ─── */
const steps = [
  {
    icon: ShoppingCart,
    title: "Source",
    description: "Drop a link from Walmart or Amazon.",
    color: "text-accentBlue",
    bgColor: "bg-accentBlue/10",
    glowColor: "shadow-accentBlue/20",
  },
  {
    icon: Cog,
    title: "Scrape & Optimize",
    description:
      "KonvertIt grabs titles, high-res images, and descriptions, automatically formatting them for eBay's standards.",
    color: "text-accentPurple",
    bgColor: "bg-accentPurple/10",
    glowColor: "shadow-accentPurple/20",
  },
  {
    icon: Gavel,
    title: "Profit",
    description:
      "Push directly to your active eBay listings with your pre-set price markups.",
    color: "text-emerald-400",
    bgColor: "bg-emerald-400/10",
    glowColor: "shadow-emerald-400/20",
  },
];

function HowItWorksSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold sm:text-4xl">
          How It <span className="text-gradient">Works</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-muted-foreground">
          Three simple steps from product discovery to eBay listing.
        </p>

        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <div key={step.title} className="relative text-center">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="absolute right-0 top-12 hidden h-px w-8 translate-x-full md:block">
                  <div className="gradient-line h-full w-full" />
                </div>
              )}

              <div
                className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl ${step.bgColor} shadow-lg ${step.glowColor}`}
              >
                <step.icon className={`h-7 w-7 ${step.color}`} />
              </div>
              <div className="mt-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-darkBorder text-xs font-bold">
                {i + 1}
              </div>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Features Grid ─── */
const features = [
  {
    icon: DollarSign,
    title: "Smart Markups",
    description:
      "Automatically calculate eBay fees and apply your desired profit margin.",
  },
  {
    icon: Image,
    title: "Image Handling",
    description:
      "Download, resize, and strip metadata from competitor images for compliant listings.",
  },
  {
    icon: Type,
    title: "Title Scrubber",
    description:
      'Remove brand-specific junk words like "Amazon Basics" or "Prime" to avoid IP flags.',
  },
  {
    icon: Layers,
    title: "Bulk Konvert",
    description:
      "Paste a list of 50 URLs and let the engine run in the background with real-time progress.",
  },
];

function FeaturesSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold sm:text-4xl">
          Built for <span className="text-gradient">Resellers</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-muted-foreground">
          Every feature designed to save you time and keep your eBay store
          stocked.
        </p>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="card-hover-glow rounded-xl border border-darkBorder bg-darkSurface p-6"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accentPurple/10">
                <f.icon className="h-5 w-5 text-accentPurple" />
              </div>
              <h3 className="mt-4 font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {f.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Live Preview Section ─── */
function LivePreviewSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold sm:text-4xl">
          See the <span className="text-gradient">Magic</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-muted-foreground">
          From cluttered marketplace listing to clean, optimized eBay product —
          in seconds.
        </p>

        <div className="mt-16 grid items-center gap-6 md:grid-cols-[1fr_auto_1fr]">
          {/* Input side — Amazon mock */}
          <div className="rounded-xl border border-darkBorder bg-darkSurface p-6">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <div className="h-3 w-3 rounded-full bg-yellow-500" />
              <div className="h-3 w-3 rounded-full bg-green-500" />
              <span className="ml-2 text-xs text-muted-foreground">
                amazon.com/dp/B0C2C9NHZW
              </span>
            </div>
            <div className="space-y-3 rounded-lg bg-darkBg p-4">
              <div className="h-24 w-full rounded bg-darkBorder/50" />
              <div className="h-3 w-3/4 rounded bg-darkBorder/50" />
              <div className="h-3 w-1/2 rounded bg-darkBorder/50" />
              <div className="flex items-center gap-2">
                <span className="text-xs text-orange-400">$39.99</span>
                <span className="text-xs text-muted-foreground line-through">
                  $49.99
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                <span className="rounded bg-orange-500/20 px-2 py-0.5 text-[10px] text-orange-400">
                  Best Seller
                </span>
                <span className="rounded bg-blue-500/20 px-2 py-0.5 text-[10px] text-blue-400">
                  Prime
                </span>
              </div>
            </div>
          </div>

          {/* Arrow */}
          <div className="flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full border border-darkBorder bg-darkSurface">
              <ArrowRight className="h-6 w-6 text-accentPurple" />
            </div>
          </div>

          {/* Output side — eBay mock */}
          <div className="rounded-xl border border-accentPurple/30 bg-darkSurface p-6 shadow-lg shadow-accentPurple/5">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <div className="h-3 w-3 rounded-full bg-yellow-500" />
              <div className="h-3 w-3 rounded-full bg-green-500" />
              <span className="ml-2 text-xs text-accentBlue">
                eBay Listing Preview
              </span>
            </div>
            <div className="space-y-3 rounded-lg bg-darkBg p-4">
              <div className="h-24 w-full rounded bg-gradient-to-br from-accentPurple/10 to-accentBlue/10" />
              <div className="h-3 w-3/4 rounded bg-accentPurple/20" />
              <div className="h-3 w-1/2 rounded bg-accentPurple/10" />
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-emerald-400">
                  $54.99
                </span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">
                  +37% margin
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                <span className="rounded bg-accentPurple/20 px-2 py-0.5 text-[10px] text-accentPurple">
                  Optimized Title
                </span>
                <span className="rounded bg-accentBlue/20 px-2 py-0.5 text-[10px] text-accentBlue">
                  eBay Compliant
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─── Pricing Section ─── */
const tiers = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "Get started with basic conversions",
    features: [
      "50 conversions / day",
      "100 active listings",
      "Single URL conversion",
      "Basic title optimization",
    ],
    cta: "Start Free",
    highlight: false,
  },
  {
    name: "Hustler",
    price: "$29",
    period: "/ mo",
    description: "For serious resellers scaling up",
    features: [
      "1,000 conversions / month",
      "Unlimited listings",
      "Bulk upload (50 at once)",
      "Auto-pricing & markups",
      "Priority support",
    ],
    cta: "Get Hustler",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "$99",
    period: "/ mo",
    description: "Unlimited power for large operations",
    features: [
      "Unlimited conversions",
      "Unlimited listings",
      "API access",
      "Custom integrations",
      "Dedicated support",
    ],
    cta: "Contact Sales",
    highlight: false,
  },
];

function PricingSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold sm:text-4xl">
          Simple <span className="text-gradient">Pricing</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-muted-foreground">
          Start free. Upgrade when you're ready to scale.
        </p>

        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-xl border p-8 ${
                tier.highlight
                  ? "border-accentPurple/50 bg-darkSurface shadow-lg shadow-accentPurple/10"
                  : "border-darkBorder bg-darkSurface"
              }`}
            >
              {tier.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-accentPurple px-3 py-1 text-xs font-semibold text-white">
                    Most Popular
                  </span>
                </div>
              )}

              <h3 className="text-lg font-semibold">{tier.name}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-bold">{tier.price}</span>
                {tier.period && (
                  <span className="text-muted-foreground">{tier.period}</span>
                )}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {tier.description}
              </p>

              <ul className="mt-6 space-y-3">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <Check
                      className={`h-4 w-4 ${
                        tier.highlight
                          ? "text-accentPurple"
                          : "text-accentBlue"
                      }`}
                    />
                    {f}
                  </li>
                ))}
              </ul>

              <Link
                to="/register"
                className={`mt-8 block w-full rounded-lg py-3 text-center text-sm font-semibold transition-all ${
                  tier.highlight
                    ? "btn-glow bg-accentPurple text-white hover:bg-accentPurple/90"
                    : "border border-darkBorder bg-darkBg text-foreground hover:bg-darkBorder"
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Footer ─── */
function Footer() {
  return (
    <footer className="border-t border-darkBorder px-6 py-12">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-3">
          <img src="/logo.jpg" alt="KonvertIt" className="h-8 w-auto" />
          <span className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} E-Clarx LLC
          </span>
        </div>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <Link to="/login" className="hover:text-foreground">
            Sign In
          </Link>
          <Link to="/register" className="hover:text-foreground">
            Get Started
          </Link>
        </div>
      </div>
    </footer>
  );
}

/* ─── Main Landing Page ─── */
export function LandingPage() {
  return (
    <div className="min-h-screen bg-darkBg text-foreground">
      {/* Navbar */}
      <nav className="fixed left-0 right-0 top-0 z-50 border-b border-darkBorder/50 bg-darkBg/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.jpg" alt="KonvertIt" className="h-10 w-auto" />
          </Link>
          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="btn-glow rounded-lg bg-accentPurple px-4 py-2 text-sm font-semibold text-white"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      <HeroSection />
      <div className="gradient-line mx-auto h-px max-w-3xl" />
      <HowItWorksSection />
      <div className="gradient-line mx-auto h-px max-w-3xl" />
      <FeaturesSection />
      <div className="gradient-line mx-auto h-px max-w-3xl" />
      <LivePreviewSection />
      <div className="gradient-line mx-auto h-px max-w-3xl" />
      <PricingSection />
      <Footer />
    </div>
  );
}
