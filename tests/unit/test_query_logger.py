"""Tests for app.db.query_logger — slow query detection via SQLAlchemy events."""

import time
from unittest.mock import MagicMock, patch

from app.db.query_logger import attach_query_logger


class _FakeConnInfo(dict):
    """Simulates the conn.info dict for SQLAlchemy connection events."""
    pass


def _make_mock_engine():
    """Create a mock async engine with a sync engine and event listeners."""
    engine = MagicMock()
    sync_engine = MagicMock()
    engine.sync_engine = sync_engine
    return engine, sync_engine


class TestAttachQueryLogger:
    """Verify that attach_query_logger registers event listeners."""

    def test_registers_before_and_after_events(self):
        engine, sync_engine = _make_mock_engine()
        with patch("app.db.query_logger.event") as mock_event:
            attach_query_logger(engine)
            calls = mock_event.listens_for.call_args_list
            events_registered = [c[0][1] for c in calls]
            assert "before_cursor_execute" in events_registered
            assert "after_cursor_execute" in events_registered


class TestSlowQueryDetection:
    """Test the slow query detection logic via the event handlers."""

    def _get_handlers(self):
        """Extract before/after handlers by invoking attach_query_logger."""
        engine, sync_engine = _make_mock_engine()
        handlers = {}

        def fake_listens_for(target, event_name):
            def decorator(fn):
                handlers[event_name] = fn
                return fn
            return decorator

        with patch("app.db.query_logger.event") as mock_event:
            mock_event.listens_for = fake_listens_for
            attach_query_logger(engine)

        return handlers

    def test_fast_query_not_logged(self):
        handlers = self._get_handlers()
        conn = MagicMock()
        conn.info = {}

        with patch("app.db.query_logger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.query_slow_threshold_ms = 200
            mock_settings.return_value = settings

            with patch("app.db.query_logger.logger") as mock_logger:
                # Simulate a fast query
                handlers["before_cursor_execute"](conn, None, "SELECT 1", None, None, False)
                # No delay — immediate after
                handlers["after_cursor_execute"](conn, None, "SELECT 1", None, None, False)
                mock_logger.warning.assert_not_called()

    def test_slow_query_logged(self):
        handlers = self._get_handlers()
        conn = MagicMock()
        conn.info = {}

        with patch("app.db.query_logger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.query_slow_threshold_ms = 0  # 0ms threshold — everything is slow
            mock_settings.return_value = settings

            with patch("app.db.query_logger.logger") as mock_logger:
                handlers["before_cursor_execute"](conn, None, "SELECT * FROM users", None, None, False)
                # Small delay to ensure elapsed > 0
                time.sleep(0.001)
                handlers["after_cursor_execute"](conn, None, "SELECT * FROM users", None, None, False)
                mock_logger.warning.assert_called_once()
                call_kwargs = mock_logger.warning.call_args
                assert "slow_query_detected" in str(call_kwargs)

    def test_no_error_when_no_start_time(self):
        handlers = self._get_handlers()
        conn = MagicMock()
        conn.info = {}

        with patch("app.db.query_logger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.query_slow_threshold_ms = 200
            mock_settings.return_value = settings

            with patch("app.db.query_logger.logger") as mock_logger:
                # Call after without calling before — should not raise
                handlers["after_cursor_execute"](conn, None, "SELECT 1", None, None, False)
                mock_logger.warning.assert_not_called()

    def test_long_statement_truncated(self):
        handlers = self._get_handlers()
        conn = MagicMock()
        conn.info = {}

        with patch("app.db.query_logger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.query_slow_threshold_ms = 0
            mock_settings.return_value = settings

            with patch("app.db.query_logger.logger") as mock_logger:
                long_stmt = "SELECT " + "x" * 1000
                handlers["before_cursor_execute"](conn, None, long_stmt, None, None, False)
                time.sleep(0.001)
                handlers["after_cursor_execute"](conn, None, long_stmt, None, None, False)
                call_kwargs = mock_logger.warning.call_args
                extra = call_kwargs[1]["extra"] if "extra" in call_kwargs[1] else call_kwargs[1]
                if "extra" in call_kwargs[1]:
                    assert len(call_kwargs[1]["extra"]["statement"]) <= 500

    def test_multiple_queries_tracked_independently(self):
        handlers = self._get_handlers()
        conn = MagicMock()
        conn.info = {}

        with patch("app.db.query_logger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.query_slow_threshold_ms = 0
            mock_settings.return_value = settings

            with patch("app.db.query_logger.logger") as mock_logger:
                # Start two queries
                handlers["before_cursor_execute"](conn, None, "Q1", None, None, False)
                handlers["before_cursor_execute"](conn, None, "Q2", None, None, False)
                time.sleep(0.001)
                # End in LIFO order (stack)
                handlers["after_cursor_execute"](conn, None, "Q2", None, None, False)
                handlers["after_cursor_execute"](conn, None, "Q1", None, None, False)
                assert mock_logger.warning.call_count == 2
