"""
Google reCAPTCHA v3 server-side verification.

Validates tokens sent from the frontend against Google's siteverify API.
If RECAPTCHA_SECRET_KEY is not configured, verification is skipped (dev mode).
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(token: str, expected_action: str = "register") -> bool:
    """
    Verify a reCAPTCHA v3 token with Google.

    Args:
        token: The reCAPTCHA response token from the frontend.
        expected_action: The action name to validate against (must match frontend).

    Returns:
        True if verification passes or reCAPTCHA is not configured.
        False if the token is invalid, score is too low, or action mismatches.
    """
    settings = get_settings()

    if not settings.recaptcha_secret_key:
        logger.debug("reCAPTCHA not configured — skipping verification")
        return True

    if not token:
        logger.warning("reCAPTCHA token missing from request")
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                VERIFY_URL,
                data={
                    "secret": settings.recaptcha_secret_key,
                    "response": token,
                },
            )
            result = resp.json()
    except Exception as e:
        logger.error(f"reCAPTCHA verification request failed: {e}")
        # Fail-open: allow request if Google is unreachable
        return True

    if not result.get("success"):
        logger.warning(f"reCAPTCHA verification failed: {result.get('error-codes', [])}")
        return False

    # Validate action matches
    if result.get("action") != expected_action:
        logger.warning(
            f"reCAPTCHA action mismatch: expected '{expected_action}', got '{result.get('action')}'"
        )
        return False

    # Check score
    score = result.get("score", 0.0)
    if score < settings.recaptcha_min_score:
        logger.warning(f"reCAPTCHA score too low: {score} < {settings.recaptcha_min_score}")
        return False

    logger.debug(f"reCAPTCHA passed (score={score}, action={result.get('action')})")
    return True
