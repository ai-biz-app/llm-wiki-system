"""
Graph rebuild scheduler with debouncing.

Hybrid approach:
- Auto: debounced rebuild 5 min after last ingestion (batches rapid uploads)
- Manual: POST /api/graph/rebuild for on-demand rebuilds
- Cron: nightly safety-net rebuild
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from backend.config import get_settings
from backend.services.graphify import get_graphify_service, GraphifyService
from backend.services.graph_sync import get_graph_sync_service, GraphSyncService

logger = logging.getLogger(__name__)

# Default debounce delay in seconds
DEFAULT_DEBOUNCE_SECONDS = 300  # 5 minutes


class GraphRebuildScheduler:
    """Schedules graph rebuilds with debouncing and status tracking."""

    def __init__(self, debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS):
        self.debounce_seconds = debounce_seconds
        self._pending_task: Optional[asyncio.Task] = None
        self._last_rebuild: Optional[datetime] = None
        self._status: str = "idle"  # idle | pending | running | failed
        self._message: str = ""
        self._lock = asyncio.Lock()

    @property
    def status(self) -> dict:
        return {
            "status": self._status,
            "message": self._message,
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
            "pending": self._pending_task is not None and not self._pending_task.done(),
        }

    async def schedule_rebuild(self) -> dict:
        """Schedule a debounced rebuild. Cancels any pending rebuild and resets timer."""
        async with self._lock:
            # Cancel existing pending rebuild
            if self._pending_task and not self._pending_task.done():
                self._pending_task.cancel()
                try:
                    await self._pending_task
                except asyncio.CancelledError:
                    pass
                logger.info("Cancelled previous pending graph rebuild")

            self._status = "pending"
            self._message = f"Rebuild scheduled in {self.debounce_seconds // 60} minutes"

            # Schedule new rebuild
            self._pending_task = asyncio.create_task(
                self._run_debounced_rebuild(self.debounce_seconds)
            )

        return self.status

    async def rebuild_now(self) -> dict:
        """Trigger an immediate rebuild, cancelling any pending debounced rebuild."""
        async with self._lock:
            if self._pending_task and not self._pending_task.done():
                self._pending_task.cancel()
                try:
                    await self._pending_task
                except asyncio.CancelledError:
                    pass

            # Run immediately
            self._pending_task = asyncio.create_task(self._execute_rebuild())

        return self.status

    async def _run_debounced_rebuild(self, delay_seconds: int):
        """Wait for delay, then rebuild."""
        try:
            await asyncio.sleep(delay_seconds)
            await self._execute_rebuild()
        except asyncio.CancelledError:
            logger.info("Debounced graph rebuild was cancelled")
            raise

    async def _execute_rebuild(self):
        """Run the actual graph rebuild."""
        self._status = "running"
        self._message = "Graph rebuild in progress..."
        logger.info("Starting graph rebuild")

        try:
            settings = get_settings()
            graphify_service: Optional[GraphifyService] = get_graphify_service()
            sync_service: Optional[GraphSyncService] = get_graph_sync_service()

            if not graphify_service:
                self._status = "failed"
                self._message = "Graphify service not initialized"
                logger.error(self._message)
                return

            # Run graphify on the raw sources directory
            corpus_dir = Path(settings.wiki_path) / "raw"
            if not corpus_dir.exists():
                # Fallback to wiki root if raw/ doesn't exist
                corpus_dir = Path(settings.wiki_path)

            result = await graphify_service.run_graphify(
                corpus_dir=corpus_dir,
                update=True,  # Incremental rebuild with SHA256 cache
            )

            if result.success:
                # Reload graph in sync service
                if sync_service:
                    sync_service.load_graph()

                self._last_rebuild = datetime.now()
                self._status = "idle"
                self._message = result.message
                logger.info(f"Graph rebuild complete: {result.message}")
            else:
                self._status = "failed"
                self._message = result.message or "Unknown error"
                logger.error(f"Graph rebuild failed: {result.message}")

        except Exception as e:
            self._status = "failed"
            self._message = str(e)
            logger.exception("Graph rebuild failed with exception")


# Global singleton instance
_scheduler: Optional[GraphRebuildScheduler] = None


def init_graph_rebuild_scheduler(debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS) -> GraphRebuildScheduler:
    """Initialize the global graph rebuild scheduler."""
    global _scheduler
    _scheduler = GraphRebuildScheduler(debounce_seconds=debounce_seconds)
    return _scheduler


def get_graph_rebuild_scheduler() -> Optional[GraphRebuildScheduler]:
    """Get the global scheduler instance."""
    return _scheduler
