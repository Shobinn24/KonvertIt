"""
Authentication API endpoints.

Provides:
- POST /api/v1/auth/register — User registration
- POST /api/v1/auth/login — User login (returns JWT)
- POST /api/v1/auth/refresh — Refresh access token
- POST /api/v1/auth/ebay/connect — Start eBay OAuth flow
- GET /api/v1/auth/ebay/callback — eBay OAuth callback
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.encryption import encrypt
from app.db.database import get_db
from app.db.repositories.ebay_credential_repo import EbayCredentialRepository
from app.db.repositories.user_repo import UserRepository
from app.listers.ebay_auth import EbayAuth
from app.middleware.auth_middleware import get_current_user
from app.services.user_service import (
    AuthenticationError,
    RegistrationError,
    TokenError,
    UserService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Request / Response Schemas ──────────────────────────────


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    """Authentication response with user info and tokens."""
    user: dict
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    """Token refresh response — new access token only."""
    access_token: str
    token_type: str = "bearer"


class EbayConnectResponse(BaseModel):
    """eBay OAuth connect response — authorization URL."""
    authorization_url: str
    state: str


class EbayCallbackResponse(BaseModel):
    """eBay OAuth callback response — connection success."""
    message: str
    store_name: str = ""


# ─── Helper: Build UserService from Request ──────────────────


def _build_user_service(db: AsyncSession) -> UserService:
    """Create a UserService instance from a DB session."""
    return UserService(user_repo=UserRepository(db))


# ─── Endpoints ───────────────────────────────────────────────


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account with email and password.

    Returns JWT access and refresh tokens on success.
    The access token expires in 15 minutes; the refresh token in 7 days.
    """
    service = _build_user_service(db)

    try:
        result = await service.register(
            email=body.email,
            password=body.password,
        )
        return result
    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.

    Returns JWT access and refresh tokens on success.
    """
    service = _build_user_service(db)

    try:
        result = await service.authenticate(
            email=body.email,
            password=body.password,
        )
        return result
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.

    The refresh token itself is not rotated — it remains valid
    until its original expiration (7 days).

    Reads the current tier from the database so Stripe webhook
    tier changes are reflected in the new access token.
    """
    service = UserService(
        user_repo=UserRepository(db),
        settings=get_settings(),
    )

    try:
        result = await service.refresh_access_token(body.refresh_token)
        return result
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/ebay/connect",
    response_model=EbayConnectResponse,
    summary="Start eBay OAuth connection",
)
async def ebay_connect(
    user: dict = Depends(get_current_user),
):
    """
    Generate an eBay OAuth authorization URL for the current user.

    The frontend should redirect the user to this URL. After authorization,
    eBay will redirect back to the callback endpoint with an auth code.

    The state parameter encodes the user ID and a CSRF nonce so the
    callback can identify the user without requiring a JWT (eBay redirects
    the browser directly — no Authorization header is present).
    """
    csrf_nonce = str(uuid.uuid4())
    # Encode user_id in state so callback can identify user without JWT
    state = f"{user['sub']}:{csrf_nonce}"

    ebay_auth = EbayAuth()
    authorization_url = ebay_auth.get_authorization_url(state=state)

    return EbayConnectResponse(
        authorization_url=authorization_url,
        state=state,
    )


@router.get(
    "/ebay/callback",
    summary="eBay OAuth callback",
)
async def ebay_callback(
    code: str,
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    Handle the eBay OAuth callback after user authorization.

    eBay redirects the browser here directly — no Authorization header
    is present.  The user_id is extracted from the state parameter which
    was set during the /ebay/connect step (format: ``user_id:csrf_nonce``).

    After saving the tokens, the user is redirected to the frontend
    settings page with a success/error query parameter.
    """
    settings = get_settings()

    # Determine frontend URL for redirect
    frontend_url = settings.cors_allowed_origins.split(",")[0].strip() if settings.cors_allowed_origins else "http://localhost:5173"
    if frontend_url and not frontend_url.startswith("http"):
        frontend_url = f"https://{frontend_url}"

    # Extract user_id from state (format: "user_id:csrf_nonce")
    try:
        user_id_str, _ = state.split(":", 1)
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        logger.error(f"Invalid state parameter in eBay callback: {state}")
        return RedirectResponse(f"{frontend_url}/settings?ebay=error&reason=invalid_state")

    ebay_auth = EbayAuth()

    try:
        tokens = await ebay_auth.exchange_code(code)
    except Exception as e:
        logger.error(f"eBay token exchange failed for user {user_id}: {e}")
        return RedirectResponse(f"{frontend_url}/settings?ebay=error&reason=token_exchange_failed")

    # Save credentials
    credential_repo = EbayCredentialRepository(db)

    await credential_repo.create(
        user_id=user_id,
        access_token=encrypt(tokens.get("access_token", "")),
        refresh_token=encrypt(tokens.get("refresh_token", "")),
        token_expiry=None,  # Will be set from expires_in on next use
        sandbox_mode=settings.ebay_sandbox,
        store_name="",
    )

    logger.info(f"eBay credentials saved for user {user_id}")

    return RedirectResponse(f"{frontend_url}/settings?ebay=connected")


class EbayStatusResponse(BaseModel):
    """eBay connection status."""
    connected: bool
    store_name: str = ""


@router.get(
    "/ebay/status",
    response_model=EbayStatusResponse,
    summary="Check eBay connection status",
)
async def ebay_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check whether the current user has a connected eBay account."""
    repo = EbayCredentialRepository(db)
    creds = await repo.find_by_user(uuid.UUID(user["sub"]))
    if creds:
        return EbayStatusResponse(connected=True, store_name=creds[0].store_name or "")
    return EbayStatusResponse(connected=False)
