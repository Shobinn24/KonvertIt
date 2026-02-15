"""Tests for app.core.logging_config — structured logging setup."""

import io
import json
import logging

from app.config import AppEnv
from app.core.logging_config import setup_logging


def _capture_log_output(app_env: AppEnv, log_format: str = "auto", log_level: str = "INFO"):
    """Helper: set up logging and capture output from a stdlib logger."""
    setup_logging(app_env=app_env, log_level=log_level, log_format=log_format)

    # Replace the root handler's stream with a StringIO for capture
    stream = io.StringIO()
    root = logging.getLogger()
    for h in root.handlers:
        h.stream = stream

    return stream


class TestSetupLoggingRenderer:
    """Verify correct renderer is selected based on env and format."""

    def test_development_auto_uses_console(self):
        stream = _capture_log_output(AppEnv.DEVELOPMENT, "auto")
        logger = logging.getLogger("test.dev.auto")
        logger.info("hello dev")
        output = stream.getvalue()
        # Console renderer produces human-readable output, not JSON
        assert "hello dev" in output
        # Should NOT be valid JSON (console format)
        try:
            json.loads(output.strip())
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json

    def test_production_auto_uses_json(self):
        stream = _capture_log_output(AppEnv.PRODUCTION, "auto")
        logger = logging.getLogger("test.prod.auto")
        logger.info("hello prod")
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["event"] == "hello prod"
        assert parsed["level"] == "info"

    def test_staging_auto_uses_json(self):
        stream = _capture_log_output(AppEnv.STAGING, "auto")
        logger = logging.getLogger("test.staging.auto")
        logger.info("hello staging")
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["event"] == "hello staging"

    def test_explicit_json_overrides_dev(self):
        stream = _capture_log_output(AppEnv.DEVELOPMENT, "json")
        logger = logging.getLogger("test.dev.json")
        logger.info("forced json")
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["event"] == "forced json"

    def test_explicit_console_overrides_prod(self):
        stream = _capture_log_output(AppEnv.PRODUCTION, "console")
        logger = logging.getLogger("test.prod.console")
        logger.info("forced console")
        output = stream.getvalue()
        assert "forced console" in output
        try:
            json.loads(output.strip())
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
        assert not is_json


class TestSetupLoggingLevel:
    """Verify root logger level is set correctly."""

    def test_sets_root_level_warning(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT, log_level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_sets_root_level_debug(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT, log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_default_level_is_info(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT)
        root = logging.getLogger()
        assert root.level == logging.INFO


class TestExistingStdlibLoggers:
    """Verify existing stdlib loggers produce structured output."""

    def test_stdlib_logger_produces_json_in_production(self):
        stream = _capture_log_output(AppEnv.PRODUCTION, "json")
        # Simulate an existing logger like app.services.user_service
        logger = logging.getLogger("app.services.user_service")
        logger.info("Registered new user: test@example.com")
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert "Registered new user" in parsed["event"]
        assert parsed["logger"] == "app.services.user_service"

    def test_stdlib_logger_includes_timestamp(self):
        stream = _capture_log_output(AppEnv.PRODUCTION, "json")
        logger = logging.getLogger("test.timestamp")
        logger.info("check timestamp")
        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert "timestamp" in parsed


class TestNoisyLoggers:
    """Verify noisy third-party loggers are quieted."""

    def test_uvicorn_access_set_to_warning(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT)
        assert logging.getLogger("uvicorn.access").level == logging.WARNING

    def test_sqlalchemy_engine_set_to_warning(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT)
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING

    def test_httpx_set_to_warning(self):
        setup_logging(app_env=AppEnv.DEVELOPMENT)
        assert logging.getLogger("httpx").level == logging.WARNING
