"""Tests for production safety enforcement in Settings."""

import pytest

from app.config import AppEnv, Settings


# Valid production values for reuse
VALID_SECRET = "a" * 64
VALID_ENCRYPTION = "ZmVybmV0LWtleS10aGF0LWlzLXZhbGlk"
VALID_CORS = "https://konvert-it.vercel.app"


def _settings(**overrides) -> Settings:
    """Create Settings isolated from .env file and OS env vars."""
    return Settings(_env_file=None, **overrides)


class TestProductionSafetyValidator:
    """Verify Settings blocks boot when production invariants are violated."""

    def test_development_allows_placeholder_defaults(self):
        """Dev mode should not raise even with placeholder secrets."""
        s = _settings(app_env=AppEnv.DEVELOPMENT)
        assert s.secret_key == "change-me-to-a-random-64-char-string"
        assert "change-me" in s.encryption_key

    def test_production_rejects_default_secret_key(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=False,
                encryption_key=VALID_ENCRYPTION,
                cors_allowed_origins=VALID_CORS,
            )

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=False,
                secret_key="tooshort",
                encryption_key=VALID_ENCRYPTION,
                cors_allowed_origins=VALID_CORS,
            )

    def test_production_rejects_default_encryption_key(self):
        with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=False,
                secret_key=VALID_SECRET,
                cors_allowed_origins=VALID_CORS,
            )

    def test_production_rejects_empty_cors(self):
        with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=False,
                secret_key=VALID_SECRET,
                encryption_key=VALID_ENCRYPTION,
                cors_allowed_origins="",
            )

    def test_production_rejects_debug_true(self):
        with pytest.raises(ValueError, match="APP_DEBUG"):
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=True,
                secret_key=VALID_SECRET,
                encryption_key=VALID_ENCRYPTION,
                cors_allowed_origins=VALID_CORS,
            )

    def test_production_valid_config_passes(self):
        """A fully valid production config should not raise."""
        s = _settings(
            app_env=AppEnv.PRODUCTION,
            app_debug=False,
            secret_key=VALID_SECRET,
            encryption_key=VALID_ENCRYPTION,
            cors_allowed_origins=VALID_CORS,
        )
        assert s.is_production is True

    def test_multiple_violations_reported(self):
        """All violations should be reported in a single error."""
        with pytest.raises(ValueError) as exc_info:
            _settings(
                app_env=AppEnv.PRODUCTION,
                app_debug=True,
                cors_allowed_origins="",
            )
        msg = str(exc_info.value)
        assert "APP_DEBUG" in msg
        assert "SECRET_KEY" in msg
        assert "ENCRYPTION_KEY" in msg
        assert "CORS_ALLOWED_ORIGINS" in msg


class TestDatabaseUrlNormalization:
    """Verify the existing database URL normalization still works."""

    def test_postgresql_prefix_normalized(self):
        s = _settings(database_url="postgresql://user:pass@host/db")
        assert s.database_url == "postgresql+asyncpg://user:pass@host/db"

    def test_postgres_prefix_normalized(self):
        s = _settings(database_url="postgres://user:pass@host/db")
        assert s.database_url == "postgresql+asyncpg://user:pass@host/db"

    def test_asyncpg_prefix_unchanged(self):
        s = _settings(database_url="postgresql+asyncpg://user:pass@host/db")
        assert s.database_url == "postgresql+asyncpg://user:pass@host/db"
