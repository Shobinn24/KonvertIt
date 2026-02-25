"""
User management service — registration, authentication, and JWT token management.

Handles:
- User registration with email/password (bcrypt hashed)
- Authentication with JWT access + refresh token generation
- Token refresh for expired access tokens
- Profile retrieval and updates

Security:
- Passwords hashed with bcrypt (12 salt rounds by default)
- Access tokens: short-lived (15 min, configurable)
- Refresh tokens: long-lived (7 days, configurable)
- Tokens signed with HS256 using app secret_key
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.core.exceptions import KonvertItError
from app.db.models import User
from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


# ─── Auth-Specific Exceptions ────────────────────────────────


class AuthenticationError(KonvertItError):
    """Invalid credentials or authentication failure."""
    pass


class RegistrationError(KonvertItError):
    """Registration failed (duplicate email, validation, etc.)."""
    pass


class TokenError(KonvertItError):
    """JWT token is invalid, expired, or malformed."""
    pass


# ─── Token Payload Type ─────────────────────────────────────


TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


# ─── Service ────────────────────────────────────────────────


class UserService:
    """
    Manages user accounts, authentication, and JWT token lifecycle.

    Usage:
        service = UserService(user_repo)
        tokens = await service.register("user@example.com", "securepass123")
        tokens = await service.authenticate("user@example.com", "securepass123")
        new_tokens = await service.refresh_access_token(refresh_token)
    """

    BCRYPT_ROUNDS = 12

    def __init__(
        self,
        user_repo: UserRepository,
        settings: Settings | None = None,
    ):
        self._repo = user_repo
        self._settings = settings or get_settings()

    # ─── Registration ────────────────────────────────────────

    async def register(self, email: str, password: str) -> dict:
        """
        Register a new user account.

        Args:
            email: User's email address (will be lowercased).
            password: Plain-text password (must be >= 8 chars).

        Returns:
            Dict with user info and JWT tokens:
            {
                "user": {"id", "email", "tier", "created_at"},
                "access_token": str,
                "refresh_token": str,
                "token_type": "bearer",
            }

        Raises:
            RegistrationError: If email is taken or validation fails.
        """
        email = email.strip().lower()

        # Validate
        if not email or "@" not in email:
            raise RegistrationError("Invalid email address")
        if len(password) < 8:
            raise RegistrationError(
                "Password must be at least 8 characters"
            )

        # Check uniqueness
        if await self._repo.email_exists(email):
            raise RegistrationError(
                f"Email '{email}' is already registered"
            )

        # Hash password
        password_hash = self._hash_password(password)

        # Create user
        user = await self._repo.create(
            email=email,
            password_hash=password_hash,
            tier="free",
            is_active=True,
        )

        logger.info(f"Registered new user: {email} (id: {user.id})")

        # Generate tokens
        access_token = self._create_token(
            user_id=str(user.id),
            email=user.email,
            tier=user.tier,
            token_type=TOKEN_TYPE_ACCESS,
        )
        refresh_token = self._create_token(
            user_id=str(user.id),
            email=user.email,
            tier=user.tier,
            token_type=TOKEN_TYPE_REFRESH,
        )

        return {
            "user": self._user_to_dict(user),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    # ─── Authentication ──────────────────────────────────────

    async def authenticate(self, email: str, password: str) -> dict:
        """
        Authenticate a user and return JWT tokens.

        Args:
            email: User's email address.
            password: Plain-text password to verify.

        Returns:
            Dict with user info and JWT tokens (same format as register).

        Raises:
            AuthenticationError: If credentials are invalid or user is inactive.
        """
        email = email.strip().lower()

        user = await self._repo.find_by_email(email)
        if user is None:
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        if not self._verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        # Update last login
        await self._repo.update_last_login(user.id)

        logger.info(f"User authenticated: {email}")

        # Generate tokens
        access_token = self._create_token(
            user_id=str(user.id),
            email=user.email,
            tier=user.tier,
            token_type=TOKEN_TYPE_ACCESS,
        )
        refresh_token = self._create_token(
            user_id=str(user.id),
            email=user.email,
            tier=user.tier,
            token_type=TOKEN_TYPE_REFRESH,
        )

        return {
            "user": self._user_to_dict(user),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    # ─── Token Refresh ───────────────────────────────────────

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Generate a new access token from a valid refresh token.

        If a user repository is available, reads the current tier from
        the database (handles Stripe webhook tier changes). Falls back
        to the tier stored in the refresh token if no repo is available.

        Args:
            refresh_token: A valid refresh token.

        Returns:
            Dict with new access token:
            {
                "access_token": str,
                "token_type": "bearer",
            }

        Raises:
            TokenError: If the refresh token is invalid or expired.
        """
        payload = self.verify_token(refresh_token)

        if payload.get("type") != TOKEN_TYPE_REFRESH:
            raise TokenError("Invalid token type — expected refresh token")

        # Read current tier from DB if repo available (handles Stripe updates)
        current_tier = payload.get("tier", "free")
        if self._repo is not None:
            try:
                user = await self._repo.get_by_id(uuid.UUID(payload["sub"]))
                if user:
                    current_tier = user.tier
            except Exception:
                pass  # Fall back to JWT tier on DB errors

        access_token = self._create_token(
            user_id=payload["sub"],
            email=payload.get("email", ""),
            tier=current_tier,
            token_type=TOKEN_TYPE_ACCESS,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    # ─── Token Verification ──────────────────────────────────

    def verify_token(self, token: str) -> dict:
        """
        Verify and decode a JWT token.

        Args:
            token: The JWT token string.

        Returns:
            Decoded payload dict with sub, email, tier, type, exp, iat.

        Raises:
            TokenError: If the token is invalid, expired, or malformed.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
            return payload
        except JWTError as e:
            raise TokenError(f"Invalid or expired token: {e}") from e

    # ─── Profile ──────────────────────────────────────────────

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get a user by their UUID string."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        return await self._repo.get_by_id(uid)

    async def update_profile(
        self,
        user_id: str,
        email: str | None = None,
        password: str | None = None,
    ) -> User | None:
        """
        Update a user's profile fields.

        Args:
            user_id: UUID string of the user.
            email: New email (optional).
            password: New password (optional, will be hashed).

        Returns:
            Updated User or None if not found.

        Raises:
            RegistrationError: If new email is already taken.
        """
        uid = uuid.UUID(user_id)
        kwargs = {}

        if email is not None:
            email = email.strip().lower()
            if not email or "@" not in email:
                raise RegistrationError("Invalid email address")

            existing = await self._repo.find_by_email(email)
            if existing and str(existing.id) != user_id:
                raise RegistrationError(
                    f"Email '{email}' is already registered"
                )
            kwargs["email"] = email

        if password is not None:
            if len(password) < 8:
                raise RegistrationError(
                    "Password must be at least 8 characters"
                )
            kwargs["password_hash"] = self._hash_password(password)

        if not kwargs:
            return await self._repo.get_by_id(uid)

        return await self._repo.update(uid, **kwargs)

    # ─── Password Hashing ────────────────────────────────────

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a bcrypt hash."""
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    # ─── JWT Token Creation ──────────────────────────────────

    def _create_token(
        self,
        user_id: str,
        email: str,
        tier: str,
        token_type: str,
    ) -> str:
        """
        Create a signed JWT token.

        Args:
            user_id: User UUID string (stored as 'sub' claim).
            email: User email (stored in payload).
            tier: User tier (free/pro/enterprise).
            token_type: "access" or "refresh".

        Returns:
            Encoded JWT string.
        """
        now = datetime.now(UTC)

        if token_type == TOKEN_TYPE_ACCESS:
            expires = now + timedelta(
                minutes=self._settings.jwt_access_token_expire_minutes
            )
        else:
            expires = now + timedelta(
                days=self._settings.jwt_refresh_token_expire_days
            )

        payload = {
            "sub": user_id,
            "email": email,
            "tier": tier,
            "type": token_type,
            "iat": now,
            "exp": expires,
        }

        return jwt.encode(
            payload,
            self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    # ─── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _user_to_dict(user: User) -> dict:
        """Serialize a User ORM instance to a safe dict (no password hash)."""
        return {
            "id": str(user.id),
            "email": user.email,
            "tier": user.tier,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
