import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function TermsPage() {
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
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              1. Acceptance of Terms
            </h2>
            <p>
              By accessing or using KonvertIt ("the Service"), operated by E-Clarx LLC ("we", "us", or "our"),
              you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              2. Description of Service
            </h2>
            <p>
              KonvertIt is a software-as-a-service platform that helps users convert product listings
              from supported marketplaces (such as Amazon and Walmart) into eBay-compatible listings.
              The Service includes product data scraping, title optimization, image processing, and
              listing management tools.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              3. Account Registration
            </h2>
            <p>
              You must create an account to use the Service. You are responsible for maintaining the
              confidentiality of your account credentials and for all activity under your account.
              You must provide accurate and complete information during registration.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              4. Acceptable Use
            </h2>
            <p>You agree not to:</p>
            <ul className="mt-2 list-disc space-y-1 pl-6">
              <li>Use the Service for any unlawful purpose or in violation of any applicable laws</li>
              <li>Attempt to reverse-engineer, decompile, or disassemble the Service</li>
              <li>Interfere with or disrupt the Service or servers connected to it</li>
              <li>Share your account credentials with third parties</li>
              <li>Use the Service to list prohibited or restricted items on any marketplace</li>
              <li>Exceed your plan's usage limits through automated or abusive means</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              5. Subscription & Billing
            </h2>
            <p>
              Paid plans are billed on a recurring monthly basis. By subscribing, you authorize us to
              charge the payment method on file. You may cancel at any time, and your access will
              continue through the end of the current billing period. All fees are non-refundable —
              please see our{" "}
              <Link to="/refund-policy" className="text-accentPurple hover:underline">
                Refund Policy
              </Link>{" "}
              for details.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              6. Intellectual Property
            </h2>
            <p>
              The Service, including its design, code, and branding, is owned by E-Clarx LLC and
              protected by intellectual property laws. You retain ownership of the content you create
              using the Service. We do not claim ownership of your listings or data.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              7. Third-Party Platforms
            </h2>
            <p>
              KonvertIt integrates with third-party platforms including eBay, Amazon, and Walmart.
              Your use of those platforms is subject to their respective terms of service. We are not
              responsible for any actions taken by those platforms regarding your account or listings.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              8. Limitation of Liability
            </h2>
            <p>
              To the fullest extent permitted by law, E-Clarx LLC shall not be liable for any
              indirect, incidental, special, consequential, or punitive damages arising out of your
              use of the Service. Our total liability shall not exceed the amount you paid us in the
              twelve (12) months preceding the claim.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              9. Disclaimer of Warranties
            </h2>
            <p>
              The Service is provided "as is" and "as available" without warranties of any kind,
              whether express or implied. We do not guarantee that the Service will be uninterrupted,
              error-free, or that any defects will be corrected.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              10. Termination
            </h2>
            <p>
              We reserve the right to suspend or terminate your account at any time for violations of
              these Terms or for any conduct that we determine is harmful to other users or the
              Service. You may delete your account at any time through your account settings.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              11. Changes to Terms
            </h2>
            <p>
              We may update these Terms from time to time. We will notify you of material changes by
              posting the updated Terms on this page. Continued use of the Service after changes
              constitutes acceptance of the updated Terms.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              12. Contact
            </h2>
            <p>
              If you have questions about these Terms, please reach out through
              our official website or support channels.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
