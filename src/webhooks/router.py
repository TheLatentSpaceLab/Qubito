"""FastAPI router for incoming webhook requests."""

from __future__ import annotations

import hashlib
import hmac
from logging import getLogger

from fastapi import APIRouter, HTTPException, Request

from src.webhooks.models import load_webhooks

logger = getLogger(__name__)

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhook_router.post("/{webhook_id}")
async def receive_webhook(webhook_id: str, request: Request) -> dict:
    """Catch-all webhook receiver.

    1. Look up WebhookConfig by ID.
    2. Verify HMAC signature if a secret is configured.
    3. Render action_template with the JSON payload.
    4. Send to a temporary daemon session.
    5. Optionally push the result to a channel target.
    """
    import asyncio
    from src.scheduler.executor import execute_job
    from src.scheduler.models import CronJob

    hooks = load_webhooks()
    hook = next((h for h in hooks if h.id == webhook_id), None)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if not hook.enabled:
        raise HTTPException(status_code=403, detail="Webhook is disabled")

    body_bytes = await request.body()

    if hook.secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            hook.secret.encode(), body_bytes, hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    action = _render_template(hook.action_template, payload)
    logger.info("Webhook '%s' fired: %s", hook.name, action[:100])

    temp_job = CronJob(name=f"webhook-{hook.name}", action=action, character=hook.character)
    response = await asyncio.to_thread(execute_job, temp_job)

    if hook.channel_target:
        from src.channels.push import push_message
        await asyncio.to_thread(push_message, hook.channel_target, response)

    return {"status": "processed", "response": response[:500]}


def _render_template(template: str, payload: dict) -> str:
    """Render an action template with payload values using safe format_map."""
    try:
        return template.format_map(_FlatDict(payload))
    except (KeyError, IndexError, ValueError):
        return template


class _FlatDict(dict):
    """Dict subclass that returns the key itself for missing keys."""

    def __missing__(self, key: str) -> str:
        parts = key.split(".")
        val = dict(self)
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, f"{{{key}}}")
            else:
                return f"{{{key}}}"
        return str(val) if not isinstance(val, dict) else str(val)
