import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function RefundPolicyPage() {
  return (
    <div className="min-h-screen bg-darkBg text-foreground">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <Link
          to="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Home
        </Link>

        <h1 className="text-4xl font-extrabold tracking-tight">
          Refund Policy
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              No Refunds
            </h2>
            <p>
              All sales on KonvertIt are final. We do not offer refunds for any subscription payments,
              plan upgrades, or other charges made through the Service.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Why We Don't Offer Refunds
            </h2>
            <p>
              KonvertIt provides immediate access to our full suite of tools upon payment. Because the
              Service delivers instant digital value (product conversions, listing optimizations, and
              data processing), charges are non-refundable once processed.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Free Tier Available
            </h2>
            <p>
              We offer a free Starter plan so you can evaluate the Service before committing to a paid
              subscription. We encourage all users to try the free tier first to ensure KonvertIt meets
              their needs.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Cancellation
            </h2>
            <p>
              You may cancel your subscription at any time from your account settings. Upon
              cancellation, you will retain access to your paid plan features through the end of your
              current billing period. No further charges will be made after cancellation.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Exceptions
            </h2>
            <p>
              In rare cases where a billing error occurs on our end (such as a duplicate charge), we
              will correct the issue promptly. If you believe you were charged in error, please contact
              us within 7 days of the charge.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              Contact
            </h2>
            <p>
              If you have questions about billing or believe there was an error,
              please reach out through our official website or support channels.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
