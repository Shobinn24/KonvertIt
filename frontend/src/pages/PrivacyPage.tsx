import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function PrivacyPage() {
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
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              1. Introduction
            </h2>
            <p>
              E-Clarx LLC ("we", "us", or "our") operates KonvertIt. This Privacy Policy explains how
              we collect, use, and protect your information when you use our Service.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              2. Information We Collect
            </h2>
            <p className="mb-2">We collect the following types of information:</p>
            <ul className="list-disc space-y-1 pl-6">
              <li>
                <strong className="text-foreground">Account Information:</strong> Name, email address,
                and password when you register
              </li>
              <li>
                <strong className="text-foreground">Billing Information:</strong> Payment details processed
                securely through Stripe — we never store your full card number
              </li>
              <li>
                <strong className="text-foreground">Usage Data:</strong> Conversion history, listing data,
                and feature usage to improve the Service
              </li>
              <li>
                <strong className="text-foreground">Technical Data:</strong> IP address, browser type,
                and device information collected automatically
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              3. How We Use Your Information
            </h2>
            <ul className="list-disc space-y-1 pl-6">
              <li>To provide, maintain, and improve the Service</li>
              <li>To process transactions and manage your subscription</li>
              <li>To send important updates about the Service or your account</li>
              <li>To monitor usage and prevent abuse or fraud</li>
              <li>To respond to support requests</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              4. Data Sharing
            </h2>
            <p>
              We do not sell your personal information. We may share data with third-party service
              providers that help us operate the Service, including:
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-6">
              <li>
                <strong className="text-foreground">Stripe</strong> — for payment processing
              </li>
              <li>
                <strong className="text-foreground">eBay API</strong> — to publish listings on your behalf
                (only with your authorization)
              </li>
              <li>
                <strong className="text-foreground">Vercel</strong> — for hosting and analytics
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              5. Data Security
            </h2>
            <p>
              We implement industry-standard security measures to protect your data, including
              encryption in transit (HTTPS), secure password hashing, and access controls. However, no
              method of transmission over the internet is 100% secure, and we cannot guarantee absolute
              security.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              6. Data Retention
            </h2>
            <p>
              We retain your data for as long as your account is active or as needed to provide the
              Service. If you delete your account, we will remove your personal data within 30 days,
              except where retention is required by law.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              7. Cookies & Analytics
            </h2>
            <p>
              We use Vercel Analytics to collect anonymous usage data such as page views and
              performance metrics. We do not use third-party advertising cookies. Essential cookies
              may be used to maintain your session and preferences.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              8. Your Rights
            </h2>
            <p>You have the right to:</p>
            <ul className="mt-2 list-disc space-y-1 pl-6">
              <li>Access and receive a copy of your personal data</li>
              <li>Request correction of inaccurate data</li>
              <li>Request deletion of your account and associated data</li>
              <li>Opt out of non-essential communications</li>
            </ul>
            <p className="mt-2">
              To exercise any of these rights, please reach out through our
              official website or support channels.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              9. Children's Privacy
            </h2>
            <p>
              The Service is not intended for users under 18 years of age. We do not knowingly collect
              information from children.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              10. Changes to This Policy
            </h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of any material
              changes by posting the updated policy on this page. Continued use of the Service after
              changes constitutes acceptance.
            </p>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              11. Contact
            </h2>
            <p>
              If you have questions about this Privacy Policy, please reach out
              through our official website or support channels.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
