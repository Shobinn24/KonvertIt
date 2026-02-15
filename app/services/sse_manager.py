"""
Server-Sent Events (SSE) manager for real-time progress streaming.

Manages active bulk conversion jobs and provides async generators
for streaming progress events to connected clients via SSE.

SSE Event Types:
    - job_started: Bulk conversion job initiated with total URL count.
    - item_started: Individual URL conversion started (with index).
    - item_step: Pipeline step changed for an item (scraping, compliance, etc.).
    - item_completed: Individual URL conversion finished (success or failure).
    - job_progress: Aggregate progress update after each item completes.
    - job_completed: Entire bulk job finished with final summary.
    - error: Unexpected error in the SSE stream.
    - heartbeat: Keep-alive ping sent every N seconds.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

logger = logging.getLogger(__name__)


class SSEEventType(StrEnum):
    """Types of SSE events emitted during bulk conversion."""

    JOB_STARTED = "job_started"
    ITEM_STARTED = "item_started"
    ITEM_STEP = "item_step"
    ITEM_COMPLETED = "item_completed"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class SSEEvent:
    """A single SSE event to be sent to the client."""

    event: SSEEventType
    data: dict
    id: str = ""
    retry: int | None = None

    def format(self) -> str:
        """Format as an SSE-compliant text block.

        SSE spec: each field on its own line, double newline to end the event.
        """
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        lines.append(f"event: {self.event.value}")
        lines.append(f"data: {json.dumps(self.data)}")
        return "\n".join(lines) + "\n\n"


@dataclass
class JobState:
    """In-memory state for an active bulk conversion job."""

    job_id: str
    total: int
    completed: int = 0
    failed: int = 0
    urls: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    is_cancelled: bool = False

    @property
    def pending(self) -> int:
        return self.total - self.completed - self.failed

    @property
    def progress_pct(self) -> float:
        if self.total == 0:
            return 100.0
        return round(((self.completed + self.failed) / self.total) * 100, 1)

    @property
    def is_done(self) -> bool:
        return self.pending == 0 or self.is_cancelled

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
            "progress_pct": self.progress_pct,
            "is_done": self.is_done,
            "is_cancelled": self.is_cancelled,
        }


class SSEProgressManager:
    """
    Manages SSE event streams for bulk conversion jobs.

    Each job gets:
    - A unique job_id
    - An asyncio.Queue for events
    - A JobState tracking progress

    The manager provides:
    - create_job() — register a new bulk conversion job
    - emit() — push an SSE event to the job's queue
    - subscribe() — async generator yielding formatted SSE strings
    - cancel_job() — signal cancellation to stop processing

    Usage in endpoint:
        manager = SSEProgressManager()
        job_id = manager.create_job(urls)

        async def generate():
            # Run conversion in background, emitting events via callbacks
            task = asyncio.create_task(run_conversion(job_id, urls, manager))
            async for event_str in manager.subscribe(job_id):
                yield event_str

        return StreamingResponse(generate(), media_type="text/event-stream")
    """

    def __init__(self, heartbeat_interval: float = 15.0):
        self._jobs: dict[str, JobState] = {}
        self._queues: dict[str, asyncio.Queue[SSEEvent | None]] = {}
        self._heartbeat_interval = heartbeat_interval

    @property
    def active_jobs(self) -> dict[str, JobState]:
        """Return all active (non-done) jobs."""
        return {jid: js for jid, js in self._jobs.items() if not js.is_done}

    def create_job(self, urls: list[str]) -> str:
        """
        Register a new bulk conversion job.

        Args:
            urls: List of product URLs to convert.

        Returns:
            Unique job_id string.
        """
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobState(
            job_id=job_id,
            total=len(urls),
            urls=list(urls),
        )
        self._queues[job_id] = asyncio.Queue()
        logger.info(f"[SSE] Created job {job_id} with {len(urls)} URLs")
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        """Get the current state of a job."""
        return self._jobs.get(job_id)

    async def emit(self, job_id: str, event: SSEEvent) -> None:
        """
        Push an SSE event to the job's queue.

        Args:
            job_id: The job to emit to.
            event: The SSE event to send.
        """
        queue = self._queues.get(job_id)
        if queue is None:
            logger.warning(f"[SSE] Attempted to emit to unknown job {job_id}")
            return
        await queue.put(event)

    async def emit_job_started(self, job_id: str) -> None:
        """Emit a job_started event."""
        job = self._jobs.get(job_id)
        if not job:
            return
        await self.emit(job_id, SSEEvent(
            event=SSEEventType.JOB_STARTED,
            data={
                "job_id": job_id,
                "total": job.total,
                "urls": job.urls,
                "started_at": job.started_at.isoformat(),
            },
        ))

    async def emit_item_started(self, job_id: str, index: int, url: str) -> None:
        """Emit an item_started event for a specific URL."""
        await self.emit(job_id, SSEEvent(
            event=SSEEventType.ITEM_STARTED,
            data={
                "job_id": job_id,
                "index": index,
                "url": url,
            },
        ))

    async def emit_item_step(
        self, job_id: str, index: int, url: str, step: str
    ) -> None:
        """Emit an item_step event when the pipeline step changes."""
        await self.emit(job_id, SSEEvent(
            event=SSEEventType.ITEM_STEP,
            data={
                "job_id": job_id,
                "index": index,
                "url": url,
                "step": step,
            },
        ))

    async def emit_item_completed(
        self,
        job_id: str,
        index: int,
        url: str,
        success: bool,
        result_data: dict | None = None,
        error: str = "",
    ) -> None:
        """Emit an item_completed event and update job state."""
        job = self._jobs.get(job_id)
        if not job:
            return

        if success:
            job.completed += 1
        else:
            job.failed += 1

        await self.emit(job_id, SSEEvent(
            event=SSEEventType.ITEM_COMPLETED,
            data={
                "job_id": job_id,
                "index": index,
                "url": url,
                "success": success,
                "result": result_data or {},
                "error": error,
            },
        ))

        # Follow up with a progress update
        await self.emit(job_id, SSEEvent(
            event=SSEEventType.JOB_PROGRESS,
            data=job.to_dict(),
        ))

    async def emit_job_completed(self, job_id: str) -> None:
        """Emit a job_completed event and signal stream end."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.finished_at = datetime.now()

        await self.emit(job_id, SSEEvent(
            event=SSEEventType.JOB_COMPLETED,
            data={
                **job.to_dict(),
                "finished_at": job.finished_at.isoformat(),
                "duration_seconds": (
                    job.finished_at - job.started_at
                ).total_seconds(),
            },
        ))

        # Send None sentinel to signal end of stream
        await self._queues[job_id].put(None)

    async def emit_error(self, job_id: str, error: str) -> None:
        """Emit an error event and end the stream."""
        await self.emit(job_id, SSEEvent(
            event=SSEEventType.ERROR,
            data={"job_id": job_id, "error": error},
        ))
        # Signal end of stream
        await self._queues[job_id].put(None)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job. The conversion loop should check is_cancelled.

        Returns:
            True if job was found and cancelled, False if not found.
        """
        job = self._jobs.get(job_id)
        if job and not job.is_done:
            job.is_cancelled = True
            logger.info(f"[SSE] Cancelled job {job_id}")
            return True
        return False

    async def subscribe(self, job_id: str) -> "AsyncGenerator[str, None]":
        """
        Async generator that yields formatted SSE event strings.

        Sends heartbeat pings every `heartbeat_interval` seconds to keep
        the connection alive. Terminates when a None sentinel is received.

        Args:
            job_id: The job to subscribe to.

        Yields:
            Formatted SSE event strings ready for StreamingResponse.
        """
        queue = self._queues.get(job_id)
        if queue is None:
            yield SSEEvent(
                event=SSEEventType.ERROR,
                data={"error": f"Unknown job: {job_id}"},
            ).format()
            return

        while True:
            try:
                # Wait for event with timeout for heartbeat
                event = await asyncio.wait_for(
                    queue.get(), timeout=self._heartbeat_interval
                )

                if event is None:
                    # Sentinel — stream is done
                    break

                yield event.format()

            except asyncio.TimeoutError:
                # No event within heartbeat interval — send keep-alive
                yield SSEEvent(
                    event=SSEEventType.HEARTBEAT,
                    data={"job_id": job_id, "timestamp": datetime.now().isoformat()},
                ).format()

    def cleanup_job(self, job_id: str) -> None:
        """Remove a completed job from memory."""
        self._jobs.pop(job_id, None)
        self._queues.pop(job_id, None)
        logger.debug(f"[SSE] Cleaned up job {job_id}")

    def cleanup_finished_jobs(self) -> int:
        """Remove all finished jobs. Returns count of cleaned jobs."""
        finished = [jid for jid, js in self._jobs.items() if js.is_done]
        for jid in finished:
            self.cleanup_job(jid)
        return len(finished)
