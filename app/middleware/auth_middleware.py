"""
JWT authentication middleware and FastAPI dependencies.

Provides:
- get_current_user: FastAPI dependency that extracts and verifies JWT
  from the Authorization header, returning the authenticated user's payload.
- require_active_user: Stricter dependency that also verifies the user
  is active in the database.
- get_current_user_optional: Returns None instead of raising 401 when no
  token is present, for endpoints that support both authenticated and
  anonymous access.

Usage in endpoints:
    @router.get("/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        return {"user_id": user["sub"], "tier": user["tier"]}
"""

import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db
from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

# FastAPI security scheme — extracts Bearer token from Authorization header
_bearer_scheme = HTTPBearer(auto_error=True)
_bearer_scheme_optional = HTTPBearer(auto_error=False)


# ─── Core Token Verification ────────────────────────────────


def _decode_token(token: str, settings: Settings) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: Raw JWT string.
        settings: App settings with secret_key and algorithm.

    Returns:
        Decoded payload dict.

    Raises:
        HTTPException 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ─── FastAPI Dependencies ────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    FastAPI dependency: extract and verify JWT access token.

    Returns the decoded token payload dict with keys:
    sub, email, tier, type, iat, exp.

    Raises:
        HTTPException 401 if token is missing, invalid, or expired.
        HTTPException 401 if token is not an access token.
    """
    payload = _decode_token(credentials.credentials, settings)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme_optional),
    settings: Settings = Depends(get_settings),
) -> dict | None:
    """
    FastAPI dependency: optionally extract JWT access token.

    Returns decoded payload if token is present and valid, None otherwise.
    Does NOT raise 401 for missing tokens — use for mixed auth endpoints.
    """
    if credentials is None:
        return None

    try:
        payload = _decode_token(credentials.credentials, settings)
        if payload.get("type") != "access":
            return None
        return payload
    except HTTPException:
        return None


async def require_active_user(
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    FastAPI dependency: verify JWT AND check user is active in the database.

    This is stricter than get_current_user — it hits the DB to confirm
    the user still exists and is active (hasn't been deactivated since
    the token was issued).

    Returns the token payload if all checks pass.

    Raises:
        HTTPException 401 if user not found or deactivated.
    """
    user_repo = UserRepository(db)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return payload
