"""
Email sending service.

Sends transactional emails via SMTP. If SMTP is not configured,
emails are logged to console (dev-friendly fallback).
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Sends transactional emails via SMTP (or logs in dev mode)."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()

    @property
    def _is_configured(self) -> bool:
        return bool(self._settings.smtp_host)

    def _build_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self._settings.smtp_from_name} <{self._settings.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        return msg

    def _send_smtp(self, to_email: str, msg: MIMEMultipart) -> None:
        """Blocking SMTP send — run in a thread."""
        s = self._settings
        if s.smtp_use_tls:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port)

        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.sendmail(s.smtp_from_email, to_email, msg.as_string())
        server.quit()

    async def send(self, to_email: str, subject: str, html_body: str) -> bool:
        """
        Send an email. Returns True on success.
        If SMTP is not configured, logs the email and returns True.
        """
        if not self._is_configured:
            logger.info(
                f"[EMAIL-DEV] To: {to_email} | Subject: {subject}\n{html_body[:500]}"
            )
            return True

        try:
            msg = self._build_message(to_email, subject, html_body)
            await asyncio.to_thread(self._send_smtp, to_email, msg)
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

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
