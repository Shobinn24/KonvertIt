"""
Email sending service.

Supports two providers:
1. Resend (preferred) — set RESEND_API_KEY env var
2. SMTP — set SMTP_HOST env var

If neither is configured, emails are logged to console (dev fallback).
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """Sends transactional emails via Resend, SMTP, or dev-mode logging."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()

    @property
    def _provider(self) -> str:
        if self._settings.resend_api_key:
            return "resend"
        if self._settings.smtp_host:
            return "smtp"
        return "dev"

    # ─── Resend (HTTP API) ───────────────────────────────────

    async def _send_resend(self, to_email: str, subject: str, html_body: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {self._settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{self._settings.smtp_from_name} <{self._settings.smtp_from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"Resend API error {resp.status_code}: {resp.text}")

    # ─── SMTP ────────────────────────────────────────────────

    def _send_smtp(self, to_email: str, subject: str, html_body: str) -> None:
        """Blocking SMTP send — run in a thread."""
        s = self._settings
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{s.smtp_from_name} <{s.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        if s.smtp_use_tls:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port)

        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.sendmail(s.smtp_from_email, to_email, msg.as_string())
        server.quit()

    # ─── Send (unified) ──────────────────────────────────────

    async def send(self, to_email: str, subject: str, html_body: str) -> bool:
        """
        Send an email via the configured provider.
        Falls back to console logging if no provider is set.
        """
        provider = self._provider

        if provider == "dev":
            logger.info(
                f"[EMAIL-DEV] To: {to_email} | Subject: {subject}\n{html_body[:500]}"
            )
            return True

        try:
            if provider == "resend":
                await self._send_resend(to_email, subject, html_body)
            else:
                await asyncio.to_thread(self._send_smtp, to_email, subject, html_body)

            logger.info(f"Email sent via {provider} to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via {provider} to {to_email}: {e}")
            return False

    # ─── Verification Email ──────────────────────────────────

    async def send_verification_email(
        self,
        to_email: str,
        first_name: str,
        verification_url: str,
    ) -> bool:
        """Send the email verification link."""
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <h1 style="color: #0B0E14; font-size: 24px;">Verify your email</h1>
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                Hi {first_name},<br><br>
                Thanks for signing up for KonvertIt! Please verify your email address
                by clicking the button below.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{verification_url}"
                   style="background-color: #2563EB; color: white; padding: 12px 32px;
                          border-radius: 8px; text-decoration: none; font-weight: 600;
                          font-size: 16px; display: inline-block;">
                    Verify Email
                </a>
            </div>
            <p style="color: #6B7280; font-size: 14px;">
                If the button doesn't work, copy and paste this link:<br>
                <a href="{verification_url}" style="color: #2563EB;">{verification_url}</a>
            </p>
            <p style="color: #9CA3AF; font-size: 12px; margin-top: 32px;">
                This link expires in 24 hours. If you didn't create a KonvertIt account,
                you can safely ignore this email.
            </p>
        </div>
        """
        return await self.send(to_email, "Verify your KonvertIt email", html)
