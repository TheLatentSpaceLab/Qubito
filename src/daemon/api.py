"""FastAPI application with session and message routes."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config.resolver import QConfig
from src.daemon.session import SessionManager

_start_time: datetime | None = None
sessions = SessionManager()
config = QConfig()


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Returns
    -------
    FastAPI
        Configured application with startup/shutdown hooks and all routes.
    """
    app = FastAPI(title="Qubito Daemon", version="0.1.0")
    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
    _register_routes(app)
    return app


def _on_startup() -> None:
    global _start_time
    _start_time = datetime.now(timezone.utc)


def _on_shutdown() -> None:
    sessions.close_all()


# --- Request / Response schemas ---


class CreateSessionRequest(BaseModel):
    character: str | None = None


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


class StatusResponse(BaseModel):
    status: str
    sessions_count: int
    uptime_seconds: float


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
        uptime = 0.0
        if _start_time:
            delta = datetime.now(timezone.utc) - _start_time
            uptime = delta.total_seconds()
        return StatusResponse(
            status="ok",
            sessions_count=len(sessions.list_all()),
            uptime_seconds=round(uptime, 1),
        )

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
        session = sessions.create(config, character=body.character)
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
        start = time.perf_counter()
        response = await asyncio.to_thread(
            session.agent.message,
            body.message,
            skill_instructions=body.skill_instructions,
        )
        elapsed = time.perf_counter() - start
        return MessageResponse(response=response, elapsed=round(elapsed, 2))

    @app.get("/sessions/{session_id}/history")
    def get_session_history(session_id: str) -> list[dict[str, str]]:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.agent.get_history()
