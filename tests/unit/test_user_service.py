"""
Unit tests for UserService — registration, authentication, JWT token lifecycle.

Tests use an async SQLite in-memory database (same pattern as test_repositories.py).
Uses real bcrypt hashing and real JWT signing/verification.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import Base, User
from app.db.repositories.user_repo import UserRepository
from app.services.user_service import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    AuthenticationError,
    RegistrationError,
    TokenError,
    UserService,
)


# ─── Test Settings ───────────────────────────────────────────


def _test_settings() -> Settings:
    """Settings with a known secret for deterministic testing."""
    return Settings(
        secret_key="test-secret-key-for-unit-tests-only-64-chars-long-padding-here",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
    )


# ─── Database Fixtures ───────────────────────────────────────


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def user_repo(db_session):
    return UserRepository(db_session)


@pytest.fixture
def settings():
    return _test_settings()


@pytest.fixture
def service(user_repo, settings):
    return UserService(user_repo=user_repo, settings=settings)


# ─── Registration Tests ─────────────────────────────────────


class TestRegistration:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_success(self, service, db_session):
        """Should create user and return tokens."""
        result = await service.register("test@example.com", "securepass123")

        assert "user" in result
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

        # User info
        user = result["user"]
        assert user["email"] == "test@example.com"
        assert user["tier"] == "free"
        assert user["is_active"] is True
        assert "id" in user

    @pytest.mark.asyncio
    async def test_register_lowercases_email(self, service):
        """Email should be normalized to lowercase."""
        result = await service.register("Test@EXAMPLE.com", "securepass123")
        assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_strips_whitespace(self, service):
        """Email whitespace should be stripped."""
        result = await service.register("  test@example.com  ", "securepass123")
        assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, service):
        """Should reject duplicate email addresses."""
        await service.register("dup@example.com", "securepass123")

        with pytest.raises(RegistrationError, match="already registered"):
            await service.register("dup@example.com", "anotherpass123")

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, service):
        """Should reject invalid email addresses."""
        with pytest.raises(RegistrationError, match="Invalid email"):
            await service.register("not-an-email", "securepass123")

    @pytest.mark.asyncio
    async def test_register_empty_email(self, service):
        """Should reject empty email."""
        with pytest.raises(RegistrationError, match="Invalid email"):
            await service.register("", "securepass123")

    @pytest.mark.asyncio
    async def test_register_short_password(self, service):
        """Should reject passwords shorter than 8 characters."""
        with pytest.raises(RegistrationError, match="at least 8"):
            await service.register("test@example.com", "short")

    @pytest.mark.asyncio
    async def test_register_returns_valid_access_token(self, service, settings):
        """Access token should be verifiable and contain correct claims."""
        result = await service.register("test@example.com", "securepass123")

        payload = jwt.decode(
            result["access_token"],
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["email"] == "test@example.com"
        assert payload["tier"] == "free"
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert "sub" in payload
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_register_returns_valid_refresh_token(self, service, settings):
        """Refresh token should be verifiable with correct type."""
        result = await service.register("test@example.com", "securepass123")

        payload = jwt.decode(
            result["refresh_token"],
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["type"] == TOKEN_TYPE_REFRESH
        assert payload["email"] == "test@example.com"


# ─── Authentication Tests ────────────────────────────────────


class TestAuthentication:
    """Tests for user login authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, service):
        """Should authenticate with correct credentials."""
        await service.register("auth@example.com", "securepass123")
        result = await service.authenticate("auth@example.com", "securepass123")

        assert result["user"]["email"] == "auth@example.com"
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, service):
        """Should reject incorrect passwords."""
        await service.register("auth@example.com", "securepass123")

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await service.authenticate("auth@example.com", "wrongpass123")

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_email(self, service):
        """Should reject email that doesn't exist."""
        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await service.authenticate("nobody@example.com", "securepass123")

    @pytest.mark.asyncio
    async def test_authenticate_deactivated_user(self, service, user_repo):
        """Should reject login for deactivated accounts."""
        await service.register("deactivated@example.com", "securepass123")
        user = await user_repo.find_by_email("deactivated@example.com")
        user.is_active = False
        await user_repo.session.flush()

        with pytest.raises(AuthenticationError, match="deactivated"):
            await service.authenticate("deactivated@example.com", "securepass123")

    @pytest.mark.asyncio
    async def test_authenticate_case_insensitive_email(self, service):
        """Should authenticate regardless of email case."""
        await service.register("auth@example.com", "securepass123")
        result = await service.authenticate("AUTH@EXAMPLE.COM", "securepass123")
        assert result["user"]["email"] == "auth@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_updates_last_login(self, service, user_repo):
        """Should update last_login timestamp on successful auth."""
        await service.register("login@example.com", "securepass123")
        user_before = await user_repo.find_by_email("login@example.com")
        login_before = user_before.last_login

        await service.authenticate("login@example.com", "securepass123")
        user_after = await user_repo.find_by_email("login@example.com")

        assert user_after.last_login is not None
        if login_before is not None:
            assert user_after.last_login >= login_before


# ─── Token Refresh Tests ─────────────────────────────────────


class TestTokenRefresh:
    """Tests for JWT token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, service, settings):
        """Should issue new access token from valid refresh token."""
        reg = await service.register("refresh@example.com", "securepass123")
        result = service.refresh_access_token(reg["refresh_token"])

        assert "access_token" in result
        assert result["token_type"] == "bearer"

        # New access token should be valid
        payload = jwt.decode(
            result["access_token"],
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert payload["email"] == "refresh@example.com"

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, service):
        """Should reject access tokens used as refresh tokens."""
        reg = await service.register("test@example.com", "securepass123")

        with pytest.raises(TokenError, match="expected refresh token"):
            service.refresh_access_token(reg["access_token"])

    def test_refresh_with_invalid_token(self, service):
        """Should reject invalid/malformed tokens."""
        with pytest.raises(TokenError, match="Invalid or expired"):
            service.refresh_access_token("not-a-valid-token")

    def test_refresh_with_expired_token(self, service, settings):
        """Should reject expired refresh tokens."""
        # Create a token that's already expired
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "email": "expired@test.com",
            "tier": "free",
            "type": TOKEN_TYPE_REFRESH,
            "iat": datetime.now(UTC) - timedelta(days=10),
            "exp": datetime.now(UTC) - timedelta(days=1),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )

        with pytest.raises(TokenError, match="Invalid or expired"):
            service.refresh_access_token(expired_token)


# ─── Token Verification Tests ────────────────────────────────


class TestTokenVerification:
    """Tests for JWT token verification."""

    @pytest.mark.asyncio
    async def test_verify_valid_access_token(self, service):
        """Should decode a valid access token."""
        reg = await service.register("verify@example.com", "securepass123")
        payload = service.verify_token(reg["access_token"])

        assert payload["email"] == "verify@example.com"
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert "sub" in payload
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_verify_valid_refresh_token(self, service):
        """Should decode a valid refresh token."""
        reg = await service.register("verify@example.com", "securepass123")
        payload = service.verify_token(reg["refresh_token"])

        assert payload["type"] == TOKEN_TYPE_REFRESH

    def test_verify_invalid_token(self, service):
        """Should raise TokenError for garbage tokens."""
        with pytest.raises(TokenError):
            service.verify_token("garbage.token.here")

    def test_verify_wrong_secret(self, service, settings):
        """Should reject tokens signed with a different secret."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@test.com",
            "tier": "free",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

        with pytest.raises(TokenError):
            service.verify_token(token)


# ─── Password Hashing Tests ─────────────────────────────────


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_password(self, service):
        """Hashed password should not equal the plain text."""
        hashed = service._hash_password("mypassword123")
        assert hashed != "mypassword123"
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_correct_password(self, service):
        """Correct password should verify against its hash."""
        hashed = service._hash_password("mypassword123")
        assert service._verify_password("mypassword123", hashed) is True

    def test_verify_wrong_password(self, service):
        """Wrong password should fail verification."""
        hashed = service._hash_password("mypassword123")
        assert service._verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self, service):
        """Same password should produce different hashes (salt)."""
        hash1 = service._hash_password("samepassword")
        hash2 = service._hash_password("samepassword")
        assert hash1 != hash2  # Different salts

    def test_both_hashes_verify(self, service):
        """Both different hashes should verify the same password."""
        hash1 = service._hash_password("samepassword")
        hash2 = service._hash_password("samepassword")
        assert service._verify_password("samepassword", hash1) is True
        assert service._verify_password("samepassword", hash2) is True


# ─── JWT Token Creation Tests ────────────────────────────────


class TestTokenCreation:
    """Tests for JWT token creation internals."""

    def test_access_token_has_short_expiry(self, service, settings):
        """Access token should expire in configured minutes."""
        token = service._create_token(
            user_id=str(uuid.uuid4()),
            email="test@test.com",
            tier="free",
            token_type=TOKEN_TYPE_ACCESS,
        )
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )

        iat = payload["iat"]
        exp = payload["exp"]
        # Should be roughly 15 minutes apart
        delta = exp - iat
        assert 14 * 60 <= delta <= 16 * 60

    def test_refresh_token_has_long_expiry(self, service, settings):
        """Refresh token should expire in configured days."""
        token = service._create_token(
            user_id=str(uuid.uuid4()),
            email="test@test.com",
            tier="free",
            token_type=TOKEN_TYPE_REFRESH,
        )
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )

        iat = payload["iat"]
        exp = payload["exp"]
        # Should be roughly 7 days apart
        delta = exp - iat
        assert 6 * 86400 <= delta <= 8 * 86400

    def test_token_contains_all_claims(self, service, settings):
        """Token should contain sub, email, tier, type, iat, exp."""
        user_id = str(uuid.uuid4())
        token = service._create_token(
            user_id=user_id,
            email="claims@test.com",
            tier="pro",
            token_type=TOKEN_TYPE_ACCESS,
        )
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )

        assert payload["sub"] == user_id
        assert payload["email"] == "claims@test.com"
        assert payload["tier"] == "pro"
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert "iat" in payload
        assert "exp" in payload


# ─── Profile Management Tests ────────────────────────────────


class TestProfileManagement:
    """Tests for user profile retrieval and updates."""

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, service):
        """Should retrieve user by UUID string."""
        reg = await service.register("profile@example.com", "securepass123")
        user_id = reg["user"]["id"]

        user = await service.get_user_by_id(user_id)
        assert user is not None
        assert user.email == "profile@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_invalid_id(self, service):
        """Should return None for invalid UUID."""
        user = await service.get_user_by_id("not-a-uuid")
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_nonexistent_id(self, service):
        """Should return None for nonexistent UUID."""
        user = await service.get_user_by_id(str(uuid.uuid4()))
        assert user is None

    @pytest.mark.asyncio
    async def test_update_email(self, service):
        """Should update user's email."""
        reg = await service.register("old@example.com", "securepass123")
        user_id = reg["user"]["id"]

        updated = await service.update_profile(user_id, email="new@example.com")
        assert updated is not None
        assert updated.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_update_password(self, service):
        """Should update user's password."""
        reg = await service.register("pass@example.com", "oldpass12345")
        user_id = reg["user"]["id"]

        await service.update_profile(user_id, password="newpass12345")

        # Old password should fail
        with pytest.raises(AuthenticationError):
            await service.authenticate("pass@example.com", "oldpass12345")

        # New password should work
        result = await service.authenticate("pass@example.com", "newpass12345")
        assert result["user"]["email"] == "pass@example.com"

    @pytest.mark.asyncio
    async def test_update_email_duplicate(self, service):
        """Should reject email change to an existing email."""
        await service.register("user1@example.com", "securepass123")
        reg2 = await service.register("user2@example.com", "securepass123")

        with pytest.raises(RegistrationError, match="already registered"):
            await service.update_profile(
                reg2["user"]["id"], email="user1@example.com"
            )

    @pytest.mark.asyncio
    async def test_update_no_changes(self, service):
        """Should return user unchanged when no fields provided."""
        reg = await service.register("nochange@example.com", "securepass123")
        user_id = reg["user"]["id"]

        updated = await service.update_profile(user_id)
        assert updated is not None
        assert updated.email == "nochange@example.com"

    @pytest.mark.asyncio
    async def test_update_short_password(self, service):
        """Should reject password change to short password."""
        reg = await service.register("short@example.com", "securepass123")

        with pytest.raises(RegistrationError, match="at least 8"):
            await service.update_profile(reg["user"]["id"], password="short")


# ─── User Serialization Tests ────────────────────────────────


class TestUserSerialization:
    """Tests for _user_to_dict helper."""

    @pytest.mark.asyncio
    async def test_user_to_dict_excludes_password(self, service):
        """Serialized user dict should not contain password hash."""
        reg = await service.register("serial@example.com", "securepass123")
        user_dict = reg["user"]

        assert "password_hash" not in user_dict
        assert "password" not in user_dict

    @pytest.mark.asyncio
    async def test_user_to_dict_contains_required_fields(self, service):
        """Serialized user dict should have id, email, tier, is_active."""
        reg = await service.register("fields@example.com", "securepass123")
        user_dict = reg["user"]

        assert "id" in user_dict
        assert "email" in user_dict
        assert "tier" in user_dict
        assert "is_active" in user_dict
        assert "created_at" in user_dict
