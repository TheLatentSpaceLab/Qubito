"""Asyncio-based cron scheduler that runs inside the daemon process."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from logging import getLogger

from croniter import croniter

from src.scheduler.models import CronJob, load_cron_jobs, save_cron_jobs

logger = getLogger(__name__)


class Scheduler:
    """Runs cron jobs on schedule using an asyncio task."""

    def __init__(self) -> None:
        self._jobs: list[CronJob] = []
        self._task: asyncio.Task | None = None

    def load(self) -> None:
        """Load jobs from the persistent JSON file."""
        self._jobs = load_cron_jobs()
        logger.info("Loaded %d cron job(s)", len(self._jobs))

    def save(self) -> None:
        """Persist current jobs to disk."""
        save_cron_jobs(self._jobs)

    @property
    def jobs(self) -> list[CronJob]:
        return list(self._jobs)

    def add(self, job: CronJob) -> None:
        """Add a job and persist."""
        self._jobs.append(job)
        self.save()

    def remove(self, job_id: str) -> bool:
        """Remove a job by ID. Returns True if found."""
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.id != job_id]
        if len(self._jobs) < before:
            self.save()
            return True
        return False

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        """Enable or disable a job. Returns True if found."""
        for j in self._jobs:
            if j.id == job_id:
                j.enabled = enabled
                self.save()
                return True
        return False

    def get(self, job_id: str) -> CronJob | None:
        """Look up a job by ID."""
        for j in self._jobs:
            if j.id == job_id:
                return j
        return None

    def start(self) -> None:
        """Start the scheduler loop as a background asyncio task."""
        self.load()
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        """Cancel the scheduler task."""
        if self._task:
            self._task.cancel()

    async def _run_loop(self) -> None:
        """Main scheduler loop — sleep until the next job fires."""
        while True:
            next_job, delay = self._next_due()
            if next_job is None:
                await asyncio.sleep(60)
                self.load()
                continue

            await asyncio.sleep(max(delay, 0))
            await self._fire(next_job)

    def _next_due(self) -> tuple[CronJob | None, float]:
        """Find the soonest enabled job and seconds until it fires."""
        now = datetime.now(timezone.utc)
        best_job: CronJob | None = None
        best_delay = float("inf")

        for job in self._jobs:
            if not job.enabled:
                continue
            try:
                cron = croniter(job.cron_expression, now)
                next_fire = cron.get_next(datetime)
                delay = (next_fire - now).total_seconds()
                if delay < best_delay:
                    best_delay = delay
                    best_job = job
            except (ValueError, KeyError):
                logger.warning("Invalid cron expression for job '%s': %s", job.name, job.cron_expression)

        return best_job, best_delay

    async def _fire(self, job: CronJob) -> None:
        """Execute a job and optionally push the result."""
        from src.scheduler.executor import execute_job

        logger.info("Firing cron job '%s': %s", job.name, job.action)
        try:
            response = await asyncio.to_thread(execute_job, job)
            job.last_run = datetime.now(timezone.utc).isoformat()
            self.save()

            if job.channel_target:
                from src.channels.push import push_message
                await asyncio.to_thread(push_message, job.channel_target, response)
        except Exception:
            logger.exception("Cron job '%s' failed", job.name)
