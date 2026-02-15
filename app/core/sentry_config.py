"""
Sentry error tracking configuration for KonvertIt.

Initializes Sentry SDK with FastAPI, Starlette, and asyncio integrations.
Filters out expected 4xx HTTPExceptions to reduce noise.

When ``dsn`` is empty (the default), Sentry is completely disabled —
no SDK overhead, no network calls.
"""

import logging

import sentry_sdk
from fastapi import HTTPException
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import AppEnv
from app.core.exceptions import KonvertItError


def init_sentry(
    dsn: str,
    app_env: AppEnv,
    app_version: str,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> None:
    """
    Initialize Sentry SDK for error tracking and performance monitoring.

    Args:
        dsn: Sentry DSN. Empty string disables Sentry entirely.
        app_env: Current environment (used as Sentry ``environment``).
        app_version: Application version (used as Sentry ``release``).
        traces_sample_rate: Fraction of transactions to trace (0.0–1.0).
        profiles_sample_rate: Fraction of transactions to profile (0.0–1.0).
    """
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=app_env.value,
        release=f"konvertit@{app_version}",
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            AsyncioIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        before_send=_filter_events,
        send_default_pii=False,
    )


def _filter_events(event: dict, hint: dict) -> dict | None:
    """
    Filter Sentry events before sending.

    - Drops 4xx HTTPException events (expected client errors).
    - Enriches KonvertItError subclasses with custom tags.
    """
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]

        # Drop expected client errors
        if isinstance(exc_value, HTTPException) and exc_value.status_code < 500:
            return None

        # Tag KonvertItError subclasses for easier filtering in Sentry
        if isinstance(exc_value, KonvertItError):
            event.setdefault("tags", {})
            event["tags"]["error_type"] = type(exc_value).__name__
            if exc_value.details:
                event["extra"] = {**event.get("extra", {}), **exc_value.details}

    return event
