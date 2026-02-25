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

    A random state parameter is generated for CSRF protection.
    """
    state = str(uuid.uuid4())

    ebay_auth = EbayAuth()
    authorization_url = ebay_auth.get_authorization_url(state=state)

    return EbayConnectResponse(
        authorization_url=authorization_url,
        state=state,
    )


@router.get(
    "/ebay/callback",
    response_model=EbayCallbackResponse,
    summary="eBay OAuth callback",
)
async def ebay_callback(
    code: str,
    state: str = "",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle the eBay OAuth callback after user authorization.

    Exchanges the authorization code for access/refresh tokens
    and saves the eBay credentials for the authenticated user.

    Query params:
        code: Authorization code from eBay redirect.
        state: CSRF state parameter (should match the one from /ebay/connect).
    """
    ebay_auth = EbayAuth()

    try:
        tokens = await ebay_auth.exchange_code(code)
    except Exception as e:
        logger.error(f"eBay token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect eBay account: {e}",
        )

    # Save credentials
    credential_repo = EbayCredentialRepository(db)
    settings = get_settings()

    user_id = uuid.UUID(user["sub"])

    await credential_repo.create(
        user_id=user_id,
        access_token=encrypt(tokens.get("access_token", "")),
        refresh_token=encrypt(tokens.get("refresh_token", "")),
        token_expiry=None,  # Will be set from expires_in on next use
        sandbox_mode=settings.ebay_sandbox,
        store_name="",
    )

    logger.info(f"eBay credentials saved for user {user['sub']}")

    return EbayCallbackResponse(
        message="eBay account connected successfully",
    )
