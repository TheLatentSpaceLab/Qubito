"""Execute a cron job by creating a temporary daemon session."""

from __future__ import annotations

from logging import getLogger

from src.daemon.client import DaemonClient
from src.scheduler.models import CronJob

logger = getLogger(__name__)


def execute_job(job: CronJob, client: DaemonClient | None = None) -> str:
    """Run a cron job's action via the daemon and return the response.

    Parameters
    ----------
    job : CronJob
        The job to execute.
    client : DaemonClient or None
        Daemon client. Created with defaults if None.

    Returns
    -------
    str
        The agent's response text.
    """
    client = client or DaemonClient()
    session = client.create_session(character=job.character)
    try:
        response, elapsed = client.send_message(session.id, job.action)
        logger.info(
            "Cron job '%s' completed in %.1fs: %s",
            job.name, elapsed, response[:100],
        )
        return response
    finally:
        client.delete_session(session.id)
