"""
eBay OAuth 2.0 authentication manager.

Handles the eBay user consent flow and token management
for creating listings on behalf of connected sellers.
"""

import base64
import logging
from urllib.parse import quote, urlencode

import httpx

from app.config import get_settings
from app.core.exceptions import EbayAuthError

logger = logging.getLogger(__name__)

# eBay OAuth scopes needed for listing management
EBAY_SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]


class EbayAuth:
    """
    Manages eBay OAuth 2.0 authentication flow.

    Usage:
        auth = EbayAuth()
        # Step 1: Get authorization URL for user consent
        url = auth.get_authorization_url(state="random-state")
        # Step 2: User authorizes → eBay redirects with auth code
        # Step 3: Exchange code for tokens
        tokens = await auth.exchange_code(auth_code)
        # Step 4: Refresh tokens when expired
        tokens = await auth.refresh_token(refresh_token)
    """

    def __init__(self):
        settings = get_settings()
        self._app_id = settings.ebay_app_id
        self._cert_id = settings.ebay_cert_id
        self._dev_id = settings.ebay_dev_id
        self._redirect_uri = settings.ebay_redirect_uri
        self._base_url = settings.ebay_base_url
        self._auth_url = settings.ebay_auth_url

    def get_authorization_url(self, state: str = "") -> str:
        """
        Generate the eBay OAuth authorization URL for user consent.

        Args:
            state: Random state parameter for CSRF protection.

        Returns:
            URL to redirect the user to for eBay authorization.
        """
        params = {
            "client_id": self._app_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "scope": " ".join(EBAY_SCOPES),
            "state": state,
        }
        # eBay requires %20 space encoding (not +) and unencoded :// in scope URLs.
        # safe=':/' keeps colons and slashes literal — eBay rejects %3A%2F%2F encoding.
        url = f"{self._auth_url}/oauth2/authorize?{urlencode(params, quote_via=quote, safe=':/')}"
        logger.info("Generated eBay auth URL (scopes: %d, state: %s)", len(EBAY_SCOPES), bool(state))
        logger.debug("eBay auth URL: %s", url)
        return url

    def _get_basic_auth_header(self) -> str:
        """Generate Base64-encoded credentials for token requests."""
        credentials = f"{self._app_id}:{self._cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def exchange_code(self, auth_code: str) -> dict:
        """
        Exchange an authorization code for access and refresh tokens.

        Args:
            auth_code: The authorization code from eBay's redirect.

        Returns:
            Dict with access_token, refresh_token, and expires_in.

        Raises:
            EbayAuthError: If token exchange fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/identity/v1/oauth2/token",
                headers={
                    "Authorization": self._get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": self._redirect_uri,
                },
            )

        if response.status_code != 200:
            raise EbayAuthError(
                f"Token exchange failed: {response.status_code}",
                details={"response": response.text},
            )

        return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Refresh an expired access token.

        Args:
            refresh_token: The refresh token from a previous authorization.

        Returns:
            Dict with new access_token and expires_in.

        Raises:
            EbayAuthError: If token refresh fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/identity/v1/oauth2/token",
                headers={
                    "Authorization": self._get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": " ".join(EBAY_SCOPES),
                },
            )

        if response.status_code != 200:
            raise EbayAuthError(
                f"Token refresh failed: {response.status_code}",
                details={"response": response.text},
            )

        return response.json()
