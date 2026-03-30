"""Asyncio-based background task queue."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from logging import getLogger

from src.daemon.client import DaemonClient
from src.tasks.models import BackgroundTask

logger = getLogger(__name__)


class TaskQueue:
    """Manages background tasks with a configurable worker pool."""

    def __init__(self, max_workers: int = 2) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._semaphore = asyncio.Semaphore(max_workers)

    @property
    def tasks(self) -> list[BackgroundTask]:
        return list(self._tasks.values())

    def get(self, task_id: str) -> BackgroundTask | None:
        return self._tasks.get(task_id)

    def submit(self, task: BackgroundTask) -> None:
        """Submit a task for background execution."""
        self._tasks[task.id] = task
        asyncio.create_task(self._run(task))

    def cancel(self, task_id: str) -> bool:
        """Mark a task as cancelled. Returns True if found."""
        task = self._tasks.get(task_id)
        if task and task.status in ("queued", "running"):
            task.status = "cancelled"
            return True
        return False

    async def _run(self, task: BackgroundTask) -> None:
        """Execute a task under the semaphore."""
        async with self._semaphore:
            if task.status == "cancelled":
                return

            task.status = "running"
            task.progress = "Starting..."
            logger.info("Background task '%s' started: %s", task.id, task.description)

            try:
                response = await asyncio.to_thread(self._execute, task)
                task.status = "completed"
                task.result = response
            except Exception as e:
                task.status = "failed"
                task.result = str(e)
                logger.exception("Background task '%s' failed", task.id)
            finally:
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.progress = ""

    @staticmethod
    def _execute(task: BackgroundTask) -> str:
        """Run the task action via a temporary daemon session."""
        client = DaemonClient()
        session = client.create_session(character=task.character)
        try:
            response, _ = client.send_message(session.id, task.description)
            return response
        finally:
            client.delete_session(session.id)
