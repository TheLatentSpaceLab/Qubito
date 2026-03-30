"""FastAPI application with session and message routes."""

from __future__ import annotations

import asyncio
import json as json_mod
import queue
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import src.display as _display_mod

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config.resolver import QConfig
from src.daemon.session import SessionManager

from functools import lru_cache

from src.agents.character_loader import _collect_files

from src.bus import Event, EventBus

_start_time: datetime | None = None
sessions = SessionManager()
config = QConfig()
bus = EventBus()


def _char_filename(name: str, dirs: list[Path] | None) -> str:
    """Resolve a character display name back to its stem filename."""
    from src.agents.character_loader import _parse_character_file
    for p in _collect_files(dirs):
        c = _parse_character_file(p)
        if c.name == name:
            return p.stem
    return ""


@lru_cache(maxsize=1)
def _skill_registry() -> object:
    """Lazily load the skill registry once."""
    from src.skills import SkillRegistry, load_all_skills
    skills = load_all_skills(dirs=config.skills_dirs)
    return SkillRegistry(skills)


def _resolve_skill_command(message: str) -> tuple[object | None, str | None]:
    """Check if a message is a slash command and resolve the skill.

    Returns
    -------
    tuple of (SkillData or None, str or None)
        The matched skill and its instructions (for LLM type), or (None, None).
    """
    if not message.startswith("/"):
        return None, None
    command = message.split()[0].lstrip("/")
    registry = _skill_registry()
    skill = registry.get(command)
    if not skill:
        return None, None
    if skill.skill_type == "llm":
        return skill, skill.instructions
    return skill, None


def _persist_turn(session_id: str, user_message: str, response: str) -> None:
    """Save a user/assistant message pair and emit bus events."""
    if sessions.db:
        try:
            sessions.db.save_message(session_id, {"role": "user", "content": user_message})
            sessions.db.save_message(session_id, {"role": "assistant", "content": response})
            sessions.db.touch_session(session_id)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to persist turn for session %s", session_id, exc_info=True,
            )

    # Fire-and-forget event emission (non-blocking from sync context)
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        loop.create_task(bus.emit(Event(
            type="message.inbound",
            session_id=session_id,
            payload={"text": user_message},
        )))
        loop.create_task(bus.emit(Event(
            type="message.outbound",
            session_id=session_id,
            payload={"text": response},
        )))
    except RuntimeError:
        pass  # no running loop (e.g. tests)


def _run_handler_captured(
    registry: object, skill: object, agent: object, message: str,
) -> str:
    """Execute a handler skill and capture its console output."""
    with _display_mod.console.capture() as capture:
        registry.execute_handler(skill, agent, message)
    return capture.get().strip()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage daemon startup and shutdown."""
    import logging
    from src.constants import AI_CLIENT_MODEL, AI_CLIENT_FALLBACK_MODEL, AI_CLIENT_PROVIDER
    from src.persistence import ConversationDB
    log = logging.getLogger(__name__)
    global _start_time
    _start_time = datetime.now(timezone.utc)

    config.global_dir.mkdir(parents=True, exist_ok=True)
    db = ConversationDB(config.db_path)
    sessions.db = db

    from src.constants import SESSION_TIMEOUT_MINUTES
    log.info("Provider: %s | Model: %s | Fallback: %s",
             AI_CLIENT_PROVIDER, AI_CLIENT_MODEL, AI_CLIENT_FALLBACK_MODEL or "none")

    async def _eviction_loop() -> None:
        while True:
            await asyncio.sleep(60)
            evicted = sessions.evict_idle(SESSION_TIMEOUT_MINUTES)
            if evicted:
                log.info("Evicted %d idle session(s)", len(evicted))

    from src.agents.registry import AgentRegistry
    from src.routing import MessageRouter
    from src.scheduler import Scheduler
    from src.tasks import TaskQueue
    registry = AgentRegistry()
    sessions.registry = registry
    app.state.agent_registry = registry
    app.state.router = MessageRouter()
    scheduler = Scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    app.state.task_queue = TaskQueue()

    eviction_task = asyncio.create_task(_eviction_loop())
    yield
    scheduler.stop()
    eviction_task.cancel()
    sessions.close_all()
    db.close()


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Returns
    -------
    FastAPI
        Configured application with startup/shutdown hooks and all routes.
    """
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Qubito Daemon", version="0.1.0", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_routes(app)

    from src.webhooks.router import webhook_router
    from src.web.routes import web_router
    app.include_router(webhook_router)
    app.include_router(web_router)

    webchat_dir = Path(__file__).resolve().parent.parent / "webchat" / "static"
    if webchat_dir.is_dir():
        app.mount("/chat", StaticFiles(directory=str(webchat_dir), html=True), name="webchat")

    return app


# --- Request / Response schemas ---


class CharacterInfo(BaseModel):
    filename: str
    name: str
    emoji: str
    color: str


class CreateSessionRequest(BaseModel):
    character: str | None = None
    agent_id: str | None = None
    channel_type: str | None = None
    channel_id: str | None = None


class CreateSessionResponse(BaseModel):
    id: str
    character_name: str
    emoji: str
    color: str
    hi_message: str


class SessionInfo(BaseModel):
    id: str
    character_name: str
    emoji: str
    color: str
    created_at: str
    message_count: int


class MessageRequest(BaseModel):
    session_id: str
    message: str
    skill_instructions: str | None = None


class MessageResponse(BaseModel):
    response: str
    elapsed: float
    is_handler: bool = False


class PushRequest(BaseModel):
    channel_target: str
    message: str


class StatusResponse(BaseModel):
    status: str
    sessions_count: int
    uptime_seconds: float
    provider: str = ""
    model: str = ""
    fallback_model: str = ""


# --- Routes ---


def _register_routes(app: FastAPI) -> None:
    """Attach all API routes to the app.

    Parameters
    ----------
    app : FastAPI
        The application instance to register routes on.
    """

    @app.get("/status", response_model=StatusResponse)
    def get_status() -> StatusResponse:
        from src.constants import (
            AI_CLIENT_FALLBACK_MODEL,
            AI_CLIENT_MODEL,
            AI_CLIENT_PROVIDER,
        )
        uptime = 0.0
        if _start_time:
            delta = datetime.now(timezone.utc) - _start_time
            uptime = delta.total_seconds()
        return StatusResponse(
            status="ok",
            sessions_count=len(sessions.list_all()),
            uptime_seconds=round(uptime, 1),
            provider=AI_CLIENT_PROVIDER or "",
            model=AI_CLIENT_MODEL or "",
            fallback_model=AI_CLIENT_FALLBACK_MODEL or "",
        )

    @app.get("/characters", response_model=list[CharacterInfo])
    def list_characters() -> list[CharacterInfo]:
        from src.agents.character_loader import load_all_characters
        return [
            CharacterInfo(
                filename=_char_filename(c.name, config.agents_dirs),
                name=c.name,
                emoji=c.emoji,
                color=c.color,
            )
            for c in load_all_characters(dirs=config.agents_dirs)
        ]

    @app.get("/sessions", response_model=list[SessionInfo])
    def list_sessions() -> list[SessionInfo]:
        return [
            SessionInfo(
                id=s.id,
                character_name=s.character_name,
                emoji=s.emoji,
                color=s.color,
                created_at=s.created_at.isoformat(),
                message_count=s.message_count,
            )
            for s in sessions.list_all()
        ]

    @app.post("/sessions", response_model=CreateSessionResponse, status_code=201)
    def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
        agent_id = body.agent_id
        if not agent_id and body.channel_type and body.channel_id and hasattr(app.state, "router"):
            agent_id = app.state.router.resolve(body.channel_type, body.channel_id)
        session = sessions.create(config, character=body.character, agent_id=agent_id)
        greeting = session.agent.get_start_message()
        return CreateSessionResponse(
            id=session.id,
            character_name=session.character_name,
            emoji=session.emoji,
            color=session.color,
            hi_message=greeting,
        )

    @app.delete("/sessions/{session_id}", status_code=204)
    def delete_session(session_id: str) -> None:
        if not sessions.delete(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

    @app.post("/message", response_model=MessageResponse)
    async def send_message(body: MessageRequest) -> MessageResponse:
        session = sessions.get(body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.touch()

        skill, skill_instructions = _resolve_skill_command(body.message)
        if skill_instructions:
            body.skill_instructions = skill_instructions

        start = time.perf_counter()
        if skill and skill.skill_type == "handler":
            response = await asyncio.to_thread(
                _run_handler_captured,
                _skill_registry(), skill, session.agent, body.message,
            )
            elapsed = time.perf_counter() - start
            return MessageResponse(
                response=response, elapsed=round(elapsed, 2), is_handler=True,
            )
        else:
            response = await asyncio.to_thread(
                session.agent.message,
                body.message,
                skill_instructions=body.skill_instructions,
            )
        elapsed = time.perf_counter() - start

        _persist_turn(body.session_id, body.message, response)
        return MessageResponse(response=response, elapsed=round(elapsed, 2))

    @app.post("/message/stream")
    async def send_message_stream(body: MessageRequest) -> StreamingResponse:
        session = sessions.get(body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.touch()

        skill, skill_instructions = _resolve_skill_command(body.message)
        if skill_instructions:
            body.skill_instructions = skill_instructions

        progress_q: queue.Queue[str | None] = queue.Queue()

        def _do_work() -> None:
            original_cb = session.agent.on_tool_call

            def _tracking_cb(tool_name: str, arguments: dict) -> bool:
                args_short = ", ".join(
                    f"{k}={str(v)[:60]}" for k, v in list(arguments.items())[:2]
                )
                progress_q.put(f"{tool_name}({args_short})")
                return original_cb(tool_name, arguments)

            session.agent.on_tool_call = _tracking_cb
            start = time.perf_counter()
            try:
                if skill and skill.skill_type == "handler":
                    with _display_mod.console.capture() as capture:
                        _skill_registry().execute_handler(
                            skill, session.agent, body.message,
                        )
                    response = capture.get().strip()
                    elapsed = time.perf_counter() - start
                    result = {"response": response, "elapsed": round(elapsed, 2), "is_handler": True}
                else:
                    response = session.agent.message(
                        body.message, skill_instructions=body.skill_instructions,
                    )
                    elapsed = time.perf_counter() - start
                    result = {"response": response, "elapsed": round(elapsed, 2), "is_handler": False}
            except Exception as exc:
                result = {"response": str(exc), "elapsed": 0, "is_handler": False}
            finally:
                session.agent.on_tool_call = original_cb

            if not result.get("is_handler"):
                _persist_turn(body.session_id, body.message, result.get("response", ""))

            progress_q.put(None)
            progress_q.put(json_mod.dumps({"type": "done", **result}))

        thread = threading.Thread(target=_do_work, daemon=True)
        thread.start()

        async def _event_stream() -> AsyncIterator[str]:
            while True:
                try:
                    msg = await asyncio.to_thread(progress_q.get, timeout=300)
                except Exception:
                    break
                if msg is None:
                    final = await asyncio.to_thread(progress_q.get, timeout=5)
                    yield f"data: {final}\n\n"
                    break
                yield f"data: {json_mod.dumps({'type': 'progress', 'message': msg})}\n\n"

        return StreamingResponse(_event_stream(), media_type="text/event-stream")

    @app.get("/sessions/{session_id}/history")
    def get_session_history(session_id: str) -> list[dict[str, str]]:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.agent.get_history()

    @app.post("/push")
    async def push_to_channel(body: PushRequest) -> dict:
        from src.channels.push import push_message
        ok = await asyncio.to_thread(push_message, body.channel_target, body.message)
        if not ok:
            raise HTTPException(status_code=502, detail="Push delivery failed")
        return {"status": "sent"}

    # --- Cron routes ---

    @app.get("/cron")
    def list_cron_jobs() -> list[dict]:
        from src.scheduler.models import load_cron_jobs, asdict
        from dataclasses import asdict as _asdict
        return [_asdict(j) for j in load_cron_jobs()]

    @app.post("/cron", status_code=201)
    def create_cron_job(body: dict) -> dict:
        from dataclasses import asdict as _asdict
        from src.scheduler.models import CronJob, load_cron_jobs, save_cron_jobs
        job = CronJob(**body)
        jobs = load_cron_jobs()
        jobs.append(job)
        save_cron_jobs(jobs)
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.load()
        return _asdict(job)

    @app.delete("/cron/{job_id}", status_code=204)
    def delete_cron_job(job_id: str) -> None:
        from src.scheduler.models import load_cron_jobs, save_cron_jobs
        jobs = load_cron_jobs()
        new_jobs = [j for j in jobs if j.id != job_id]
        if len(new_jobs) == len(jobs):
            raise HTTPException(status_code=404, detail="Cron job not found")
        save_cron_jobs(new_jobs)
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.load()

    @app.patch("/cron/{job_id}")
    def patch_cron_job(job_id: str, body: dict) -> dict:
        from dataclasses import asdict as _asdict
        from src.scheduler.models import load_cron_jobs, save_cron_jobs
        jobs = load_cron_jobs()
        for j in jobs:
            if j.id == job_id:
                if "enabled" in body:
                    j.enabled = body["enabled"]
                save_cron_jobs(jobs)
                if hasattr(app.state, "scheduler"):
                    app.state.scheduler.load()
                return _asdict(j)
        raise HTTPException(status_code=404, detail="Cron job not found")

    @app.post("/cron/{job_id}/run")
    async def run_cron_job(job_id: str) -> dict:
        from src.scheduler.models import load_cron_jobs
        from src.scheduler.executor import execute_job
        jobs = load_cron_jobs()
        job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Cron job not found")
        response = await asyncio.to_thread(execute_job, job)
        return {"response": response}

    # --- Background task routes ---

    @app.post("/tasks", status_code=201)
    def create_task(body: dict) -> dict:
        from dataclasses import asdict as _asdict
        from src.tasks.models import BackgroundTask
        task = BackgroundTask(
            description=body.get("description", ""),
            character=body.get("character"),
        )
        app.state.task_queue.submit(task)
        return _asdict(task)

    @app.get("/tasks")
    def list_tasks() -> list[dict]:
        from dataclasses import asdict as _asdict
        return [_asdict(t) for t in app.state.task_queue.tasks]

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        from dataclasses import asdict as _asdict
        task = app.state.task_queue.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _asdict(task)

    @app.delete("/tasks/{task_id}", status_code=204)
    def cancel_task(task_id: str) -> None:
        if not app.state.task_queue.cancel(task_id):
            raise HTTPException(status_code=404, detail="Task not found or already completed")

    # --- Agent registry routes ---

    @app.get("/agents")
    def list_agents() -> list[dict]:
        from dataclasses import asdict as _asdict
        return [_asdict(a) for a in app.state.agent_registry.list_agents()]

    @app.post("/agents", status_code=201)
    def register_agent(body: dict) -> dict:
        from dataclasses import asdict as _asdict
        from src.agents.registry import AgentConfig
        cfg = AgentConfig(**body)
        app.state.agent_registry.register(cfg)
        return _asdict(cfg)

    @app.get("/agents/{agent_id}")
    def get_agent(agent_id: str) -> dict:
        from dataclasses import asdict as _asdict
        cfg = app.state.agent_registry.get_config(agent_id)
        if not cfg:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _asdict(cfg)

    @app.delete("/agents/{agent_id}", status_code=204)
    def delete_agent(agent_id: str) -> None:
        if not app.state.agent_registry.unregister(agent_id):
            raise HTTPException(status_code=404, detail="Agent not found")

    # --- Routing rules routes ---

    @app.get("/routes")
    def list_routes() -> list[dict]:
        from dataclasses import asdict as _asdict
        return [_asdict(r) for r in app.state.router.rules]

    @app.post("/routes", status_code=201)
    def create_route(body: dict) -> dict:
        from dataclasses import asdict as _asdict
        from src.routing.models import RoutingRule, load_routing_rules, save_routing_rules
        rule = RoutingRule(**body)
        rules = load_routing_rules()
        rules.append(rule)
        save_routing_rules(rules)
        app.state.router.load()
        return _asdict(rule)

    @app.delete("/routes/{rule_id}", status_code=204)
    def delete_route(rule_id: str) -> None:
        from src.routing.models import load_routing_rules, save_routing_rules
        rules = load_routing_rules()
        new_rules = [r for r in rules if r.id != rule_id]
        if len(new_rules) == len(rules):
            raise HTTPException(status_code=404, detail="Routing rule not found")
        save_routing_rules(new_rules)
        app.state.router.load()
