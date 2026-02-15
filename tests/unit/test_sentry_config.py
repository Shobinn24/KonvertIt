"""Tests for app.core.sentry_config — Sentry initialization and event filtering."""

from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.config import AppEnv
from app.core.exceptions import KonvertItError, ScrapingError
from app.core.sentry_config import _filter_events, init_sentry


class TestInitSentry:
    """Verify Sentry SDK initialization behavior."""

    @patch("app.core.sentry_config.sentry_sdk.init")
    def test_skips_init_when_dsn_empty(self, mock_init: MagicMock):
        init_sentry(dsn="", app_env=AppEnv.PRODUCTION, app_version="0.1.0")
        mock_init.assert_not_called()

    @patch("app.core.sentry_config.sentry_sdk.init")
    def test_initializes_with_valid_dsn(self, mock_init: MagicMock):
        init_sentry(
            dsn="https://key@sentry.io/123",
            app_env=AppEnv.PRODUCTION,
            app_version="0.1.0",
            traces_sample_rate=0.2,
            profiles_sample_rate=0.05,
        )
        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["dsn"] == "https://key@sentry.io/123"
        assert call_kwargs["environment"] == "production"
        assert call_kwargs["release"] == "konvertit@0.1.0"
        assert call_kwargs["traces_sample_rate"] == 0.2
        assert call_kwargs["profiles_sample_rate"] == 0.05
        assert call_kwargs["send_default_pii"] is False
        assert call_kwargs["before_send"] is _filter_events

    @patch("app.core.sentry_config.sentry_sdk.init")
    def test_uses_environment_value(self, mock_init: MagicMock):
        init_sentry(dsn="https://key@sentry.io/1", app_env=AppEnv.STAGING, app_version="0.2.0")
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["environment"] == "staging"


class TestFilterEvents:
    """Verify Sentry event filtering logic."""

    def test_drops_4xx_http_exception(self):
        event = {"exception": {"values": [{"type": "HTTPException"}]}}
        hint = {"exc_info": (HTTPException, HTTPException(status_code=404), None)}
        result = _filter_events(event, hint)
        assert result is None

    def test_drops_400_http_exception(self):
        event = {"exception": {}}
        hint = {"exc_info": (HTTPException, HTTPException(status_code=400), None)}
        result = _filter_events(event, hint)
        assert result is None

    def test_drops_429_http_exception(self):
        event = {"exception": {}}
        hint = {"exc_info": (HTTPException, HTTPException(status_code=429), None)}
        result = _filter_events(event, hint)
        assert result is None

    def test_keeps_500_http_exception(self):
        event = {"exception": {}}
        exc = HTTPException(status_code=500)
        hint = {"exc_info": (HTTPException, exc, None)}
        result = _filter_events(event, hint)
        assert result is event

    def test_tags_konvertit_error_subclass(self):
        event = {}
        exc = ScrapingError(message="timeout", details={"url": "https://example.com"})
        hint = {"exc_info": (ScrapingError, exc, None)}
        result = _filter_events(event, hint)
        assert result is not None
        assert result["tags"]["error_type"] == "ScrapingError"
        assert result["extra"]["url"] == "https://example.com"

    def test_tags_base_konvertit_error(self):
        event = {}
        exc = KonvertItError(message="generic error")
        hint = {"exc_info": (KonvertItError, exc, None)}
        result = _filter_events(event, hint)
        assert result is not None
        assert result["tags"]["error_type"] == "KonvertItError"

    def test_passes_regular_exception(self):
        event = {"exception": {}}
        exc = ValueError("bad value")
        hint = {"exc_info": (ValueError, exc, None)}
        result = _filter_events(event, hint)
        assert result is event

    def test_passes_event_without_exc_info(self):
        event = {"message": "something happened"}
        hint = {}
        result = _filter_events(event, hint)
        assert result is event
