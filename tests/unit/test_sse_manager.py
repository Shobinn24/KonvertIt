"""
Unit tests for SSE Progress Manager and bulk conversion with progress streaming.

Tests:
- SSEEvent formatting (SSE spec compliance)
- JobState lifecycle (create, progress, complete, cancel)
- SSEProgressManager (event emission, subscription, cleanup)
- ConversionService callback integration (on_step, on_item_complete, cancel_check)
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ScrapingError
from app.core.models import (
    ComplianceResult,
    ConversionStatus,
    ListingDraft,
    ListingResult,
    ListingStatus,
    ProfitBreakdown,
    RiskLevel,
    ScrapedProduct,
    SourceMarketplace,
    TargetMarketplace,
)
from app.services.conversion_service import (
    BulkConversionProgress,
    ConversionResult,
    ConversionService,
    ConversionStep,
)
from app.services.sse_manager import (
    JobState,
    SSEEvent,
    SSEEventType,
    SSEProgressManager,
)


# ─── SSEEvent Tests ──────────────────────────────────────


class TestSSEEvent:
    """Tests for SSE event formatting."""

    def test_basic_format(self):
        """Should format a basic event with event type and data."""
        event = SSEEvent(
            event=SSEEventType.JOB_STARTED,
            data={"job_id": "abc-123", "total": 5},
        )
        formatted = event.format()

        assert "event: job_started\n" in formatted
        assert 'data: {"job_id": "abc-123", "total": 5}\n' in formatted
        assert formatted.endswith("\n\n")

    def test_format_with_id(self):
        """Should include id field when provided."""
        event = SSEEvent(
            event=SSEEventType.ITEM_COMPLETED,
            data={"index": 0},
            id="evt-001",
        )
        formatted = event.format()

        assert "id: evt-001\n" in formatted
        assert "event: item_completed\n" in formatted

    def test_format_with_retry(self):
        """Should include retry field when provided."""
        event = SSEEvent(
            event=SSEEventType.ERROR,
            data={"error": "timeout"},
            retry=3000,
        )
        formatted = event.format()

        assert "retry: 3000\n" in formatted
        assert "event: error\n" in formatted

    def test_format_with_all_fields(self):
        """Should include all fields in correct order."""
        event = SSEEvent(
            event=SSEEventType.JOB_PROGRESS,
            data={"progress_pct": 50.0},
            id="evt-042",
            retry=5000,
        )
        formatted = event.format()
        lines = formatted.strip().split("\n")

        # Order: id, retry, event, data
        assert lines[0] == "id: evt-042"
        assert lines[1] == "retry: 5000"
        assert lines[2] == "event: job_progress"
        assert lines[3].startswith("data: ")

    def test_data_is_valid_json(self):
        """Data field should be valid JSON."""
        event = SSEEvent(
            event=SSEEventType.ITEM_STEP,
            data={"url": "https://amazon.com/dp/TEST", "step": "scraping"},
        )
        formatted = event.format()

        # Extract the data line
        for line in formatted.split("\n"):
            if line.startswith("data: "):
                json_str = line[len("data: "):]
                parsed = json.loads(json_str)
                assert parsed["step"] == "scraping"
                break

    def test_heartbeat_format(self):
        """Heartbeat events should have correct type."""
        event = SSEEvent(
            event=SSEEventType.HEARTBEAT,
            data={"job_id": "abc", "timestamp": "2026-02-07T12:00:00"},
        )
        formatted = event.format()
        assert "event: heartbeat\n" in formatted


# ─── JobState Tests ──────────────────────────────────────


class TestJobState:
    """Tests for job state tracking."""

    def test_initial_state(self):
        """New job should start with correct defaults."""
        job = JobState(job_id="job-1", total=5, urls=["u1", "u2", "u3", "u4", "u5"])

        assert job.completed == 0
        assert job.failed == 0
        assert job.pending == 5
        assert job.progress_pct == 0.0
        assert not job.is_done
        assert not job.is_cancelled

    def test_progress_tracking(self):
        """Progress should update correctly as items complete."""
        job = JobState(job_id="job-1", total=4)
        job.completed = 2
        job.failed = 1

        assert job.pending == 1
        assert job.progress_pct == 75.0
        assert not job.is_done

    def test_is_done_when_all_processed(self):
        """Job should be done when all items are processed."""
        job = JobState(job_id="job-1", total=3, completed=2, failed=1)

        assert job.is_done
        assert job.progress_pct == 100.0

    def test_is_done_when_cancelled(self):
        """Job should be done when cancelled."""
        job = JobState(job_id="job-1", total=5, completed=1)
        job.is_cancelled = True

        assert job.is_done

    def test_empty_job_is_done(self):
        """Empty job (0 URLs) should be immediately done."""
        job = JobState(job_id="job-1", total=0)

        assert job.is_done
        assert job.progress_pct == 100.0

    def test_to_dict(self):
        """Should serialize to dict with all fields."""
        job = JobState(job_id="job-1", total=10, completed=4, failed=2)
        d = job.to_dict()

        assert d["job_id"] == "job-1"
        assert d["total"] == 10
        assert d["completed"] == 4
        assert d["failed"] == 2
        assert d["pending"] == 4
        assert d["progress_pct"] == 60.0
        assert d["is_done"] is False
        assert d["is_cancelled"] is False


# ─── SSEProgressManager Tests ─────────────────────────────


class TestSSEProgressManager:
    """Tests for the SSE progress manager."""

    def test_create_job(self):
        """Should create a job with unique ID and correct state."""
        manager = SSEProgressManager()
        urls = ["https://amazon.com/dp/TEST1", "https://amazon.com/dp/TEST2"]
        job_id = manager.create_job(urls)

        assert job_id is not None
        assert len(job_id) > 0

        job = manager.get_job(job_id)
        assert job is not None
        assert job.total == 2
        assert job.urls == urls

    def test_create_multiple_jobs(self):
        """Should create separate jobs with unique IDs."""
        manager = SSEProgressManager()
        job1 = manager.create_job(["url1"])
        job2 = manager.create_job(["url2", "url3"])

        assert job1 != job2
        assert manager.get_job(job1).total == 1
        assert manager.get_job(job2).total == 2

    def test_get_nonexistent_job(self):
        """Should return None for unknown job IDs."""
        manager = SSEProgressManager()
        assert manager.get_job("nonexistent") is None

    def test_active_jobs(self):
        """Should only return non-done jobs."""
        manager = SSEProgressManager()
        job1 = manager.create_job(["url1"])
        job2 = manager.create_job(["url2"])

        # Complete job1
        manager._jobs[job1].completed = 1

        active = manager.active_jobs
        assert job1 not in active
        assert job2 in active

    def test_cancel_job(self):
        """Should cancel an active job."""
        manager = SSEProgressManager()
        job_id = manager.create_job(["url1", "url2"])

        result = manager.cancel_job(job_id)
        assert result is True

        job = manager.get_job(job_id)
        assert job.is_cancelled

    def test_cancel_nonexistent_job(self):
        """Should return False for unknown job ID."""
        manager = SSEProgressManager()
        assert manager.cancel_job("nonexistent") is False

    def test_cancel_already_done_job(self):
        """Should return False for already completed job."""
        manager = SSEProgressManager()
        job_id = manager.create_job(["url1"])
        manager._jobs[job_id].completed = 1  # Mark as done

        assert manager.cancel_job(job_id) is False

    def test_cleanup_job(self):
        """Should remove a job from memory."""
        manager = SSEProgressManager()
        job_id = manager.create_job(["url1"])
        manager.cleanup_job(job_id)

        assert manager.get_job(job_id) is None

    def test_cleanup_finished_jobs(self):
        """Should remove all finished jobs."""
        manager = SSEProgressManager()
        done_id = manager.create_job(["url1"])
        active_id = manager.create_job(["url2", "url3"])

        manager._jobs[done_id].completed = 1  # Mark as done

        count = manager.cleanup_finished_jobs()
        assert count == 1
        assert manager.get_job(done_id) is None
        assert manager.get_job(active_id) is not None

    @pytest.mark.asyncio
    async def test_emit_and_subscribe(self):
        """Should emit events and receive them via subscribe."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        job_id = manager.create_job(["url1"])

        # Emit events
        await manager.emit_job_started(job_id)
        await manager.emit_job_completed(job_id)  # Sends None sentinel

        # Subscribe and collect events
        events = []
        async for event_str in manager.subscribe(job_id):
            events.append(event_str)

        assert len(events) == 2  # job_started + job_completed
        assert "event: job_started" in events[0]
        assert "event: job_completed" in events[1]

    @pytest.mark.asyncio
    async def test_emit_item_lifecycle(self):
        """Should emit item_started, item_step, item_completed in order."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        job_id = manager.create_job(["url1"])

        await manager.emit_item_started(job_id, 0, "url1")
        await manager.emit_item_step(job_id, 0, "url1", "scraping")
        await manager.emit_item_step(job_id, 0, "url1", "compliance")
        await manager.emit_item_completed(job_id, 0, "url1", True, {"title": "Test"})
        # emit_item_completed also emits job_progress
        await manager.emit_job_completed(job_id)

        events = []
        async for event_str in manager.subscribe(job_id):
            events.append(event_str)

        assert len(events) == 6  # started + 2 steps + completed + progress + job_completed
        assert "event: item_started" in events[0]
        assert "event: item_step" in events[1]
        assert "event: item_step" in events[2]
        assert "event: item_completed" in events[3]
        assert "event: job_progress" in events[4]
        assert "event: job_completed" in events[5]

    @pytest.mark.asyncio
    async def test_emit_item_completed_updates_state(self):
        """Should update job state when items complete."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        job_id = manager.create_job(["url1", "url2", "url3"])

        await manager.emit_item_completed(job_id, 0, "url1", True)
        await manager.emit_item_completed(job_id, 1, "url2", False, error="Failed")
        await manager.emit_item_completed(job_id, 2, "url3", True)

        job = manager.get_job(job_id)
        assert job.completed == 2
        assert job.failed == 1
        assert job.is_done

    @pytest.mark.asyncio
    async def test_heartbeat_on_timeout(self):
        """Should send heartbeat when no events arrive within interval."""
        manager = SSEProgressManager(heartbeat_interval=0.1)  # 100ms for test speed
        job_id = manager.create_job(["url1"])

        events = []

        async def collect():
            async for event_str in manager.subscribe(job_id):
                events.append(event_str)
                if len(events) >= 2:
                    break

        # Don't emit any events — let heartbeat trigger
        collect_task = asyncio.create_task(collect())

        # Wait for at least 2 heartbeats
        await asyncio.sleep(0.35)

        # End the stream
        await manager._queues[job_id].put(None)
        await collect_task

        # Should have received at least 2 heartbeats
        heartbeats = [e for e in events if "event: heartbeat" in e]
        assert len(heartbeats) >= 2

    @pytest.mark.asyncio
    async def test_emit_error_ends_stream(self):
        """Should emit error event and end the stream."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        job_id = manager.create_job(["url1"])

        await manager.emit_error(job_id, "Something went wrong")

        events = []
        async for event_str in manager.subscribe(job_id):
            events.append(event_str)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "Something went wrong" in events[0]

    @pytest.mark.asyncio
    async def test_emit_to_unknown_job(self):
        """Should not crash when emitting to unknown job."""
        manager = SSEProgressManager()

        # These should all silently return without error
        await manager.emit(
            "nonexistent",
            SSEEvent(event=SSEEventType.HEARTBEAT, data={}),
        )
        await manager.emit_job_started("nonexistent")
        await manager.emit_item_started("nonexistent", 0, "url")
        await manager.emit_item_step("nonexistent", 0, "url", "scraping")
        await manager.emit_item_completed("nonexistent", 0, "url", True)
        await manager.emit_job_completed("nonexistent")

    @pytest.mark.asyncio
    async def test_subscribe_unknown_job(self):
        """Should yield a single error event for unknown job."""
        manager = SSEProgressManager()

        events = []
        async for event_str in manager.subscribe("nonexistent"):
            events.append(event_str)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "Unknown job" in events[0]


# ─── ConversionService Callback Tests ────────────────────


class TestConversionServiceCallbacks:
    """Tests for ConversionService with progress callbacks."""

    @pytest.fixture
    def mock_scraper(self):
        scraper = AsyncMock()
        scraper.scrape = AsyncMock(return_value=ScrapedProduct(
            title="Test Product - Premium Quality Widget",
            price=25.99,
            brand="TestBrand",
            images=["https://example.com/img1.jpg"],
            description="A high-quality test product",
            category="Electronics > Gadgets",
            availability="In Stock",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B09TEST123",
            source_product_id="B09TEST123",
        ))
        return scraper

    @pytest.fixture
    def mock_compliance(self):
        compliance = MagicMock()
        compliance.check_product = MagicMock(return_value=ComplianceResult(
            is_compliant=True,
            brand="TestBrand",
            risk_level=RiskLevel.CLEAR,
            violations=[],
        ))
        return compliance

    @pytest.fixture
    def mock_profit_engine(self):
        engine = MagicMock()
        engine.suggest_price = MagicMock(return_value=39.99)
        engine.calculate_profit = MagicMock(return_value=ProfitBreakdown(
            cost=25.99,
            sell_price=39.99,
            ebay_fee=5.30,
            payment_fee=1.46,
            shipping_cost=5.00,
            profit=2.24,
            margin_pct=5.6,
        ))
        return engine

    @pytest.fixture
    def mock_converter(self):
        converter = MagicMock()
        converter.convert = MagicMock(return_value=ListingDraft(
            title="Test Product Premium Quality Widget",
            description_html="<p>A high-quality test product</p>",
            price=25.99,
            images=["https://example.com/img1.jpg"],
            sku="KI-B09TEST123",
            target_marketplace=TargetMarketplace.EBAY,
            source_product_id="B09TEST123",
            source_marketplace=SourceMarketplace.AMAZON,
        ))
        return converter

    @pytest.fixture
    def service(self, mock_compliance, mock_profit_engine, mock_converter):
        return ConversionService(
            proxy_manager=MagicMock(),
            browser_manager=MagicMock(),
            compliance_service=mock_compliance,
            profit_engine=mock_profit_engine,
            ebay_converter=mock_converter,
        )

    @pytest.mark.asyncio
    async def test_on_step_callback_called(self, service, mock_scraper):
        """Should call on_step for each pipeline step."""
        step_calls = []

        async def on_step(url: str, step: str) -> None:
            step_calls.append((url, step))

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                on_step=on_step,
            )

        # Should have called for: scraping, compliance, converting, pricing, complete
        steps = [s[1] for s in step_calls]
        assert "scraping" in steps
        assert "compliance" in steps
        assert "converting" in steps
        assert "pricing" in steps
        assert "complete" in steps

    @pytest.mark.asyncio
    async def test_on_step_callback_with_failure(self, service, mock_scraper):
        """Should call on_step up until the failure point."""
        mock_scraper.scrape.side_effect = ScrapingError("Bot detected")

        step_calls = []

        async def on_step(url: str, step: str) -> None:
            step_calls.append(step)

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                on_step=on_step,
            )

        assert result.status == ConversionStatus.FAILED
        # Only scraping step should have been notified before failure
        assert "scraping" in step_calls
        assert "compliance" not in step_calls

    @pytest.mark.asyncio
    async def test_on_step_not_called_when_none(self, service, mock_scraper):
        """Should work fine with no callback provided."""
        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            result = await service.convert_url(
                url="https://www.amazon.com/dp/B09TEST123",
                user_id="user-1",
                on_step=None,
            )

        assert result.status == ConversionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_bulk_on_item_complete_callback(self, service, mock_scraper):
        """Should call on_item_complete for each URL in bulk conversion."""
        item_completions = []

        async def on_item_complete(
            index: int, url: str, success: bool, result_data, error: str
        ) -> None:
            item_completions.append({"index": index, "url": url, "success": success})

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
        ]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            progress = await service.convert_bulk(
                urls=urls,
                user_id="user-1",
                on_item_complete=on_item_complete,
            )

        assert len(item_completions) == 2
        assert item_completions[0]["index"] == 0
        assert item_completions[0]["success"] is True
        assert item_completions[1]["index"] == 1
        assert item_completions[1]["success"] is True

    @pytest.mark.asyncio
    async def test_bulk_cancel_check(self, service, mock_scraper):
        """Should stop processing when cancel_check returns True."""
        call_count = 0

        def cancel_check() -> bool:
            nonlocal call_count
            call_count += 1
            # Cancel after first item
            return call_count > 1

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
        ]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            progress = await service.convert_bulk(
                urls=urls,
                user_id="user-1",
                cancel_check=cancel_check,
            )

        # Only first URL should have been processed
        assert progress.total == 3
        assert progress.completed == 1
        assert len(progress.results) == 1

    @pytest.mark.asyncio
    async def test_bulk_with_step_and_item_callbacks(self, service, mock_scraper):
        """Should fire both step and item callbacks during bulk conversion."""
        step_calls = []
        item_calls = []

        async def on_step(url: str, step: str) -> None:
            step_calls.append(step)

        async def on_item_complete(
            index, url, success, result_data, error
        ) -> None:
            item_calls.append(index)

        urls = ["https://www.amazon.com/dp/B09TEST001"]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            await service.convert_bulk(
                urls=urls,
                user_id="user-1",
                on_step=on_step,
                on_item_complete=on_item_complete,
            )

        # Step callback should have been called multiple times
        assert len(step_calls) >= 4  # at least scraping, compliance, converting, pricing, complete
        # Item callback should have been called once
        assert item_calls == [0]

    @pytest.mark.asyncio
    async def test_bulk_mixed_with_callbacks(self, service, mock_scraper):
        """Should correctly report success/failure via on_item_complete."""
        original_product = ScrapedProduct(
            title="Test Product - Premium Quality Widget",
            price=25.99,
            brand="TestBrand",
            images=["https://example.com/img1.jpg"],
            description="A high-quality test product",
            category="Electronics > Gadgets",
            availability="In Stock",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B09TEST123",
            source_product_id="B09TEST123",
        )
        call_count = 0

        async def scrape_side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ScrapingError("Bot detected on second URL")
            return original_product

        mock_scraper.scrape = AsyncMock(side_effect=scrape_side_effect)

        completions = []

        async def on_item_complete(
            index, url, success, result_data, error
        ) -> None:
            completions.append({"index": index, "success": success, "error": error})

        urls = [
            "https://www.amazon.com/dp/B09TEST001",
            "https://www.amazon.com/dp/B09TEST002",
            "https://www.amazon.com/dp/B09TEST003",
        ]

        with patch.object(service, "_get_scraper", return_value=mock_scraper):
            progress = await service.convert_bulk(
                urls=urls,
                user_id="user-1",
                on_item_complete=on_item_complete,
            )

        assert progress.completed == 2
        assert progress.failed == 1
        assert len(completions) == 3
        assert completions[0]["success"] is True
        assert completions[1]["success"] is False
        assert "Bot detected" in completions[1]["error"]
        assert completions[2]["success"] is True


# ─── Full SSE Integration Tests ──────────────────────────


class TestSSEIntegration:
    """Integration tests: SSEProgressManager + ConversionService callbacks."""

    @pytest.mark.asyncio
    async def test_full_sse_flow(self):
        """Should produce the full event lifecycle through SSE manager."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        urls = ["https://www.amazon.com/dp/B09TEST001", "https://www.amazon.com/dp/B09TEST002"]
        job_id = manager.create_job(urls)

        # Simulate the conversion emitting events
        await manager.emit_job_started(job_id)

        for i, url in enumerate(urls):
            await manager.emit_item_started(job_id, i, url)
            await manager.emit_item_step(job_id, i, url, "scraping")
            await manager.emit_item_step(job_id, i, url, "compliance")
            await manager.emit_item_step(job_id, i, url, "converting")
            await manager.emit_item_step(job_id, i, url, "pricing")
            await manager.emit_item_completed(
                job_id, i, url, True, {"title": f"Product {i}"}
            )

        await manager.emit_job_completed(job_id)

        # Collect all events
        events = []
        async for event_str in manager.subscribe(job_id):
            events.append(event_str)

        # Verify event sequence
        event_types = []
        for e in events:
            for line in e.split("\n"):
                if line.startswith("event: "):
                    event_types.append(line[7:])

        assert event_types[0] == "job_started"
        assert event_types[-1] == "job_completed"

        # Count specific event types
        assert event_types.count("item_started") == 2
        assert event_types.count("item_step") == 8  # 4 steps x 2 items
        assert event_types.count("item_completed") == 2
        assert event_types.count("job_progress") == 2  # After each item_completed

    @pytest.mark.asyncio
    async def test_sse_with_cancellation(self):
        """Should handle cancellation gracefully in SSE flow."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        urls = ["url1", "url2", "url3"]
        job_id = manager.create_job(urls)

        # Emit only first item then cancel
        await manager.emit_job_started(job_id)
        await manager.emit_item_completed(job_id, 0, "url1", True)

        manager.cancel_job(job_id)
        await manager.emit_job_completed(job_id)

        events = []
        async for event_str in manager.subscribe(job_id):
            events.append(event_str)

        job = manager.get_job(job_id)
        assert job.is_cancelled
        assert job.completed == 1

    @pytest.mark.asyncio
    async def test_sse_event_data_parseable(self):
        """All event data fields should be parseable as JSON."""
        manager = SSEProgressManager(heartbeat_interval=30.0)
        job_id = manager.create_job(["url1"])

        await manager.emit_job_started(job_id)
        await manager.emit_item_started(job_id, 0, "url1")
        await manager.emit_item_step(job_id, 0, "url1", "scraping")
        await manager.emit_item_completed(job_id, 0, "url1", True, {"title": "Test"})
        await manager.emit_job_completed(job_id)

        async for event_str in manager.subscribe(job_id):
            for line in event_str.split("\n"):
                if line.startswith("data: "):
                    data_str = line[6:]
                    parsed = json.loads(data_str)
                    assert isinstance(parsed, dict)
